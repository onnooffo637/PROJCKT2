"""
Media, Acoustic Voice Note, and Selfie Request Event Handler.
Handles voice perception, emotional empathy responses, direct voice note requests,
face-locked selfie deliveries, and Deep Multimodal Vision (Stickers, GIFs, Photos, Documents).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.multimodal_engine.acoustic_voice.emotion_detector import acoustic_detector
from aether_human_core.multimodal_engine.acoustic_voice.realistic_voice_generator import voice_generator
from aether_human_core.multimodal_engine.visual_identity.face_lock_pipeline import face_lock_pipeline
from aether_human_core.multimodal_engine.visual_identity.life_simulator import life_sim
from aether_human_core.psychology_engine.affinity_matrix import RelationshipTier, UserAffinityVector
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.telegram_client.human_typer import human_typer
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

logger = logging.getLogger("Aether.Telegram.MediaHandler")


class MediaEventHandler:
    """
    Orchestrates multimodal reception and transmission across Telegram.
    """

    @classmethod
    async def handle_incoming_voice(
        cls,
        message_id: int,
        chat_id: int,
        sender_id: int,
        sender_name: str,
        voice_file_path: str,
        is_reply_to_me: bool = False,
    ) -> None:
        """
        Handles incoming voice message: extracts real speech and emotion via Gemini,
        enforces group silence unless addressed to Omar, and responds contextually in Egyptian voice.
        """
        logger.info(f"Received Voice Note from [{sender_name}] in Chat [{chat_id}].")

        # 1. Acoustic Emotion & Speech-to-Text via Gemini Multimodal
        analysis = await acoustic_detector.analyze_voice_note(
            audio_file_path=voice_file_path, sender_name=sender_name
        )

        is_group = int(chat_id) < 0
        if is_group:
            import re
            transcript_norm = re.sub(r"[إأآ]", "ا", analysis.transcript.lower()).replace("ة", "ه")
            is_addressed = (
                is_reply_to_me
                or any(k in transcript_norm for k in ["عمر", "عمور", "عموره", "يا عمر", "ياعمر", "omar", "@omarggforbot"])
            )
            if not is_addressed:
                logger.info(
                    f"Group voice note in [{chat_id}] from [{sender_name}] ignored: "
                    f"Speech does not mention Omar ('{analysis.transcript[:40]}...')."
                )
                return

        # 2. Craft contextual human response using cognitive orchestrator
        resp = await cognitive_orchestrator.process_incoming_event(
            telegram_message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=analysis.transcript,
            media_type="voice",
            chat_type="group" if is_group else "private",
            chat_title=f"محادثة صوتية مع {sender_name}",
        )
        reply_text = (resp.raw_response_text or "").strip()
        if len(reply_text) < 2:
            if analysis.empathy_dialogue_cue:
                reply_text = analysis.empathy_dialogue_cue
            else:
                reply_text = "سمعت الريكورد وفهمتك يا باشا، معاك ومتابع في أي وقت."

        # 3. Always reply via authentic Voice Note (with Spoken-Colloquial Pre-Processor & Smartphone DSP)
        voice_path, waveform, duration = await voice_generator.generate_voice_note(
            text_content=reply_text,
            emotional_tone=analysis.detected_emotion,
            format_ext="ogg",
            dialect_code=getattr(resp, "detected_dialect", "egyptian") or "egyptian",
            gender="male",
            bot_name="عمر",
        )
        if voice_path and os.path.exists(voice_path):
            await mtproto_manager.send_voice_note(
                chat_id=chat_id,
                file_path=voice_path,
                waveform=waveform,
                duration=duration,
                reply_to_msg_id=message_id,
            )
        else:
            bursts = human_typer.prepare_message_bursts(reply_text)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id, bursts=bursts, reply_to_msg_id=message_id
            )

        if not is_group:
            from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
            asyncio.create_task(
                live_event_streamer.stream_dm_event(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    user_text=f"🎙️ [رسالة صوتية]: {analysis.transcript}",
                    bot_reply=f"🎙️ [رد صوتي]: {reply_text}",
                    persona_name="عمر",
                )
            )

    @classmethod
    async def handle_voice_request(
        cls,
        message_id: int,
        chat_id: int,
        sender_id: int,
        sender_name: str,
        message_text: str,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
        target_bot_name: str = "عمر",
        target_bot_id: Optional[str] = None,
        is_reply_to_me: bool = False,
        reply_to_other: bool = False,
    ) -> bool:
        """
        Detects if user asks for a voice note, speech, or singing.
        Strictly enforces immediate voice/song synthesis without textual dodging.
        Guarantees strict MTProto client routing when is_userbot=True.
        """
        if not message_text or message_text.lstrip().startswith(("[ملصق", "[صورة", "<ATTACHED_FILE", "<STUDY_FILE")):
            return False
        from aether_human_core.multimodal_engine.acoustic_voice.voice_intent_enforcer import voice_intent_enforcer
        is_voice, is_singing, song_name = voice_intent_enforcer.detect_intent(message_text)

        if not is_voice:
            return False

        from aether_human_core.config.settings import settings
        is_king = sender_id in settings.super_admin_ids_list
        is_dm = (chat_id == sender_id) or (int(chat_id) > 0)

        t_name_lower = (target_bot_name or "عمر").lower().strip()
        is_fem_bot = is_userbot or any(
            f in t_name_lower for f in ["ريمي", "gg", "مريم", "ماسه", "ماسة", "ملوكة", "ملوكه", "سارة", "ليلى"]
        )
        eff_gender = "female" if is_fem_bot else "male"

        # In groups, strictly safeguard against hijacking:
        if not is_dm:
            import re
            text_norm = re.sub(r"[إأآ]", "ا", message_text.lower()).replace("ة", "ه")

            if reply_to_other:
                logger.debug(f"Voice request in group [{chat_id}] ignored by [{target_bot_name}]: Reply directed at another bot/member.")
                return False

            is_feminine_request = any(
                fem in text_norm for fem in [
                    "ليكي", "سمعيني", "ابعتيلي", "ابعتليلي", "صوتكِ", "صوتك انتي", "يا مريم", "مريومه",
                    "يا قمر", "يا بنتي", "يا شابه", "يا مزه", "يا عسليه", "يا ريمي", "يا ملوكه", "يا ماسه"
                ]
            )

            bot_names = ["عمر", "عمور", "عموره", "omar", "@omarggforbot"] if not is_userbot else ["ريمي", "gg", "جي جي", "reemy"]
            if target_bot_name:
                bot_names.append(re.sub(r"[إأآ]", "ا", target_bot_name.lower()).replace("ة", "ه"))
            has_name = any(k in text_norm for k in bot_names if k)

            if not is_fem_bot and is_feminine_request and not has_name:
                logger.debug(f"Voice request in group [{chat_id}] ignored by Omar: Addressed to female bot/member.")
                return False

            if not is_reply_to_me and not has_name:
                return False

        logger.info(
            f"🎤 Voice/Singing intent detected from [{sender_name}] | Userbot={is_userbot} "
            f"| Bot='{target_bot_name}' | Gender={eff_gender} | Singing={is_singing} | Song='{song_name}'"
        )

        # Villain / Antagonist rejection
        if not is_king:
            async with db_manager.session() as session:
                u_repo = UserRepository(session)
                u_rec = await u_repo.get_by_telegram_id(sender_id)
                if u_rec and (u_rec.role == "VILLAIN" or u_rec.affinity_score < 0):
                    bursts = human_typer.prepare_message_bursts(
                        f"مش هبعت أي فويس لأشرار زيك يا {sender_name}! وفر محاولاتك! 🦹❌"
                    )
                    await mtproto_manager.dispatch_burst_messages(
                        chat_id=chat_id,
                        bursts=bursts,
                        reply_to_msg_id=message_id,
                        is_userbot=is_userbot,
                        userbot_client=userbot_client,
                    )
                    return True

        eff_bot_id = target_bot_id or ("userbot_primary" if is_userbot else "master_omar_official")
        eff_dialect = "egyptian"
        try:
            from bot_factory.factory_manager import bot_factory as _bf_v
            b_cfg = _bf_v.get_bot(eff_bot_id) or _bf_v.get_bot_by_name(target_bot_name)
            if b_cfg and b_cfg.primary_dialect:
                eff_dialect = b_cfg.primary_dialect
        except Exception:
            pass

        # CASE A: User explicitly requested singing / music
        if is_singing:
            pre_text, lyrics = await voice_intent_enforcer.generate_singing_lyrics(
                user_message=message_text,
                user_name=sender_name,
                song_name=song_name,
            )
            bursts = human_typer.prepare_message_bursts(pre_text)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )

            voice_path, waveform, duration = await voice_generator.generate_voice_note(
                text_content=lyrics,
                emotional_tone="JOYFUL",
                format_ext="ogg",
                dialect_code=eff_dialect,
                is_singing=True,
                gender=eff_gender,
                bot_name=target_bot_name,
            )

            await mtproto_manager.send_voice_note(
                chat_id=chat_id,
                file_path=voice_path,
                waveform=waveform,
                duration=duration,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )
            return True

        # CASE B: Contextual colloquial human voice note response
        resp = await cognitive_orchestrator.process_incoming_event(
            telegram_message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
            media_type="voice",
            chat_type="private" if is_dm else "supergroup",
            chat_title=f"محادثة مع {sender_name}",
            is_userbot=is_userbot,
            target_bot_name=target_bot_name,
            target_bot_id=eff_bot_id,
        )
        reply_content = (resp.raw_response_text or "").strip()
        if len(reply_content) < 4:
            if is_fem_bot:
                reply_content = f"بص بقى يا {sender_name}، والله مبسوطة أوي إني بتكلم معاك بصوتي دلوقتي، طمني عليك عامل إيه؟"
            else:
                reply_content = f"بص يا {sender_name}، منور والله يا صاحبي، وأنا معاك وسامعك في أي وقت."

        mood = endocrine_engine.evaluate_psychological_mood()
        voice_path, waveform, duration = await voice_generator.generate_voice_note(
            text_content=reply_content,
            emotional_tone=mood.get("temperament", "WARM"),
            format_ext="ogg",
            dialect_code=eff_dialect,
            is_singing=False,
            gender=eff_gender,
            bot_name=target_bot_name,
        )

        await mtproto_manager.send_voice_note(
            chat_id=chat_id,
            file_path=voice_path,
            waveform=waveform,
            duration=duration,
            reply_to_msg_id=message_id,
            is_userbot=is_userbot,
            userbot_client=userbot_client,
        )

        if is_dm:
            from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
            p_display = f"{target_bot_name} (Userbot)" if is_userbot else target_bot_name
            asyncio.create_task(
                live_event_streamer.stream_dm_event(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    user_text=message_text,
                    bot_reply=f"🎙️ [طلب صوت / غناء]: {reply_content}",
                    persona_name=p_display,
                )
            )
        return True

    @classmethod
    def is_selfie_photo_request(cls, message_text: str, media_type: str = "text") -> bool:
        """
        Determines whether a user's text message is an explicit request for the bot's own selfie/photo.
        Never triggers on incoming stickers, photos, GIFs, documents, or Gemini Vision descriptions!
        """
        if media_type in ("sticker", "photo", "gif", "document", "voice"):
            return False
        if not message_text:
            return False
        stripped = message_text.lstrip()
        if stripped.startswith(("[ملصق", "[صورة", "<ATTACHED_FILE", "<STUDY_FILE", "📄", "👁️")):
            return False

        text_clean = stripped.lower()
        text_norm = (
            text_clean.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
        )

        # Explicit selfie request phrases
        explicit_phrases = [
            "ابعت صورتك", "ابعتلي صورتك", "ابعتيلي صورتك", "ابعت صوره ليك", "ابعتي صوره ليكي",
            "ابعتلي صوره", "ابعتيلي صوره", "ابعت صوره", "ابعت سيلفي", "ابعتلي سيلفي", "ابعتيلي سيلفي",
            "وريني صورتك", "وريني شكلك", "عايز اشوفك", "عاوز اشوفك", "عايزه اشوفك", "عاوزه اشوفك",
            "عايز اشوف شكلك", "عاوز اشوف شكلك", "عايز اشوف صورتك", "عاوز اشوف صورتك",
            "ممكن صورتك", "ممكن سيلفي", "هات صورتك", "هاتي صورتك", "صوره ليك", "صوره ليكي",
            "سيلفي ليك", "سيلفي ليكي", "صور نفسك", "صوري نفسك", "send selfie", "your photo",
        ]
        if any(combo in text_norm for combo in explicit_phrases):
            return True

        # Second-person target keywords + request verbs (note: "صور" is excluded from intent_words so "صورة" never self-matches!)
        second_person_photo_kws = ["صورتك", "سيلفي", "شكلك", "selfie"]
        intent_verbs = ["ابعت", "وريني", "عايز", "عاوز", "عايزه", "عاوزه", "شوف", "اشوف", "اشوفك", "هات", "هاتي", "ممكن", "send", "show"]
        has_second_person_kw = any(p in text_norm for p in second_person_photo_kws)
        has_intent = any(w in text_norm for w in intent_verbs)
        if has_second_person_kw and (has_intent or len(text_norm.split()) <= 3):
            return True

        return False

    @classmethod
    async def handle_photo_request(
        cls,
        message_id: int,
        chat_id: int,
        sender_id: int,
        sender_name: str,
        message_text: str,
        is_reply_to_me: bool = False,
        reply_to_other: bool = False,
        is_userbot: bool = False,
        persona_name: Optional[str] = None,
        gender: Optional[str] = None,
        userbot_client: Optional[Any] = None,
        target_bot_id: Optional[str] = None,
        media_type: str = "text",
    ) -> bool:
        """
        Checks if user is requesting a selfie and evaluates eligibility.
        Generates a 100% watermark-free smartphone selfie with locked Per-Bot Visual DNA
        and dynamic non-repeating expression/pose/angle.
        """
        if not cls.is_selfie_photo_request(message_text, media_type=media_type):
            return False

        text_clean = message_text.lower().strip()
        text_norm = (
            text_clean.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
        )

        eff_persona = persona_name or ("ريمي" if is_userbot else "عمر")
        eff_gender = gender or ("female" if is_userbot else "male")
        is_fem_bot = (eff_gender.lower() == "female")

        is_group = int(chat_id) < 0
        if is_group:
            if reply_to_other:
                logger.debug(f"Photo request in group [{chat_id}] ignored by [{eff_persona}]: Reply directed at another bot/member.")
                return False

            is_feminine_request = any(
                fem in text_norm for fem in [
                    "ليكي", "صورتكِ", "صورتك انتي", "ابعتيلي", "ابعتليلي", "يا مريم", "مريومه",
                    "يا قمر", "يا بنتي", "يا شابه", "يا مزه", "يا عسليه", "يا ريمي", "يا ملوكه", "يا ماسه"
                ]
            )
            if is_userbot:
                target_tokens = ["ريمي", "gg", "جي جي", "reemy"]
            else:
                target_tokens = ["عمر", "عمور", "عموره", "يا عمر", "ياعمر", "omar", "@omarggforbot"]
            if eff_persona:
                target_tokens.append(eff_persona.lower().replace("أ", "ا").replace("ة", "ه"))

            is_addressed_to_this_bot = is_reply_to_me or any(k in text_norm for k in target_tokens if k)

            if not is_addressed_to_this_bot or (not is_fem_bot and is_feminine_request and not any(o in text_norm for o in ["عمر", "عمور", "omar"])):
                logger.debug(f"Photo request in group [{chat_id}] ignored by [{eff_persona}]: Not addressed to this bot.")
                return False

        logger.info(f"📸 Detected photo request from [{sender_name}] for [{eff_persona}]: '{message_text}'")

        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            user_record = await user_repo.get_or_create(telegram_id=sender_id, first_name=sender_name)

        user_vector = UserAffinityVector(
            user_id=sender_id,
            affinity_score=user_record.affinity_score,
            trust_score=user_record.trust_score,
            romantic_attachment=user_record.romantic_attachment,
            respect_dominance=user_record.respect_dominance,
            tier=RelationshipTier(user_record.relationship_tier),
        )

        if user_record.role == "VILLAIN" or user_record.affinity_score < 0:
            bursts = human_typer.prepare_message_bursts(
                f"مش هبعت صوري يا {sender_name}، ركز في كلامك وسيبك من الصور."
            )
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )
            return True

        can_send, verbal_response = life_sim.evaluate_photo_request(user_vector, sender_name)
        if is_fem_bot and can_send:
            verbal_response = f"ثانية واحدة يا {sender_name} ألقطلك سيلفي سريع حالاً 😉📸"

        if not can_send:
            bursts = human_typer.prepare_message_bursts(verbal_response)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )
            return True

        # Approved: Send verbal lead-in first via the exact originating transport (Userbot vs Bot API)
        lead_bursts = human_typer.prepare_message_bursts(verbal_response)
        await mtproto_manager.dispatch_burst_messages(
            chat_id=chat_id,
            bursts=lead_bursts,
            reply_to_msg_id=message_id,
            is_userbot=is_userbot,
            userbot_client=userbot_client,
        )

        # Generate face-locked distinct human photograph
        eff_bot_id = target_bot_id or ("userbot_primary" if is_userbot else "master_omar_official")
        photo_file = await face_lock_pipeline.generate_photo(
            requester_name=sender_name,
            persona_name=eff_persona,
            gender=eff_gender,
            bot_id=eff_bot_id,
        )
        caption = (
            f"سيلفي سريع لعيونك 😉✨"
            if is_fem_bot else
            f"سيلفي سريع لعيونك يا صاحبي 😉📸"
        )

        await mtproto_manager.send_photo(
            chat_id=chat_id,
            photo_path=photo_file,
            caption=caption,
            reply_to_msg_id=message_id,
            is_userbot=is_userbot,
            userbot_client=userbot_client,
        )
        if not is_group:
            from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
            asyncio.create_task(
                live_event_streamer.stream_dm_event(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    user_text=message_text,
                    bot_reply=f"📸 [سيلفي]: {caption}",
                    persona_name=eff_persona,
                )
            )
        return True

    # =========================================================================
    # TASK 3.2: True Visual Sticker, Animated Sticker/GIF, Image & File Vision
    # =========================================================================

    SUPPORTED_TEXT_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".txt", ".json", ".md", ".csv",
        ".log", ".pdf", ".docx", ".pptx", ".html", ".htm", ".css", ".yaml", ".yml", ".xml",
        ".sh", ".bat", ".ps1", ".sql", ".c", ".cpp", ".h", ".java", ".go",
        ".rs", ".php", ".rb", ".ini", ".env", ".toml", ".rtf",
    }

    # Persistent + In-Memory Vision Description Cache (Stickers, GIFs, Photos -> 0ms repeat lookup)
    _vision_cache: Dict[str, str] = {}
    _vision_cache_loaded: bool = False

    # Active Study Companion Sessions: keyed by (chat_id, sender_id) -> {"file_name": str, "content": str, "timestamp": float}
    _active_study_sessions: Dict[Tuple[int, int], Dict[str, Any]] = {}

    @classmethod
    def _ensure_vision_cache_loaded(cls) -> None:
        if cls._vision_cache_loaded:
            return
        cls._vision_cache_loaded = True
        cache_path = os.path.join(os.getcwd(), "artifacts", "vision_cache", "vision_descriptions.json")
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cls._vision_cache.update(data)
        except Exception:
            pass

    @classmethod
    def _save_vision_cache(cls) -> None:
        cache_dir = os.path.join(os.getcwd(), "artifacts", "vision_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "vision_descriptions.json")
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cls._vision_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def store_study_session(
        cls,
        chat_id: int,
        sender_id: int,
        file_name: str,
        extracted_text: str,
    ) -> None:
        """
        Stores the user's uploaded file in active study memory so follow-up messages
        ('اشرحلي الجزء التاني', 'لخصلي الملف', 'اسألني في الملف ده') can study with the user seamlessly.
        """
        if not extracted_text:
            return
        cls._active_study_sessions[(int(chat_id), int(sender_id))] = {
            "file_name": file_name,
            "content": extracted_text[:45000],
            "timestamp": time.time(),
        }
        logger.info(
            f"📚 [Study Companion] Stored active study file [{file_name}] ({len(extracted_text)} chars) "
            f"for user [{sender_id}] in chat [{chat_id}]."
        )

    @classmethod
    def get_active_study_context(
        cls,
        chat_id: int,
        sender_id: int,
        max_age_sec: float = 6 * 3600.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the active uploaded study file for (chat_id, sender_id) if uploaded within the last 6 hours.
        """
        sess = cls._active_study_sessions.get((int(chat_id), int(sender_id)))
        if not sess:
            return None
        if (time.time() - sess.get("timestamp", 0.0)) > max_age_sec:
            cls._active_study_sessions.pop((int(chat_id), int(sender_id)), None)
            return None
        return sess

    @classmethod
    def _downscale_image_for_vision(cls, raw_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
        """
        Downscales large photos in-memory to max 768x768 JPEG (quality 80) before sending to Gemini Vision,
        cutting payload size from ~500KB+ to ~35KB and speeding up Vision response to ~1 second.
        """
        if not raw_bytes or len(raw_bytes) < 45 * 1024:
            return raw_bytes, mime_type
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw_bytes)) as img:
                if max(img.size) <= 768 and len(raw_bytes) <= 90 * 1024:
                    return raw_bytes, mime_type
                img_rgb = img.convert("RGB")
                img_rgb.thumbnail((768, 768), Image.Resampling.LANCZOS)
                out_buf = io.BytesIO()
                img_rgb.save(out_buf, format="JPEG", quality=80, optimize=True)
                return out_buf.getvalue(), "image/jpeg"
        except Exception:
            return raw_bytes, mime_type

    @classmethod
    async def extract_keyframes_with_ffmpeg(
        cls,
        video_bytes: bytes,
        ext: str = ".webm",
        max_frames: int = 1,
    ) -> List[Tuple[bytes, str]]:
        """
        Extracts a visual JPEG keyframe from a .webm video sticker or .mp4 GIF animation
        using FFmpeg in a non-blocking subprocess.
        """
        if not video_bytes:
            return []
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            return []

        cache_dir = os.path.join(os.getcwd(), "artifacts", "vision_cache")
        os.makedirs(cache_dir, exist_ok=True)
        uid = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        in_path = os.path.join(cache_dir, f"in_{uid}{ext}")
        out_pattern = os.path.join(cache_dir, f"frame_{uid}_%d.jpg")

        frames: List[Tuple[bytes, str]] = []
        try:
            with open(in_path, "wb") as f:
                f.write(video_bytes)

            cmd = [
                ffmpeg_bin, "-y", "-i", in_path,
                "-vf", "scale=512:-1",
                "-vframes", str(max_frames),
                "-q:v", "4",
                out_pattern,
            ]
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5.0,
            )

            for idx in range(1, max_frames + 1):
                fp = os.path.join(cache_dir, f"frame_{uid}_{idx}.jpg")
                if os.path.exists(fp):
                    with open(fp, "rb") as rf:
                        data = rf.read()
                    if data:
                        frames.append((data, "image/jpeg"))
        except Exception as exc:
            logger.debug(f"FFmpeg keyframe extraction notice: {exc}")
        finally:
            try:
                if os.path.exists(in_path):
                    os.remove(in_path)
            except Exception:
                pass
            for idx in range(1, max_frames + 2):
                fp = os.path.join(cache_dir, f"frame_{uid}_{idx}.jpg")
                try:
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass

        return frames

    @classmethod
    async def analyze_visual_media_with_gemini(
        cls,
        visual_frames: List[Tuple[bytes, str]],
        media_kind: str = "sticker",
        sticker_emoji: str = "",
        user_caption: str = "",
        cache_id: str = "",
    ) -> str:
        """
        Passes visual frames (image/webp or image/jpeg) to Gemini Vision via inline_data
        with persistent SHA-256 / file_unique_id caching and fast image downscaling.
        """
        from aether_human_core.config.llm_router import llm_pool

        cls._ensure_vision_cache_loaded()

        valid_parts: List[Dict[str, Any]] = []
        first_hash = ""
        for raw_bytes, mime_type in visual_frames:
            if not raw_bytes:
                continue
            if not first_hash:
                first_hash = hashlib.sha256(raw_bytes).hexdigest()[:24]
            opt_bytes, opt_mime = cls._downscale_image_for_vision(raw_bytes, mime_type)
            b64_str = base64.b64encode(opt_bytes).decode("utf-8")
            valid_parts.append(
                {
                    "inline_data": {
                        "mime_type": opt_mime,
                        "data": b64_str,
                    }
                }
            )

        if not valid_parts:
            if media_kind == "sticker":
                return f"[ملصق تعبيري: {sticker_emoji or '✨'}]"
            return user_caption or "[صورة]"

        eff_cache_key = f"{media_kind}:{cache_id or first_hash}"
        vision_desc = cls._vision_cache.get(eff_cache_key, "")

        if not vision_desc:
            if media_kind in ("sticker", "gif"):
                vision_prompt = (
                    "حلل هذا الملصق التعبيري (Sticker/GIF) بأعلى درجات الدقة والعمق البصري والتفصيلي التام، "
                    "مع ذكر أدق التفاصيل بدون أي تستر أو اختصار، حتى يفهم الذكاء الاصطناعي المشهد والحالة النفسية والمغزى بدقة 100%:\n"
                    "1. تحديد الشخصيات والجنس والمظهر:\n"
                    "   - كم شخصية أو كائن في الملصق؟\n"
                    "   - جنس كل شخصية بوضوح تام (رجل/شاب، امرأة/فتاة، طفل، كائن كرتوني، حيوان).\n"
                    "   - الملامح الجسدية، شكل الوجه، العيون، الشفاه، الشعر، ولون البشرة، والبنية.\n"
                    "2. وضعية الجسد الدقيقة والتلامس البدني (Body Posture & Physical Contact):\n"
                    "   - وضعية الجسم بالكامل لكل شخصية (واقف، جالس، متمدد/مستلقي، منحني، راكع، يحتضن، ملتصق، مقترب).\n"
                    "   - حركة وموضع اليدين والأطراف بدقة (أين توضع الأيدي؟ هل تلمس، تمسك، تتحسس، تشد، تحتضن، تصفع، تشير؟ تحديد موضع اللمس بالضبط كالخصر، الوجه، الظهر، الرقبة، اليد، الفخذ، إلخ).\n"
                    "   - مدى القرب الجسدي أو التداخل بين الأجسام (عناق، التصاق، مسافة، قبلة، حميمية).\n"
                    "3. السياق الرومانسي / الحميمي / الجنسي (Sensual, Romantic & Intimate Context):\n"
                    "   - هل هناك تلميح أو تصوير لعاطفة، رغبة، حب، غزل، خجل، إغراء، أو سياق حميمي أو جنسي؟\n"
                    "   - وصف القبلات إن وجدت (قبلة على الشفاه، الخد، الرقبة، الجبين، في الهواء)، أو المداعبة والملامسة الحسية والشهوانية بدقة.\n"
                    "4. الملابس والمظهر الخارجي والعري (Attire & Exposure):\n"
                    "   - ماذا ترتدي الشخصيات؟ وصف نوع ولون الملابس (ملابس نوم، ملابس داخلية، ملابس كاشفة أو ضيقة، عري علوي/كامل، بيجاما، ملابس رسمية/كاجوال).\n"
                    "   - أي تفاصيل مميزة (وشوم، علامات على الجلد، إكسسوارات، شعر مبعثر).\n"
                    "5. تعابير الوجه والانفعالات الدقيقة (Micro-Expressions):\n"
                    "   - نظرة العيون (شغف، حب، شهوة، خجل، مكر، براءة، غضب، صدمة، ضحك هستيري، غمزة، دموع).\n"
                    "   - شكل الفم والابتسامة (مفتوح، عاض على الشفاه، متثائب، يخرج لسانه، مبتسم بدلع أو خبث).\n"
                    "6. النصوص والأدوات والرموز (Text & Props):\n"
                    "   - اقتباس أي نصوص أو كلمات مكتوبة بالملصق بأي لغة كما هي بالضبط.\n"
                    "   - أي رموز أو تأثيرات مرسومة (قلوب، شرارات، نار، علامات استفهام/تعجب، عرق، أثر كف أو حمرة).\n"
                    "7. المغزى والرسالة والريأكشن الفعلي المقصود:\n"
                    "   - ما هو الهدف النفسي أو الشعوري الذي يريد مرسل هذا الملصق إيصاله (دلع، مداعبة رومانسية، إغواء، حب وحنان، خجل، ضحك، تريقة، عتاب، صدمة، طلب اهتمام)؟\n"
                    "اكتب الوصف بأسلوب مباشر وغني جداً وشامل لكل نقطة بأدق التفاصيل وبدون مقدمات:"
                )
            else:
                vision_prompt = (
                    "انظر إلى هذا المشهد المرسل من المستخدم بدقة فائقة وشرح تفصيلي عميق:\n"
                    "- الأشخاص: جنسهم، أعمارهم التقريبية، ملامح وجوههم، تعابيرهم، وضعيات أجسادهم وحركات أيديهم، ملابسهم ومظهرهم بالكامل، وأي تفاصيل حميمية أو لافتة.\n"
                    "- العناصر والأشياء: كل الأدوات، الأجسام، الأجهزة، والأطعمة أو المقتنيات الظاهرة.\n"
                    "- المكان والبيئة: نوع الغرفة، الإضاءة، الأثاث، أو المكان المفتوح والجو العام.\n"
                    "- النصوص والأرقام: اقتباس أي كتابات أو شاشات أو أرقام أو أكواد برمجية ظاهرة بدقة.\n"
                    "اشرح كل تفصيلة بدقة متناهية وبدون اختصار:"
                )

            try:
                vision_desc = await llm_pool.generate_content(
                    prompt=vision_prompt,
                    media_parts=valid_parts,
                    temperature=0.2,
                    max_tokens=850,
                )
                vision_desc = (vision_desc or "").strip().replace("\n", " ")
                if vision_desc:
                    cls._vision_cache[eff_cache_key] = vision_desc
                    cls._save_vision_cache()
            except Exception as exc:
                logger.warning(f"Gemini Vision analysis fallback ({exc}).")
                vision_desc = ""
        else:
            logger.info(f"⚡ [Vision Cache Hit] Instant 0ms description for [{eff_cache_key}]")

        if media_kind in ("sticker", "gif"):
            label = "ملصق مرئي" if media_kind == "sticker" else "متحركة GIF"
            if vision_desc:
                enriched = (
                    f"[{label} {sticker_emoji} - التفاصيل المرئية الكاملة للملصق: ({vision_desc}). "
                    f"تفاعل مع كل تفاصيل المشهد والريأكشن المرسوم بحرية وعفوية وخفة دم كإنسان يرى الملصق أمامه تماماً حسب شخصيتك]"
                )
            else:
                enriched = f"[{label}: {sticker_emoji or '✨'}]"
            if user_caption:
                enriched += f" {user_caption}"
            logger.info(f"👁️ [Gemini Vision Sticker/GIF] Parsed visual content: '{vision_desc[:120]}'")
            return enriched

        # Photo
        if vision_desc:
            enriched = (
                f"[مشهد مرئي أرسله المستخدم - المحتوى المرئي الفعلي بعد رؤيته: ({vision_desc})]"
            )
            if user_caption:
                enriched += f" تعليق المستخدم: {user_caption}"
            else:
                enriched += " علق على المشهد وتفاعل مع ما يظهر فيه بطبيعية كإنسان شايفه قدامه."
            logger.info(f"👁️ [Gemini Vision Photo] Parsed photo content: '{vision_desc[:80]}'")
            return enriched
        return user_caption or "[مشهد مرئي]"

    @classmethod
    def _extract_docx_text(cls, file_bytes: bytes) -> str:
        """
        Extracts all paragraphs and table cells from a Word (.docx) file using built-in zipfile + XML.
        """
        paragraphs: List[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                if "word/document.xml" not in zf.namelist():
                    return ""
                xml_bytes = zf.read("word/document.xml")
                root = ET.fromstring(xml_bytes)
                for elem in root.iter():
                    tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag_name == "p":
                        p_texts = [
                            t.text for t in elem.iter()
                            if (t.tag.split("}")[-1] if "}" in t.tag else t.tag) == "t" and t.text
                        ]
                        if p_texts:
                            paragraphs.append("".join(p_texts).strip())
        except Exception as e:
            logger.warning(f"DOCX extraction notice: {e}")
        return "\n".join(p for p in paragraphs if p)

    @classmethod
    def _extract_pptx_text(cls, file_bytes: bytes) -> str:
        """
        Extracts all slide text from a PowerPoint (.pptx) presentation sorted by slide number.
        """
        slides_output: List[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                slide_files = [
                    name for name in zf.namelist()
                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                ]
                slide_files.sort(
                    key=lambda n: int(re.search(r"slide(\d+)\.xml", n).group(1))
                    if re.search(r"slide(\d+)\.xml", n) else 0
                )
                for idx, s_name in enumerate(slide_files, 1):
                    xml_bytes = zf.read(s_name)
                    root = ET.fromstring(xml_bytes)
                    s_texts = [
                        t.text.strip() for t in root.iter()
                        if (t.tag.split("}")[-1] if "}" in t.tag else t.tag) == "t" and t.text and t.text.strip()
                    ]
                    if s_texts:
                        slides_output.append(f"--- [شريحة {idx}] ---\n" + "\n".join(s_texts))
        except Exception as e:
            logger.warning(f"PPTX extraction notice: {e}")
        return "\n\n".join(slides_output)

    @classmethod
    def extract_document_text(
        cls,
        file_bytes: bytes,
        file_name: str,
        user_caption: str = "",
        max_chars: int = 45000,
        chat_id: Optional[int] = None,
        sender_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Extracts text, lecture slides, or source code from uploaded Documents (.pdf, .docx, .pptx,
        .py, .js, .txt, .json, .md, .csv, .html, etc.) up to 45,000 chars, saves it to the active
        Study Companion Session for follow-up studying, and wraps inside <ATTACHED_FILE>.
        """
        if not file_bytes:
            return None

        safe_name = os.path.basename(file_name or "attached_file.txt")
        _, ext = os.path.splitext(safe_name.lower())

        extracted = ""
        if ext == ".pdf":
            try:
                import pypdf  # type: ignore
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_txt: List[str] = []
                total_len = 0
                for p_idx, page in enumerate(reader.pages, 1):
                    pt = (page.extract_text() or "").strip()
                    if pt:
                        page_block = f"--- [صفحة {p_idx}] ---\n{pt}"
                        pages_txt.append(page_block)
                        total_len += len(page_block)
                        if total_len >= max_chars:
                            break
                extracted = "\n\n".join(pages_txt)
            except Exception as pdf_err:
                logger.warning(f"PDF text extraction error for [{safe_name}]: {pdf_err}")
                extracted = ""
        elif ext == ".docx":
            extracted = cls._extract_docx_text(file_bytes)
        elif ext == ".pptx":
            extracted = cls._extract_pptx_text(file_bytes)
        else:
            for enc in ("utf-8", "utf-8-sig", "cp1256", "latin-1"):
                try:
                    extracted = file_bytes.decode(enc)
                    break
                except Exception:
                    continue

        extracted = (extracted or "").strip()
        if not extracted:
            return None

        if len(extracted) > max_chars:
            extracted = extracted[:max_chars] + "\n... [تم اقتصاص باقي الملف لطوله، ويمكنك سؤال المستخدم عن أي جزء محدد]"

        if chat_id is not None and sender_id is not None:
            cls.store_study_session(chat_id=chat_id, sender_id=sender_id, file_name=safe_name, extracted_text=extracted)

        caption_instruction = (
            user_caption.strip()
            if user_caption
            else (
                "المستخدم أرسل لك هذا الملف لكي تشرحه له وتذاكره معه! "
                "اشرح محتوى الملف وأهم الأفكار والنقاط أو الكود الموجود بداخله بأسلوب واضح ومبسط وممتع، "
                "وذكره في نهاية ردك أنه يقدر يسألك في أي جزء في الملف أو يطلب منك تختبره فيه."
            )
        )
        logger.info(f"📄 [File & Study Companion] Extracted {len(extracted)} chars from [{safe_name}].")
        return (
            f"<ATTACHED_FILE name=\"{safe_name}\">\n"
            f"{extracted}\n"
            f"</ATTACHED_FILE>\n"
            f"{caption_instruction}"
        )

    @classmethod
    async def extract_document_text_async(
        cls,
        file_bytes: bytes,
        file_name: str,
        user_caption: str = "",
        max_chars: int = 45000,
        chat_id: Optional[int] = None,
        sender_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Async document extractor that first runs fast text/XML extraction (.pdf, .docx, .pptx, code, text),
        and if a .pdf is scanned/image-based (yielding < 80 chars via pypdf), uses Gemini Multimodal
        native PDF vision (application/pdf) to read and transcribe the scanned PDF/slides!
        """
        sync_res = cls.extract_document_text(
            file_bytes=file_bytes,
            file_name=file_name,
            user_caption=user_caption,
            max_chars=max_chars,
            chat_id=chat_id,
            sender_id=sender_id,
        )
        if sync_res:
            return sync_res

        safe_name = os.path.basename(file_name or "attached_file.pdf")
        _, ext = os.path.splitext(safe_name.lower())
        if ext == ".pdf" and len(file_bytes) <= 8 * 1024 * 1024:
            try:
                from aether_human_core.config.llm_router import llm_pool
                b64_pdf = base64.b64encode(file_bytes).decode("utf-8")
                pdf_vision_prompt = (
                    "اقرأ هذا الملف الـ PDF المرفق بالكامل واستخرج كل المحتوى العلمي أو النصوص أو الشرائح أو المسائل "
                    "الموجودة فيه بترتيب الصفحات بدقة ووضوح باللغة العربية/الإنجليزية كما وردت:"
                )
                extracted_pdf = await llm_pool.generate_content(
                    prompt=pdf_vision_prompt,
                    media_parts=[{"inline_data": {"mime_type": "application/pdf", "data": b64_pdf}}],
                    temperature=0.2,
                    max_tokens=2048,
                )
                extracted_pdf = (extracted_pdf or "").strip()
                if extracted_pdf:
                    if chat_id is not None and sender_id is not None:
                        cls.store_study_session(
                            chat_id=chat_id, sender_id=sender_id, file_name=safe_name, extracted_text=extracted_pdf
                        )
                    caption_instruction = (
                        user_caption.strip()
                        if user_caption
                        else (
                            "المستخدم أرسل لك هذا الملف لكي تشرحه له وتذاكره معه! "
                            "اشرح محتوى الملف وأهم الأفكار والنقاط الموجودة بداخله بأسلوب واضح ومبسط وممتع."
                        )
                    )
                    logger.info(f"📄 [Gemini Multimodal Scanned PDF] Extracted {len(extracted_pdf)} chars from [{safe_name}].")
                    return (
                        f"<ATTACHED_FILE name=\"{safe_name}\">\n"
                        f"{extracted_pdf}\n"
                        f"</ATTACHED_FILE>\n"
                        f"{caption_instruction}"
                    )
            except Exception as e:
                logger.warning(f"Multimodal scanned PDF extraction fallback for [{safe_name}]: {e}")

        return None

    @classmethod
    async def _download_bot_api_file_bytes(
        cls,
        file_id: str,
        bot_token: str,
        http_client: Any,
    ) -> Optional[bytes]:
        if not file_id or not bot_token or not http_client:
            return None
        try:
            info_res = await http_client.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={"file_id": file_id},
                timeout=12.0,
            )
            if info_res.status_code != 200:
                return None
            file_path_tg = info_res.json().get("result", {}).get("file_path")
            if not file_path_tg:
                return None
            dl_res = await http_client.get(
                f"https://api.telegram.org/file/bot{bot_token}/{file_path_tg}",
                timeout=20.0,
            )
            if dl_res.status_code == 200:
                return dl_res.content
        except Exception as exc:
            logger.debug(f"Bot API file download notice for [{file_id}]: {exc}")
        return None

    @classmethod
    async def inspect_bot_api_media(
        cls,
        msg: Dict[str, Any],
        bot_token: str,
        http_client: Any,
    ) -> Optional[Tuple[str, str]]:
        """
        Unified Bot API Multimodal Inspector for Master Bot and all Factory Sub-Bots.
        Inspects Stickers (.webp, .webm, .tgs), GIFs/Animations, Photos, and Files/Documents (.pdf, .docx, .pptx, code, txt).
        Returns (enriched_message_text, media_type) or None if not a visual/document media message.
        """
        caption = msg.get("caption", "") or ""
        chat_id = msg.get("chat", {}).get("id")
        sender_id = msg.get("from", {}).get("id", chat_id)

        # Send immediate typing indicator so user sees instant responsiveness while media is analyzed
        if chat_id and bot_token and http_client:
            asyncio.create_task(
                http_client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                    timeout=4.0,
                )
            )

        # 1. Sticker (.webp static, .webm video, .tgs animated)
        sticker = msg.get("sticker")
        if sticker:
            emoji = sticker.get("emoji", "") or "✨"
            unique_id = sticker.get("file_unique_id", "") or ""
            is_animated = bool(sticker.get("is_animated"))  # .tgs
            is_video = bool(sticker.get("is_video"))        # .webm
            thumb_obj = sticker.get("thumbnail") or sticker.get("thumb") or {}
            thumb_file_id = thumb_obj.get("file_id")

            # Fast cache check BEFORE downloading bytes if file_unique_id is already cached!
            cls._ensure_vision_cache_loaded()
            if unique_id and f"sticker:{unique_id}" in cls._vision_cache:
                enriched = await cls.analyze_visual_media_with_gemini(
                    visual_frames=[(b"cached", "image/webp")],
                    media_kind="sticker",
                    sticker_emoji=emoji,
                    user_caption=caption,
                    cache_id=unique_id,
                )
                return enriched, "sticker"

            frames: List[Tuple[bytes, str]] = []
            # Priority optimization: For animated (.tgs) OR video (.webm) stickers, use Telegram's built-in
            # high-clarity thumbnail first (~8KB webp/jpg) to avoid downloading a full video + spawning ffmpeg!
            if (is_animated or is_video) and thumb_file_id:
                t_bytes = await cls._download_bot_api_file_bytes(thumb_file_id, bot_token, http_client)
                if t_bytes:
                    mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                    frames.append((t_bytes, mime))

            if not frames and is_video:
                v_bytes = await cls._download_bot_api_file_bytes(sticker.get("file_id", ""), bot_token, http_client)
                if v_bytes:
                    frames = await cls.extract_keyframes_with_ffmpeg(v_bytes, ext=".webm", max_frames=1)
            elif not frames and not is_animated:
                s_bytes = await cls._download_bot_api_file_bytes(sticker.get("file_id", ""), bot_token, http_client)
                if s_bytes:
                    frames.append((s_bytes, "image/webp"))

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="sticker",
                sticker_emoji=emoji,
                user_caption=caption,
                cache_id=unique_id,
            )
            return enriched, "sticker"

        # 2. GIF / Animation
        anim = msg.get("animation")
        if anim:
            unique_id = anim.get("file_unique_id", "") or ""
            frames = []
            thumb_obj = anim.get("thumbnail") or anim.get("thumb") or {}
            thumb_id = thumb_obj.get("file_id")
            if thumb_id:
                t_bytes = await cls._download_bot_api_file_bytes(thumb_id, bot_token, http_client)
                if t_bytes:
                    mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                    frames.append((t_bytes, mime))
            if not frames:
                file_size = int(anim.get("file_size", 0) or 0)
                if 0 < file_size <= 6 * 1024 * 1024:
                    a_bytes = await cls._download_bot_api_file_bytes(anim.get("file_id", ""), bot_token, http_client)
                    if a_bytes:
                        frames = await cls.extract_keyframes_with_ffmpeg(a_bytes, ext=".mp4", max_frames=1)
            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="gif",
                user_caption=caption,
                cache_id=unique_id,
            )
            return enriched, "sticker"

        # 3. Photo (Pick medium-high resolution <= 800px when available for ultra-fast download & vision)
        photos = msg.get("photo")
        if photos and isinstance(photos, list):
            chosen_photo = photos[-1]
            if len(photos) >= 2:
                # If second-to-last photo is already >= 320px, use it for 3x faster download
                cand = photos[-2]
                if int(cand.get("width", 0) or 0) >= 320:
                    chosen_photo = cand
            unique_id = chosen_photo.get("file_unique_id", "") or ""
            p_bytes = await cls._download_bot_api_file_bytes(chosen_photo.get("file_id", ""), bot_token, http_client)
            frames = [(p_bytes, "image/jpeg")] if p_bytes else []
            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="photo",
                user_caption=caption,
                cache_id=unique_id,
            )
            return enriched, "photo"

        # 4. Document / File (Study Companion: PDF, DOCX, PPTX, TXT, MD, CSV, Code files, or Image documents)
        doc = msg.get("document")
        if doc:
            file_name = doc.get("file_name", "") or "attached_file"
            mime_type = (doc.get("mime_type", "") or "").lower()
            file_size = int(doc.get("file_size", 0) or 0)
            _, ext = os.path.splitext(file_name.lower())

            if mime_type.startswith("image/") and file_size <= 10 * 1024 * 1024:
                d_bytes = await cls._download_bot_api_file_bytes(doc.get("file_id", ""), bot_token, http_client)
                if d_bytes:
                    enriched = await cls.analyze_visual_media_with_gemini(
                        visual_frames=[(d_bytes, mime_type)],
                        media_kind="photo",
                        user_caption=caption,
                        cache_id=doc.get("file_unique_id", ""),
                    )
                    return enriched, "photo"

            is_supported_doc = (
                ext in cls.SUPPORTED_TEXT_EXTENSIONS
                or mime_type.startswith("text/")
                or any(k in mime_type for k in ("json", "pdf", "word", "officedocument", "presentation", "powerpoint", "xml", "csv"))
            )
            if is_supported_doc and file_size <= 20 * 1024 * 1024:
                d_bytes = await cls._download_bot_api_file_bytes(doc.get("file_id", ""), bot_token, http_client)
                if d_bytes:
                    doc_prompt = await cls.extract_document_text_async(
                        file_bytes=d_bytes,
                        file_name=file_name,
                        user_caption=caption,
                        chat_id=chat_id,
                        sender_id=sender_id,
                    )
                    if doc_prompt:
                        return doc_prompt, "document"

        return None

    @classmethod
    async def inspect_telethon_media(
        cls,
        event: Any,
    ) -> Optional[Tuple[str, str]]:
        """
        Unified Telethon MTProto Multimodal Inspector for Userbot.
        Inspects Stickers (.webp, .webm, .tgs), GIFs, Photos, and Files/Documents (.pdf, .docx, .pptx, code, txt).
        Returns (enriched_message_text, media_type) or None.
        """
        raw_caption = getattr(event, "raw_text", "") or ""
        file_obj = getattr(event, "file", None)
        mime_type = (getattr(file_obj, "mime_type", "") or "").lower()
        chat_id = getattr(event, "chat_id", None)
        sender_id = getattr(event, "sender_id", chat_id)

        # 1. Sticker
        if getattr(event, "sticker", None):
            sticker_emoji = getattr(file_obj, "emoji", "") or "✨"
            frames: List[Tuple[bytes, str]] = []
            try:
                if "x-tgsticker" in mime_type or "webm" in mime_type or "video" in mime_type:
                    t_bytes = await event.download_media(bytes, thumb=-1)
                    if t_bytes:
                        t_mime = "image/webp" if t_bytes[:4] == b"RIFF" else "image/jpeg"
                        frames.append((t_bytes, t_mime))
                    elif "webm" in mime_type or "video" in mime_type:
                        v_bytes = await event.download_media(bytes)
                        if v_bytes:
                            frames = await cls.extract_keyframes_with_ffmpeg(v_bytes, ext=".webm", max_frames=1)
                else:
                    s_bytes = await event.download_media(bytes)
                    if s_bytes:
                        frames.append((s_bytes, "image/webp"))
            except Exception as st_err:
                logger.debug(f"Telethon sticker download notice: {st_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="sticker",
                sticker_emoji=sticker_emoji,
                user_caption=raw_caption,
            )
            return enriched, "sticker"

        # 2. GIF / Animation
        if getattr(event, "gif", None):
            frames = []
            try:
                t_bytes = await event.download_media(bytes, thumb=-1)
                if t_bytes:
                    frames.append((t_bytes, "image/jpeg"))
                else:
                    g_bytes = await event.download_media(bytes)
                    if g_bytes:
                        frames = await cls.extract_keyframes_with_ffmpeg(g_bytes, ext=".mp4", max_frames=1)
            except Exception as gf_err:
                logger.debug(f"Telethon GIF download notice: {gf_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="gif",
                user_caption=raw_caption,
            )
            return enriched, "sticker"

        # 3. Photo
        if getattr(event, "photo", None):
            frames = []
            try:
                p_bytes = await event.download_media(bytes)
                if p_bytes:
                    frames.append((p_bytes, "image/jpeg"))
            except Exception as ph_err:
                logger.debug(f"Telethon photo download notice: {ph_err}")

            enriched = await cls.analyze_visual_media_with_gemini(
                visual_frames=frames,
                media_kind="photo",
                user_caption=raw_caption,
            )
            return enriched, "photo"

        # 4. Document / File (not voice/audio/video/sticker)
        if getattr(event, "document", None) and not (getattr(event, "voice", None) or getattr(event, "audio", None)):
            file_name = getattr(file_obj, "name", "") or "attached_file.txt"
            file_size = int(getattr(file_obj, "size", 0) or 0)
            _, ext = os.path.splitext(file_name.lower())

            if mime_type.startswith("image/") and file_size <= 10 * 1024 * 1024:
                try:
                    d_bytes = await event.download_media(bytes)
                    if d_bytes:
                        enriched = await cls.analyze_visual_media_with_gemini(
                            visual_frames=[(d_bytes, mime_type)],
                            media_kind="photo",
                            user_caption=raw_caption,
                        )
                        return enriched, "photo"
                except Exception:
                    pass

            is_supported_doc = (
                ext in cls.SUPPORTED_TEXT_EXTENSIONS
                or mime_type.startswith("text/")
                or any(k in mime_type for k in ("json", "pdf", "word", "officedocument", "presentation", "powerpoint", "xml", "csv"))
            )
            if is_supported_doc and file_size <= 20 * 1024 * 1024:
                try:
                    d_bytes = await event.download_media(bytes)
                    if d_bytes:
                        doc_prompt = await cls.extract_document_text_async(
                            file_bytes=d_bytes,
                            file_name=file_name,
                            user_caption=raw_caption,
                            chat_id=chat_id,
                            sender_id=sender_id,
                        )
                        if doc_prompt:
                            return doc_prompt, "document"
                except Exception as doc_err:
                    logger.debug(f"Telethon document download notice: {doc_err}")

        return None


media_handler = MediaEventHandler()
