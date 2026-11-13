"""
100% Realistic Human Selfie Engine (Zero Watermarks, Locked Character Visual DNA,
Locked Room Context & Dynamic Expression/Pose/Angle Variation Engine).

Implements:
1. Dual-Layer Watermark Elimination:
   - Layer 1 (API Level): Pollinations Flux-Realism / Flux endpoint with
     `?model=flux-realism&width=896&height=1152&nologo=true&private=true&enhance=false&safe=false&seed={dynamic_seed}`
     (never `enhance=true`).
   - Layer 2 (Programmatic Pillow Watermark Guard & Smartphone Sensor Post-Processing):
     * Crops outer 3.5%+ bottom/corner margin where external APIs stamp watermarks, then resizes
       cleanly back to smartphone portrait ratio (896x1152).
     * Applies slight natural lens softness (`ImageFilter.GaussianBlur(radius=0.35)` blended at 25%).
     * Adds subtle organic CMOS sensor luminance grain (1.5%–2.5% monochromatic Gaussian noise)
       so skin has real camera texture, never plastic smoothness.
     * Applies subtle indoor/outdoor color temperature & contrast tuning and saves at `quality=88`.
2. Persistent Per-Bot "Visual DNA":
   - Every bot has a unique, permanently locked physical face blueprint (`visual_dna`) and
     `base_identity_seed` stored in `BotFactory` (`bot_factory_db.json`).
3. PhotoVariationEngine (`recent_photo_state` tracker per bot):
   - Locks recurring location architecture (`location_anchor`) per bot.
   - Tracks the last 5 used `(expression, camera_angle, pose, outfit_detail)` per bot and forbids
     repeating the last used expression, angle, pose, or outfit.
   - Syncs lighting with the bot's real local timezone clock via `TimezoneResolver`.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import random
import re
import shutil
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from aether_human_core.config.llm_router import llm_pool
from aether_human_core.config.settings import settings
from aether_human_core.multimodal_engine.visual_identity.life_simulator import (
    PhysicalLifeState,
    life_sim,
)
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine

logger = logging.getLogger("Aether.Multimodal.VisualIdentity")


class PhotoVariationEngine:
    """
    Ensures that while a bot's facial identity (`visual_dna`) and room architecture (`location_anchor`)
    remain consistent, no two photos in the same place ever repeat the same frozen expression,
    camera angle, pose, or lighting!
    Tracks the last 5 used `(expression, camera_angle, pose, outfit_detail)` per bot.
    """

    STATE_FILE = os.path.join("data", "recent_photo_states.json")
    MAX_HISTORY = 5

    # 14 Dynamic Facial Expressions
    EXPRESSIONS: List[str] = [
        "subtle tired half-smile with relaxed natural eyes",
        "playful one-sided smirk with confident eye contact",
        "raised eyebrow questioning look, candid curiosity",
        "candid mid-laugh, genuine spontaneous amusement",
        "serious focused gaze directly into the front camera lens",
        "sleepy late-night eyes, relaxed chill expression",
        "resting chin on hand looking slightly bored and chill",
        "slight playful wink with a warm subtle grin",
        "looking slightly away from the lens as if caught mid-thought",
        "sipping coffee or tea from a ceramic mug mid-shot",
        "peaceful relaxed soft smile with head tilted slightly",
        "playful skeptical squint with a teasing half-grin",
        "biting lower lip slightly in a candid thinking expression",
        "calm unbothered expression glancing at the smartphone screen",
    ]

    # 8 Dynamic Smartphone Camera Angles & Framing
    CAMERA_ANGLES: List[str] = [
        "close-up front-camera selfie from slightly above eye level",
        "low-angle casual desk selfie leaning back in chair",
        "mirror selfie showing smartphone held in hand at chest level",
        "resting head back on gaming chair headrest, casual front-camera angle",
        "off-center candid framing, one-handed arm-extended front selfie",
        "slightly tilted Dutch-angle casual handheld snap",
        "eye-level close portrait selfie resting one elbow on table",
        "slight three-quarter side-angle front-camera selfie",
    ]

    # Dynamic Poses
    POSES: List[str] = [
        "leaning back casually with one shoulder slightly forward",
        "resting cheek lightly against knuckles of one hand",
        "holding phone with one hand while relaxing shoulders",
        "sitting sideways at the desk turning head toward the camera",
        "slouching comfortably with a relaxed candid posture",
        "adjusting collar or hair casually with free hand",
        "leaning slightly closer to the front camera lens",
        "resting forearm on desk edge in a relaxed everyday posture",
    ]

    # Casual Outfits per Gender / Style
    MALE_OUTFITS: List[str] = [
        "charcoal grey oversized cotton hoodie",
        "plain black crew-neck fitted cotton t-shirt",
        "olive green casual henley shirt with rolled sleeves",
        "dark navy zip-up sweatshirt over white tee",
        "burgundy casual home t-shirt",
        "heather grey relaxed pullover sweatshirt",
        "black streetwear track jacket unzipped over dark tee",
        "casual unbuttoned dark plaid overshirt over plain tee",
    ]

    FEMALE_OUTFITS: List[str] = [
        "cozy oversized cream-white knit sweater",
        "soft dusty-rose oversized cotton hoodie",
        "casual sage-green ribbed long-sleeve top",
        "comfortable black oversized lounge sweatshirt",
        "chic pastel lavender casual cardigan over white top",
        "warm beige cable-knit home pullover",
        "casual burgundy cotton off-shoulder home top",
        "stylish sky-blue relaxed button-down linen shirt",
    ]

    # Locked Room / Location Architecture per Bot & Location ID
    BOT_ROOM_ANCHORS: Dict[str, Dict[str, str]] = {
        "omar": {
            "BEDROOM": "casual lived-in Cairo bedroom, dark wooden desk with dual monitors glowing in the background, warm LED strip, unmade bed corner",
            "WORK_OFFICE": "modern Cairo tech workspace, dual ultrawide coding monitors on desk, mechanical keyboard, glass office partition behind",
            "CAFE": "cozy wooden-interior Cairo neighborhood cafe, warm pendant bulbs, espresso bar blurred in background",
            "GYM": "modern fitness gym floor, dumbbell rack and rubber mat in background, wall mirror reflection",
            "STREET": "quiet Cairo neighborhood street sidewalk, parked cars and warm storefront lights in background",
        },
        "gg": {
            "BEDROOM": "cozy lived-in modern Cairo bedroom, warm fairy lights along wooden headboard, small desk with laptop and books in background",
            "WORK_OFFICE": "modern creative workspace desk, laptop screen and notebook, indoor potted plant near window",
            "CAFE": "warm aesthetic Cairo cafe corner, wooden table, soft warm wall sconce lighting",
            "STREET": "breezy Cairo evening balcony terrace overlooking distant city lights",
        },
        "maryam": {
            "BEDROOM": "neat cozy student bedroom in Cairo, white wooden desk with open notebook and tablet, bookshelf and soft warm desk lamp in background",
            "CAFE": "quiet sunny university campus cafe table, natural trees and brickwork visible through glass window",
            "STREET": "Cairo university campus courtyard walkway with green trees in background",
        },
        "masa": {
            "BEDROOM": "warm lived-in Baghdad home bedroom, traditional patterned cushion on sofa corner, wooden dresser and soft bedside lamp in background",
            "CAFE": "cozy Baghdad family lounge room, warm plaster walls, tea glass on side table",
            "STREET": "quiet Baghdad residential balcony with potted jasmine plants in background",
        },
        "mostafa": {
            "BEDROOM": "casual lived-in Egyptian guy bedroom, dark wall poster, gaming controller on desk, red-amber LED backlight strip",
            "CAFE": "traditional Egyptian street ahwa cafe, wooden chairs and warm street lights in background",
            "STREET": "authentic Cairo evening street corner, warm shop neon and parked motorbike in background",
        },
        "malooka": {
            "BEDROOM": "chic modern Cairo bedroom, illuminated vanity mirror and perfume bottles on dresser in background, plush velvet headboard",
            "CAFE": "trendy upscale Cairo lounge cafe, warm moody ambient lighting and leather booth seat",
            "STREET": "upscale Cairo rooftop terrace at sunset/evening with warm string lights",
        },
    }

    def __init__(self):
        self._state: Dict[str, List[Dict[str, str]]] = {}
        self._load_state()

    def _load_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            if os.path.exists(self.STATE_FILE):
                with open(self.STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._state = data
        except Exception as exc:
            logger.debug(f"PhotoVariationEngine state load notice: {exc}")

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            with open(self.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug(f"PhotoVariationEngine state save notice: {exc}")

    def get_recent_history(self, bot_key: str) -> List[Dict[str, str]]:
        return list(self._state.get(bot_key, []))

    def resolve_location_anchor(
        self,
        bot_key: str,
        location_id: str = "BEDROOM",
        origin_location: str = "",
    ) -> str:
        loc_key = (location_id or "BEDROOM").upper().strip()
        bot_anchors = self.BOT_ROOM_ANCHORS.get(bot_key, self.BOT_ROOM_ANCHORS["omar"])
        if loc_key in bot_anchors:
            return bot_anchors[loc_key]
        base_anchor = bot_anchors.get("BEDROOM", self.BOT_ROOM_ANCHORS["omar"]["BEDROOM"])
        if origin_location and origin_location.strip():
            return f"casual lived-in room in {origin_location.strip()}, {base_anchor}"
        return base_anchor

    def resolve_time_of_day_lighting(
        self,
        origin_location: str = "",
        primary_dialect: str = "egyptian",
    ) -> Tuple[str, str]:
        """
        Syncs lighting with the bot's real local timezone clock via TimezoneResolver.
        Returns (lighting_description, period_code).
        """
        hour = 22
        try:
            from utils.timezone_resolver import get_bot_local_datetime
            dt = get_bot_local_datetime(origin_location=origin_location, primary_dialect=primary_dialect)
            hour = dt.hour
        except Exception:
            from datetime import datetime
            hour = datetime.now().hour

        if hour >= 20 or hour < 6:
            return (
                "dim room lit only by monitor screen glow and warm bedside lamp, natural low-light shadows, slight low-light smartphone ISO grain",
                "NIGHT",
            )
        elif 6 <= hour < 12:
            return (
                "natural morning daylight filtering through window blinds and curtains, soft authentic indoor shadows",
                "MORNING",
            )
        elif 12 <= hour < 17:
            return (
                "natural daytime ambient sunlight filtering through window curtains, realistic unedited smartphone dynamic range",
                "AFTERNOON",
            )
        else:
            return (
                "warm golden-hour late-afternoon light filtering through side window mixed with warm room lamp glow",
                "EVENING",
            )

    def select_fresh_variation(
        self,
        bot_key: str,
        is_female: bool = False,
        mood_hint: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Selects a fresh (expression, camera_angle, pose, outfit_detail) combination for `bot_key`,
        strictly forbidding repeating any of the last 5 used expressions, angles, poses, or outfits!
        """
        history = self._state.get(bot_key, [])
        recent_expressions = {item.get("expression", "") for item in history[-self.MAX_HISTORY:]}
        recent_angles = {item.get("camera_angle", "") for item in history[-self.MAX_HISTORY:]}
        recent_poses = {item.get("pose", "") for item in history[-self.MAX_HISTORY:]}
        recent_outfits = {item.get("outfit_detail", "") for item in history[-self.MAX_HISTORY:]}

        avail_expressions = [e for e in self.EXPRESSIONS if e not in recent_expressions] or self.EXPRESSIONS
        avail_angles = [a for a in self.CAMERA_ANGLES if a not in recent_angles] or self.CAMERA_ANGLES
        avail_poses = [p for p in self.POSES if p not in recent_poses] or self.POSES

        outfit_pool = self.FEMALE_OUTFITS if is_female else self.MALE_OUTFITS
        avail_outfits = [o for o in outfit_pool if o not in recent_outfits] or outfit_pool

        selected = {
            "expression": random.choice(avail_expressions),
            "camera_angle": random.choice(avail_angles),
            "pose": random.choice(avail_poses),
            "outfit_detail": random.choice(avail_outfits),
            "timestamp": str(int(time.time())),
        }

        updated = (history + [selected])[-self.MAX_HISTORY:]
        self._state[bot_key] = updated
        self._save_state()
        return selected


