"""
LLM Router and Gemini API Multi-Key Pool Manager for Project Aether-Human.
Provides robust sliding-window rate limiting, least-loaded key distribution,
multi-model cascading failover, and token metrics across Google Gemini API credentials.
Engineered to handle ~1,000 active users safely across the 11-key pool without 429 exhaustion.
"""

from __future__ import annotations

import asyncio
from collections import deque
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from aether_human_core.config.settings import settings

logger = logging.getLogger("Aether.LLMRouter")


class KeyHealthTracker:
    """
    Monitors health metrics, sliding-window RPM, and cool-off periods for a single API key.
    """
    def __init__(self, key: str, index: int):
        self.key: str = key
        self.index: int = index
        self.total_calls: int = 0
        self.successful_calls: int = 0
        self.failed_calls: int = 0
        self.rate_limited_count: int = 0
        self.last_used_timestamp: float = 0.0
        self.cool_down_until: float = 0.0
        self.is_active: bool = True
        # 60-second sliding window timestamps
        self.call_timestamps: deque[float] = deque()

    @property
    def masked_key(self) -> str:
        if len(self.key) <= 10:
            return "***"
        return f"{self.key[:6]}...{self.key[-4:]}"

    def clean_old_calls(self, now: Optional[float] = None) -> None:
        t = now or time.time()
        window_start = t - 60.0
        while self.call_timestamps and self.call_timestamps[0] < window_start:
            self.call_timestamps.popleft()

    def get_current_rpm(self, now: Optional[float] = None) -> int:
        self.clean_old_calls(now)
        return len(self.call_timestamps)

    def is_available(self, max_rpm: int = 12) -> bool:
        if not self.is_active:
            return False
        now = time.time()
        if now < self.cool_down_until:
            return False
        if self.get_current_rpm(now) >= max_rpm:
            return False
        return True

    def seconds_until_available(self, max_rpm: int = 12) -> float:
        if not self.is_active:
            return 9999.0
        now = time.time()
        # Cooldown check
        cooldown_wait = max(0.0, self.cool_down_until - now)
        # Sliding window check
        self.clean_old_calls(now)
        if len(self.call_timestamps) >= max_rpm:
            oldest = self.call_timestamps[0]
            rpm_wait = max(0.0, (oldest + 60.0) - now)
        else:
            rpm_wait = 0.0
        return max(cooldown_wait, rpm_wait)

    def record_attempt(self) -> None:
        now = time.time()
        self.total_calls += 1
        self.last_used_timestamp = now
        self.call_timestamps.append(now)

    def mark_success(self) -> None:
        self.successful_calls += 1
        # Reset cooldown on success
        self.cool_down_until = 0.0

    def mark_rate_limited(self, cool_off_seconds: float = 20.0) -> None:
        self.failed_calls += 1
        self.rate_limited_count += 1
        self.cool_down_until = time.time() + cool_off_seconds
        logger.warning(
            f"Key [{self.index}] ({self.masked_key}) rate-limited (429). Cooldown: {cool_off_seconds:.1f}s."
        )

    def mark_fatal_error(self) -> None:
        self.failed_calls += 1
        self.is_active = False
        logger.error(f"Key [{self.index}] ({self.masked_key}) marked inactive due to fatal auth/permission error.")


ROBOTIC_RANT_TRIGGERS = [
    "مفكرني روبوت", "هو مفكرني", "هو فاكرني", "أنا مش آلة", "مش آلة",
    "مش كمبيوتر", "مش كول سنتر", "أصفار وآحاد", "قالب برمجي", "آلة عطلانة",
    "كتالوجات الصيانة", "إيه الهبل ده هو مفكرني"
]

SYCOPHANTIC_BANNED_PHRASES = [
    "من عيوني يا غالي", "من عيوني يا باشا", "من عيوني الاتنين",
    "أقدر أساعدك بإيه", "اقدر اساعدك بايه", "أقدر أساعدك ازاي", "كيف يمكنني مساعدتك",
    "تحت أمرك يا باشا", "تحت امرك يا باشا", "أنا تحت أمرك", "انا تحت امرك",
    "أهلاً بيك في بايثون", "اهلا بيك في بايثون",
    "ربنا يهديك أنا مش هنزل لمستواك", "ربنا يهديك انا مش هنزل لمستواك",
    "وأنا أرقى بكتير من إني أنزل لمستوى زي ده", "أنا أرقى من كده", "مش هنزل لمستواك",
    "أؤمرني يا غالي", "اؤمرني يا غالي", "أوامرك على راسي",
]