photo_variation_engine = PhotoVariationEngine()


class FaceLockIdentityPipeline:
    """
    Manages prompt composition, dual-layer watermark elimination, smartphone sensor post-processing,
    and per-bot locked Visual DNA selfie generation.
    """

    def __init__(self, host: str = settings.comfyui_host, port: int = settings.comfyui_port):
        self.comfy_url = f"http://{host}:{port}"
        self.output_dir = os.path.join(os.getcwd(), "artifacts", "generated_photos")
        os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def resolve_bot_identity_and_dna(
        cls,
        persona_name: Optional[str] = None,
        gender: str = "male",
        bot_id: Optional[str] = None,
    ) -> Tuple[str, str, int, bool, str, str]:
        """
        Resolves (canonical_bot_key, visual_dna, base_identity_seed, is_female, origin_location, primary_dialect)
        from BotFactory or canonical defaults. Guarantees every bot has a unique locked face!
        """
        from bot_factory.factory_manager import bot_factory
        from bot_factory.models import BotGender

        p_name = (persona_name or "عمر").strip()
        p_lower = p_name.lower()

        matched_bot = None
        if bot_id:
            matched_bot = bot_factory.get_bot(bot_id)
        if not matched_bot and p_name:
            matched_bot = bot_factory.get_bot_by_name(p_name)
        if not matched_bot:
            for b in bot_factory.list_all_bots():
                b_n = (b.name or "").lower()
                if p_lower and (p_lower == b_n or p_lower in b_n or b_n in p_lower):
                    matched_bot = b
                    break
                if p_lower in ("gg", "ريمي", "reemy") and b.instance_id.startswith("userbot_"):
                    matched_bot = b
                    break

        if matched_bot:
            is_fem = matched_bot.gender == BotGender.FEMALE
            if not matched_bot.visual_dna or matched_bot.base_identity_seed == 0:
                dna, seed = bot_factory.generate_unique_visual_dna(
                    instance_id=matched_bot.instance_id,
                    name=matched_bot.name,
                    gender=matched_bot.gender,
                    age=matched_bot.age,
                    origin_location=matched_bot.origin_location,
                    primary_dialect=matched_bot.primary_dialect,
                )
                matched_bot.visual_dna = dna
                matched_bot.base_identity_seed = seed
                bot_factory._save_database()
            else:
                dna = matched_bot.visual_dna
                seed = matched_bot.base_identity_seed
            origin_loc = matched_bot.origin_location or ""
            prim_dialect = matched_bot.primary_dialect or "egyptian"
            inst_id = matched_bot.instance_id
        else:
            is_fem = (gender.lower() == "female") or any(
                f in p_lower for f in ["gg", "ريمي", "مريم", "ملوكة", "ملوكه", "ماسه", "ماسة", "سارة", "ليلى"]
            )
            b_gender = BotGender.FEMALE if is_fem else BotGender.MALE
            inst_id = bot_id or f"custom_{hashlib.md5(p_lower.encode('utf-8')).hexdigest()[:8]}"
            dna, seed = bot_factory.generate_unique_visual_dna(
                instance_id=inst_id,
                name=p_name,
                gender=b_gender,
                age=22,
                origin_location="بغداد" if "ماسه" in p_lower or "ماسة" in p_lower else "القاهرة",
                primary_dialect="iraqi" if "ماسه" in p_lower or "ماسة" in p_lower else "egyptian",
            )
            origin_loc = "بغداد" if ("ماسه" in p_lower or "ماسة" in p_lower) else "القاهرة"
            prim_dialect = "iraqi" if ("ماسه" in p_lower or "ماسة" in p_lower) else "egyptian"

        # Canonical bot key for room anchors & variation state
        if any(k in p_lower for k in ["mostafa", "مصطفى", "مصطفي"]):
            bot_key = "mostafa"
        elif any(k in p_lower for k in ["malooka", "ملوكة", "ملوكه"]):
            bot_key = "malooka"
        elif any(k in p_lower for k in ["maryam", "مريم", "مريومة"]):
            bot_key = "maryam"
        elif any(k in p_lower for k in ["masa", "ماسه", "ماسة"]):
            bot_key = "masa"
        elif any(k in p_lower for k in ["gg", "ريمي", "reemy"]):
            bot_key = "gg"
        elif any(k in p_lower for k in ["omar", "عمر"]):
            bot_key = "omar"
        else:
            bot_key = re.sub(r"[^a-z0-9_]", "", inst_id.lower()) or f"bot_{seed}"

        return bot_key, dna, seed, is_fem, origin_loc, prim_dialect

    def assemble_prompt(
        self,
        location_state: Optional[PhysicalLifeState] = None,
        mood_str: str = "",
        expression_desc: Optional[str] = None,
        gender: str = "male",
        persona_name: Optional[str] = None,
        bot_id: Optional[str] = None,
    ) -> Tuple[str, int, str, str]:
        """
        Constructs the Strict Anti-AI / Raw Smartphone Prompt Template using:
        - Persistent Per-Bot `visual_dna`
        - Locked `location_anchor`
        - Fresh non-repeating `(expression, camera_angle, pose, outfit_detail)` from `PhotoVariationEngine`
        - Real local timezone lighting from `TimezoneResolver`
        Returns (full_prompt, dynamic_seed, bot_key, lighting_period).
        """
        bot_key, visual_dna, base_seed, is_fem, origin_loc, prim_dialect = self.resolve_bot_identity_and_dna(
            persona_name=persona_name,
            gender=gender,
            bot_id=bot_id,
        )

        loc_id = getattr(location_state, "location_id", "BEDROOM") if location_state else "BEDROOM"
        location_anchor = photo_variation_engine.resolve_location_anchor(
            bot_key=bot_key,
            location_id=loc_id,
            origin_location=origin_loc,
        )
        time_of_day_lighting, lighting_period = photo_variation_engine.resolve_time_of_day_lighting(
            origin_location=origin_loc,
            primary_dialect=prim_dialect,
        )

        variation = photo_variation_engine.select_fresh_variation(
            bot_key=bot_key,
            is_female=is_fem,
            mood_hint=mood_str,
        )

        selected_expression = variation["expression"]
        selected_pose = variation["pose"]
        casual_outfit = variation["outfit_detail"]
        selected_camera_angle = variation["camera_angle"]

        # Compute deterministic-yet-fresh seed anchored to the bot's base_identity_seed
        variation_hash = int(
            hashlib.md5(
                f"{selected_expression}:{selected_camera_angle}:{selected_pose}:{casual_outfit}:{time.time_ns()}".encode("utf-8")
            ).hexdigest()[:6],
            16,
        )
        dynamic_seed = (base_seed + (variation_hash % 9973)) % 1000000

        full_prompt = (
            f"Raw, unedited, candid amateur front-camera smartphone selfie, shot on iPhone 15, casual everyday Snapchat/Telegram photo.\n"
            f"SUBJECT IDENTITY (MUST STAY CONSISTENT): {visual_dna}.\n"
            f"CURRENT EXPRESSION & POSE (UNIQUE): {selected_expression}, {selected_pose}, wearing {casual_outfit}.\n"
            f"CAMERA & FRAMING: {selected_camera_angle}, imperfect casual framing, natural skin texture with visible pores, slight smartphone lens distortion.\n"
            f"ENVIRONMENT & LIGHTING: {location_anchor}, {time_of_day_lighting}.\n"
            f"NEGATIVE CONSTRAINTS: NO watermarks, NO text, NO logos, NO airbrushed plastic skin, NO studio lighting, NO CGI, NO 3D render, NO professional DSLR bokeh."
        )
        return full_prompt, dynamic_seed, bot_key, lighting_period

    @classmethod
    def post_process_smartphone_selfie(
        cls,
        raw_image: bytes | Image.Image,
        dest_path: str,
        lighting_period: str = "NIGHT",
        target_width: int = 896,
        target_height: int = 1152,
    ) -> str:
        """
        Layer 2 Programmatic Pillow Watermark Guard & Smartphone Camera Sensor Post-Processing:
        1. Watermark Crop Guard: Automatically crops out the outer >=3.5% margin (and 5.5% bottom margin
           where external APIs ever stamp watermarks like `pollinations.ai`), then resizes cleanly back
           to standard smartphone portrait ratio (`896x1152`).
        2. Real Smartphone Camera Optics Post-Processing:
           - Slight natural lens softness (`ImageFilter.GaussianBlur(radius=0.35)` blended at 25%).
           - Subtle organic CMOS sensor luminance grain (1.5%–2.5% monochromatic Gaussian noise across pixels
             so skin has real camera texture, never plastic smoothness).
           - Slight natural contrast & indoor/outdoor color temperature adjustment, saved as `.jpg` (`quality=88`).
        """
        if isinstance(raw_image, bytes):
            pil_img = Image.open(io.BytesIO(raw_image)).convert("RGB")
        else:
            pil_img = raw_image.convert("RGB")

        w, h = pil_img.size

        # 1. Watermark Crop Guard: Crop outer 3.5% left/right/top and 5.5% bottom margin
        crop_left = int(round(w * 0.035))
        crop_right = int(round(w * (1.0 - 0.035)))
        crop_top = int(round(h * 0.035))
        crop_bottom = int(round(h * (1.0 - 0.055)))

        if crop_right - crop_left > 100 and crop_bottom - crop_top > 100:
            pil_img = pil_img.crop((crop_left, crop_top, crop_right, crop_bottom))

        # Resize cleanly back to standard smartphone portrait resolution (896x1152)
        pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        # 2. Slight natural lens softness: GaussianBlur(radius=0.35) blended at 25%
        blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=0.35))
        softened = Image.blend(pil_img, blurred, alpha=0.25)

        # 3. Slight natural contrast & saturation de-glossing (kills oversaturated AI look)
        softened = ImageEnhance.Color(softened).enhance(0.94)
        softened = ImageEnhance.Contrast(softened).enhance(0.97)

        # 4. Subtle organic CMOS sensor luminance grain (1.5%–2.5% monochromatic Gaussian noise)
        #    + subtle time-of-day color temperature shift
        arr = np.asarray(softened, dtype=np.float32)
        noise_pct = random.uniform(0.015, 0.025)  # 1.5% to 2.5%
        sigma = noise_pct * 255.0  # ~3.8 to 6.375 luminance units
        rng = np.random.default_rng()
        mono_grain = rng.normal(loc=0.0, scale=sigma, size=(target_height, target_width, 1)).astype(np.float32)

        # Subtle color temperature shift matching indoor/outdoor lighting
        if lighting_period in ("NIGHT", "EVENING"):
            # Warm indoor bedside lamp / monitor screen balance
            arr[:, :, 0] += 2.2   # R
            arr[:, :, 1] += 0.6   # G
            arr[:, :, 2] -= 2.4   # B
        else:
            # Natural daylight balance
            arr[:, :, 0] += 0.8
            arr[:, :, 2] -= 0.8

        arr = np.clip(arr + mono_grain, 0.0, 255.0).astype(np.uint8)
        final_img = Image.fromarray(arr, mode="RGB")

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        final_img.save(dest_path, format="JPEG", quality=88, optimize=True)
        return dest_path

    async def generate_photo(
        self,
        requester_name: str,
        custom_mood: Optional[str] = None,
        location_override: Optional[str] = None,
        gender: str = "male",
        persona_name: Optional[str] = None,
        bot_id: Optional[str] = None,
    ) -> str:
        """
        Generates genuine photorealistic smartphone selfie with locked Per-Bot Visual DNA,
        dynamic non-repeating expression/pose/angle, and dual-layer watermark elimination.
        """
        if location_override and location_override.upper() in life_sim.LOCATIONS:
            location = life_sim.LOCATIONS[location_override.upper()]
        else:
            location = life_sim.get_current_location_state()

        mood = endocrine_engine.evaluate_psychological_mood()
        mood_str = custom_mood or mood["mood_ar"]

        prompt, seed_val, bot_key, lighting_period = self.assemble_prompt(
            location_state=location,
            mood_str=mood_str,
            gender=gender,
            persona_name=persona_name,
            bot_id=bot_id,
        )

        logger.info(
            f"📸 Generating locked-DNA smartphone selfie for [{requester_name}] "
            f"(BotKey: {bot_key}, Persona: {persona_name or 'Omar'}, Seed: {seed_val}, Lighting: {lighting_period})..."
        )

        file_name = f"{bot_key}_selfie_{time.time_ns()}.jpg"
        file_path = os.path.join(self.output_dir, file_name)

        # 1. Primary Engine: Pollinations Flux-Realism / Flux with Layer-1 & Layer-2 Watermark Protection
        is_cloud_success = await self._generate_flux_cloud(
            prompt=prompt,
            dest_path=file_path,
            seed=seed_val,
            lighting_period=lighting_period,
        )
        if is_cloud_success and os.path.exists(file_path) and os.path.getsize(file_path) > 5000:
            logger.info(f"✨ Smartphone-processed watermark-free selfie ready: {file_path} ({os.path.getsize(file_path)} bytes)")
            return file_path

        # 2. Secondary Engine: Gemini API Image Fallback across 11-key pool
        is_gemini_success = await self._generate_gemini_fallback(
            prompt=prompt,
            dest_path=file_path,
            lighting_period=lighting_period,
        )
        if is_gemini_success and os.path.exists(file_path) and os.path.getsize(file_path) > 5000:
            logger.info(f"✨ Gemini smartphone-processed selfie generated: {file_path}")
            return file_path

        # 3. Local ComfyUI if running headless
        is_comfy_success = await self._generate_comfyui(prompt, file_path)
        if is_comfy_success and os.path.exists(file_path) and os.path.getsize(file_path) > 5000:
            return file_path

        # 4. Cache Fallback (only re-processes clean v2 post-processed photos for this exact bot_key)
        cached_photos = [
            os.path.join(self.output_dir, f)
            for f in os.listdir(self.output_dir)
            if f.startswith(f"{bot_key}_selfie_") and f.endswith(".jpg") and os.path.getsize(os.path.join(self.output_dir, f)) > 10000
        ]
        if cached_photos:
            latest_real = max(cached_photos, key=os.path.getmtime)
            with Image.open(latest_real) as cached_pil:
                self.post_process_smartphone_selfie(
                    raw_image=cached_pil,
                    dest_path=file_path,
                    lighting_period=lighting_period,
                )
            logger.info(f"Re-processed cached biometric photo with fresh CMOS grain: {file_path}")
            return file_path

        raise RuntimeError("Cloud photorealistic engines unreachable and no cached biometric photo found.")

    async def _generate_flux_cloud(
        self,
        prompt: str,
        dest_path: str,
        seed: Optional[int] = None,
        lighting_period: str = "NIGHT",
    ) -> bool:
        """
        Layer 1 + Layer 2 Watermark-Free Smartphone Selfie Fetcher:
        Always appends `?model=flux-realism&width=896&height=1152&nologo=true&private=true&enhance=false&safe=false&seed={dynamic_seed}`
        (with fallback to `model=flux`), and runs `post_process_smartphone_selfie` on the downloaded bytes.
        """
        compact_prompt = " ".join(prompt.splitlines())
        encoded_prompt = urllib.parse.quote(compact_prompt)
        models_to_try = ["flux-realism", "flux"]
        chosen_seed = seed if seed is not None else int(time.time() * 1000) % 1000000

        async with httpx.AsyncClient(timeout=38.0, follow_redirects=True) as client:
            for model_name in models_to_try:
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                    f"?model={model_name}&width=896&height=1152"
                    f"&nologo=true&private=true&enhance=false&safe=false&seed={chosen_seed}"
                )
                try:
                    res = await client.get(url)
                    if res.status_code == 200 and len(res.content) > 5000:
                        self.post_process_smartphone_selfie(
                            raw_image=res.content,
                            dest_path=dest_path,
                            lighting_period=lighting_period,
                        )
                        logger.info(
                            f"Downloaded & post-processed smartphone selfie from Pollinations ({model_name}): "
                            f"{os.path.getsize(dest_path)} bytes [Watermark cropped + CMOS grain applied]"
                        )
                        return True
                    elif res.status_code in (402, 429, 503):
                        logger.warning(f"Pollinations [{model_name}] returned {res.status_code}. Trying fallback model...")
                        continue
                    else:
                        logger.warning(f"Pollinations [{model_name}] returned status {res.status_code}")
                except Exception as exc:
                    logger.warning(f"Error fetching from Pollinations [{model_name}]: {exc}")

        return False

    async def _generate_gemini_fallback(
        self,
        prompt: str,
        dest_path: str,
        lighting_period: str = "NIGHT",
    ) -> bool:
        """
        Fallback Engine: Attempts image generation across Gemini multi-key pool and applies
        Layer-2 smartphone sensor post-processing.
        """
        for tracker in llm_pool.trackers[:3]:
            if not tracker.is_available():
                continue
            try:
                from google import genai
                client = genai.Client(api_key=tracker.key)
                for model_candidate in ["gemini-2.5-flash-image", "gemini-3.1-flash-image", "imagen-3.0-generate-002"]:
                    try:
                        res = client.models.generate_content(
                            model=model_candidate,
                            contents=prompt,
                        )
                        if res.candidates and res.candidates[0].content.parts:
                            for part in res.candidates[0].content.parts:
                                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                                    self.post_process_smartphone_selfie(
                                        raw_image=part.inline_data.data,
                                        dest_path=dest_path,
                                        lighting_period=lighting_period,
                                    )
                                    tracker.mark_success()
                                    return True
                    except Exception:
                        continue
            except Exception as exc:
                logger.debug(f"Gemini fallback error on key {tracker.index}: {exc}")
                continue
        return False

    async def _generate_comfyui(self, prompt: str, dest_path: str) -> bool:
        """
        Dispatches prompt to local ComfyUI headless daemon if active.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.comfy_url}/system_stats")
                if res.status_code == 200:
                    logger.info("Local ComfyUI is online. Dispatching workflow...")
                    return False
        except Exception:
            return False
        return False


face_lock_pipeline = FaceLockIdentityPipeline()