def sanitize_and_validate_reply(text: Optional[str]) -> str:
    """
    Validates conversational text, stripping existential robotic crisis rants
    and customer-service sycophantic clichés if present.
    """
    if not text or not isinstance(text, str):
        return ""
    clean = text.strip()
    for trig in ROBOTIC_RANT_TRIGGERS:
        if trig in clean:
            logger.warning(f"Sanitizer: Detected robotic crisis trigger '{trig}' in response. Stripping phrase.")
            clean = clean.replace(trig, "").strip()
    for syc in SYCOPHANTIC_BANNED_PHRASES:
        if syc in clean:
            logger.info(f"Sanitizer: Stripped banned sycophantic cliché '{syc}' from reply.")
            clean = clean.replace(syc, "").strip()
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    return clean


DEAD_MODELS: set[str] = {"gemini-2.5-flash", "gemini-2.5-flash-lite"}


class GeminiKeyPoolManager:
    """
    Intelligent Governor managing multi-key pool for Gemini model inference.
    Executes resilient REST-based generation with least-loaded key selection,
    sliding-window RPM smoothing, and multi-model cascading.
    Supports priority key reservation for live voice calls.
    """
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # Priority cascade of verified fast & high-quota models (no 404 models)
    MODEL_CASCADE: List[str] = [
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
    ]

    def __init__(self, keys: Optional[List[str]] = None, max_rpm_per_key: int = 12):
        raw_keys = keys if keys is not None else settings.gemini_keys_list
        self.trackers: List[KeyHealthTracker] = [
            KeyHealthTracker(key=k, index=idx) for idx, k in enumerate(raw_keys)
        ]
        self.max_rpm_per_key: int = max_rpm_per_key
        self._lock = asyncio.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None
        # Reserve last 2-3 keys for live VoIP calls so group chats cannot starve calls
        self.reserved_call_keys_count: int = min(3, max(1, len(self.trackers) // 4)) if len(self.trackers) >= 4 else 0
        logger.info(
            f"Initialized GeminiKeyPoolManager with {len(self.trackers)} keys. "
            f"Reserved {self.reserved_call_keys_count} keys for live voice calls. "
            f"Max pool capacity: {len(self.trackers) * max_rpm_per_key} RPM safe limit."
        )

    async def _get_client(self, timeout: float = 12.0) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(timeout, connect=3.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._http_client

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _select_best_tracker(self, is_call_priority: bool = False) -> KeyHealthTracker:
        """
        Picks the healthiest, least-loaded key using sliding-window RPM load balancing.
        Task B3.b: In call mode, prioritizes reserved keys and skips cooldown keys instantly without sleeping.
        """
        async with self._lock:
            active_trackers = [t for t in self.trackers if t.is_active]
            if not active_trackers:
                raise RuntimeError("No active Gemini API keys available in the pool.")

            now = time.time()

            if is_call_priority and self.reserved_call_keys_count > 0:
                # Prioritize dedicated call pool
                pool = active_trackers[-self.reserved_call_keys_count:]
                available = [t for t in pool if t.is_available(self.max_rpm_per_key)]
                if available:
                    best = min(available, key=lambda t: (t.get_current_rpm(now), t.last_used_timestamp))
                    best.record_attempt()
                    return best
                # Fallback to general pool for calls immediately without waiting
                general_available = [t for t in active_trackers if t.is_available(self.max_rpm_per_key)]
                if general_available:
                    best = min(general_available, key=lambda t: (t.get_current_rpm(now), t.last_used_timestamp))
                    best.record_attempt()
                    return best
                # If all busy, pick the one with earliest cooldown and proceed without sleeping
                best = min(active_trackers, key=lambda t: t.cool_down_until)
                best.record_attempt()
                return best

            # Normal (non-call) traffic: use unreserved keys to protect call capacity
            normal_pool = active_trackers[:-self.reserved_call_keys_count] if self.reserved_call_keys_count > 0 else active_trackers
            available = [t for t in normal_pool if t.is_available(self.max_rpm_per_key)]

            if available:
                best = min(available, key=lambda t: (t.get_current_rpm(now), t.last_used_timestamp))
                best.record_attempt()
                return best

            # If normal keys are cooling down, wait briefly for soonest unreserved tracker
            soonest_tracker = min(normal_pool, key=lambda t: t.seconds_until_available(self.max_rpm_per_key))
            wait_time = soonest_tracker.seconds_until_available(self.max_rpm_per_key)
            wait_time = min(max(wait_time, 0.05), 0.5)

            await asyncio.sleep(wait_time)
            soonest_tracker.record_attempt()
            return soonest_tracker

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 12,
        media_parts: Optional[List[Dict[str, Any]]] = None,
        response_mime_type: Optional[str] = None,
        is_call_priority: bool = False,
    ) -> str:
        """
        Sends prompt to Gemini with least-loaded key selection and multi-model cascade failover.
        Supports multimodal parts (audio/images) via media_parts and response_mime_type.
        Task B3.b & B4: High-speed call-mode support with 6s timeout, max 2 attempts, and 10s budget cap.
        """
        requested_model = model_name or settings.gemini_default_model
        if requested_model in DEAD_MODELS:
            requested_model = "gemini-flash-lite-latest"
        current_model = requested_model

        temp = temperature if temperature is not None else settings.gemini_temperature
        tokens = max_tokens or settings.gemini_max_output_tokens

        # Call-mode specific optimizations
        effective_retries = 2 if is_call_priority else max_retries
        call_timeout = 6.0 if is_call_priority else 12.0
        client = await self._get_client(timeout=call_timeout)
        start_time = time.time()

        parts: List[Dict[str, Any]] = []
        if media_parts:
            parts.extend(media_parts)
        parts.append({"text": prompt})

        generation_config: Dict[str, Any] = {
            "temperature": temp,
            "maxOutputTokens": tokens
        }
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "generationConfig": generation_config
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        last_exception: Optional[Exception] = None
        model_cascade_idx: int = 0

        for attempt in range(effective_retries):
            # Task B4: Cap total retry time for call requests at 10.0s
            if is_call_priority and (time.time() - start_time) > 10.0:
                logger.warning("Call-mode LLM request exceeded 10.0s time budget. Returning short in-character fallback.")
                return "سامعك وفاهمك يا غالي، كمل أنا معاك ومتابعك."

            tracker = await self._select_best_tracker(is_call_priority=is_call_priority)
            url = f"{self.BASE_URL}/{current_model}:generateContent?key={tracker.key}"

            try:
                response = await client.post(url, json=payload, timeout=call_timeout)

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        res_parts = candidates[0]["content"].get("parts", [])
                        text_response = "".join(part.get("text", "") for part in res_parts)
                        tracker.mark_success()
                        return text_response
                    else:
                        tracker.mark_success()
                        return ""

                elif response.status_code == 429:
                    # Task B4: True quota rate limit: distinct 20s cooldown
                    cooldown = 20.0 + (attempt * 2.0)
                    tracker.mark_rate_limited(cool_off_seconds=cooldown)
                    model_cascade_idx = (model_cascade_idx + 1) % len(self.MODEL_CASCADE)
                    current_model = self.MODEL_CASCADE[model_cascade_idx]
                    logger.warning(
                        f"Key [{tracker.index}] hit quota rate limit (429). Cooldown: {cooldown:.1f}s. "
                        f"Instant failover to model: {current_model}."
                    )
                    if not is_call_priority:
                        await asyncio.sleep(0.01)

                elif response.status_code in (500, 503):
                    # Task B4: Transient Google server overload (503): short 1.5s cooldown (never label as 429)
                    tracker.mark_rate_limited(cool_off_seconds=1.5)
                    model_cascade_idx = (model_cascade_idx + 1) % len(self.MODEL_CASCADE)
                    current_model = self.MODEL_CASCADE[model_cascade_idx]
                    logger.warning(
                        f"Key [{tracker.index}] hit transient server overload ({response.status_code}). "
                        f"Short cooldown 1.5s. Failover to model {current_model}."
                    )
                    if not is_call_priority:
                        await asyncio.sleep(0.01)

                elif response.status_code == 404:
                    # Task B4: Cache models returning 404 as dead for process lifetime
                    DEAD_MODELS.add(current_model)
                    logger.warning(f"Model {current_model} returned 404. Cached as DEAD for process lifetime.")
                    current_model = "gemini-flash-lite-latest"

                elif response.status_code in (400, 403):
                    resp_text = response.text
                    if "API_KEY_INVALID" in resp_text or "PERMISSION_DENIED" in resp_text:
                        tracker.mark_fatal_error()
                    else:
                        logger.error(f"Gemini client error {response.status_code}: {resp_text[:120]}")
                        tracker.mark_rate_limited(cool_off_seconds=10.0)

                else:
                    logger.warning(f"Unexpected status {response.status_code}: {response.text[:120]}")
                    tracker.mark_rate_limited(cool_off_seconds=5.0)

            except httpx.RequestError as exc:
                logger.error(f"HTTP request error with key [{tracker.index}]: {exc}")
                tracker.mark_rate_limited(cool_off_seconds=5.0)
                last_exception = exc
                if not is_call_priority:
                    await asyncio.sleep(0.05)

        if is_call_priority:
            logger.warning("Call-mode LLM attempts exhausted. Returning short in-character fallback.")
            return "سامعك وفاهمك يا غالي، كمل أنا معاك ومتابعك."

        error_msg = f"Failed to generate content after {max_retries} attempts across Gemini key pool."
        logger.critical(error_msg)
        raise RuntimeError(error_msg) from last_exception
        logger.critical(error_msg)
        raise RuntimeError(error_msg) from last_exception

    # Backwards-compatible alias for text generation
    generate_text = generate_content

    async def generate_content_with_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        prompt: str = "اسمع هذا المقطع الصوتي بدقة واكتب النص المنطوق بالكامل بنفس اللهجة بدون تلخيص.",
        system_instruction: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> str:
        """
        Sends audio data directly to Gemini Multimodal API via base64 inline_data.
        """
        import base64
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        media_parts = [
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_audio,
                }
            }
        ]
        return await self.generate_content(
            prompt=prompt,
            system_instruction=system_instruction,
            model_name=model_name or "gemini-flash-lite-latest",
            media_parts=media_parts,
            temperature=0.2,
        )

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Prompts Gemini and strictly extracts a valid JSON structure from response.
        Uses multiline regex recovery and raw conversational extraction if JSONDecodeError occurs.
        Guarantees ZERO canned fallback garbage (never returns 'معاك يا غالي' or 'سامعك ومصحصح').
        """
        augmented_prompt = (
            f"{prompt}\n\nIMPORTANT: Respond with pure, valid JSON only. Do not wrap in markdown or backticks."
        )
        raw_text = await self.generate_content(
            prompt=augmented_prompt,
            system_instruction=system_instruction,
            model_name=model_name,
            temperature=temperature or 0.2,
            max_tokens=2048,
            response_mime_type="application/json",
        )

        cleaned = (raw_text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Strategy 1: Direct JSON parsing
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                if "reply_text" in parsed and parsed["reply_text"]:
                    parsed["reply_text"] = sanitize_and_validate_reply(parsed["reply_text"])
                if "internal_thought_raw" in parsed and parsed["internal_thought_raw"]:
                    parsed["internal_thought_raw"] = sanitize_and_validate_reply(parsed["internal_thought_raw"])
                return parsed
        except json.JSONDecodeError:
            pass

        # Strategy 2: Slice JSON braces if surrounded by conversational chatter
        start_brace = cleaned.find("{")
        end_brace = cleaned.rfind("}")
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            try:
                parsed = json.loads(cleaned[start_brace : end_brace + 1])
                if isinstance(parsed, dict):
                    if "reply_text" in parsed and parsed["reply_text"]:
                        parsed["reply_text"] = sanitize_and_validate_reply(parsed["reply_text"])
                    if "internal_thought_raw" in parsed and parsed["internal_thought_raw"]:
                        parsed["internal_thought_raw"] = sanitize_and_validate_reply(parsed["internal_thought_raw"])
                    return parsed
            except Exception:
                pass

        # Strategy 3: Robust Multi-Line Regex Extraction (Handles unescaped quotes & python code blocks)
        logger.warning("JSONDecodeError encountered. Attempting robust multi-line regex extraction.")
        reply_val = None
        # Match up to next JSON key or closing brace, preserving complete code blocks
        match = re.search(r'"(?:reply_text|reply|response)"\s*:\s*"(.*?)"(?=\s*,\s*"(?:decision|reaction|emotional_reaction|internal_thought_raw|should_report_to_partner)"|\s*\})', cleaned, re.DOTALL)
        if match:
            raw_val = match.group(1)
            reply_val = raw_val.replace('\\"', '"').replace('\\n', '\n')
        else:
            match2 = re.search(r'"(?:reply_text|reply|response)"\s*:\s*"((?:\\.|[^"\\])*)"', cleaned, re.DOTALL)
            if match2:
                raw_val = match2.group(1)
                try:
                    reply_val = json.loads(f'"{raw_val}"')
                except Exception:
                    reply_val = raw_val.replace('\\"', '"').replace('\\n', '\n')
        
        thought_val = "هرد بشكل هادئ وسالك."
        t_match = re.search(r'"(?:internal_thought_raw|thought)"\s*:\s*"((?:\\.|[^"\\])*)"', cleaned, re.DOTALL)
        if t_match:
            try:
                thought_val = json.loads(f'"{t_match.group(1)}"')
            except Exception:
                thought_val = t_match.group(1).replace('\\"', '"').replace('\\n', '\n')

        d_match = re.search(r'"decision"\s*:\s*"([A-Za-z_]+)"', cleaned)
        decision_val = d_match.group(1) if d_match else "REPLY"

        b_match = re.search(r'"should_report_to_partner"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
        report_val = b_match.group(1).lower() == "true" if b_match else False

        if reply_val and len(reply_val.strip()) > 1:
            clean_reply = sanitize_and_validate_reply(reply_val)
            return {
                "decision": decision_val,
                "reply_text": clean_reply,
                "emotional_reaction": "طبيعي",
                "internal_thought_raw": thought_val,
                "should_report_to_partner": report_val,
            }

        # Strategy 4: Direct Raw Speech Extraction (When Gemini outputs conversational reply or code directly)
        if cleaned and len(cleaned) > 2:
            raw_speech = cleaned
            if raw_speech.startswith("```"):
                raw_speech = re.sub(r"^```[a-zA-Z]*\n?", "", raw_speech)
            if raw_speech.endswith("```"):
                raw_speech = re.sub(r"\n?```$", "", raw_speech)
            raw_speech = re.sub(r'^(?:\{\s*)?["\']?(?:reply_text|reply|response|internal_thought_raw)["\']?\s*:\s*["\']?', '', raw_speech)
            raw_speech = re.sub(r'["\']?\s*\}?$', '', raw_speech).strip()

            if len(raw_speech) > 2 and not (raw_speech.startswith("{") and raw_speech.endswith("}")):
                logger.info(f"LLMRouter: Utilizing directly recovered raw conversational text ({len(raw_speech)} chars).")
                return {
                    "decision": "REPLY",
                    "reply_text": raw_speech,
                    "emotional_reaction": "طبيعي",
                    "internal_thought_raw": "هرد بشكل هادئ ومباشر.",
                    "should_report_to_partner": False,
                }

        # Strategy 5: Pure Silence over Canned Lies (Never output fake canned phrases)
        logger.warning("LLMRouter: Model returned empty or unrecoverable output. Returning empty reply without canned phrases.")
        return {
            "decision": "REPLY",
            "reply_text": None,
            "emotional_reaction": "طبيعي",
            "internal_thought_raw": "لا يوجد رد متاح.",
            "should_report_to_partner": False,
        }


# Global singleton instance of GeminiKeyPoolManager
llm_pool = GeminiKeyPoolManager()
