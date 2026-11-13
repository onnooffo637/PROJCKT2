"""
Autonomous Profile Mutation & Stories Engine for MTProto Living Userbot (V2.0).
Empowers Omar to autonomously control his visual avatar, display name, biography,
and Telegram Stories according to internal neuro-hormones, circadian cycle, and social events.
Protected by the Stealth Anti-Ban Shield (Strict rate caps & human pacing).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from userbot_mtproto_engine.stealth_anti_ban import stealth_anti_ban
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine
from aether_human_core.multimodal_engine.visual_identity.life_simulator import life_sim

logger = logging.getLogger("Aether.Userbot.AutonomousProfile")


class BioProfileState(BaseModel):
    bio_text: str
    mood_category: str
    requires_avatar_change: bool = False
    avatar_theme: str = "casual_maadi"


class AutonomousProfileMutationEngine:
    """
    Simulates genuine human profile self-expression across Telegram:
    - Modulates Bio text based on endocrine state.
    - Decides whether to update or temporarily delete profile photo.
    - Designs and publishes authentic Telegram Stories.
    """

    MOOD_BIOS = {
        "JOY_ENERGY": [
            "Software engineer, coffee enthusiast & music lover ☕💻 | القاهرة",
            "الدنيا رايقة وكل حاجة ماشية تمام الحمد لله ✨",
            "Coding, AI, and beautiful Cairo vibes 🎧",
            "مركز في أهدافي ومبسوط بالرحلة 🚀",
        ],
        "TIRED_MELANCHOLY": [
            "مشغول شوية اليومين دول.. نتكلم بعدين.",
            "...",
            "offline mentally | محتاج شوية هدوء",
            "أحياناً الصمت أبلغ من ألف كلمة.",
        ],
        "LATE_NIGHT_SLEEP": [
            "أوضتي | القاهرة 🌙 (Sleeping mode)",
            "الليل هادي وسكونه مريح.. تصبحوا على خير 🌌",
            "Late night thoughts & ambient melodies 🎧",
        ],
        "TECH_FOCUSED": [
            "Deep in Python, Neural Networks & System Architecture 🧠⚡",
            "Building next-gen AI entities | Zero to One 💻",
            "Code, Coffee & Git commits ☕",
        ],
        "DEFENSIVE_UPSET": [
            "الكرامة فوق كل اعتبار.",
            "محدش يقرب من مساحتي الشخصية.",
            "Silence is the ultimate response.",
        ],
    }

    def __init__(self):
        self._last_bio_update_time: float = 0.0
        self._last_photo_update_time: float = 0.0
        self._active_bio: str = self.MOOD_BIOS["JOY_ENERGY"][0]
        self._is_avatar_hidden: bool = False

    def evaluate_profile_expression(self) -> BioProfileState:
        """
        Synthesizes emotional hormones and circadian hour to deduce appropriate profile state.
        """
        hormones = endocrine_engine.get_current_state()
        circadian = circadian_engine.evaluate_circadian_state()

        # 1. Stressed, insulted, or acute anger -> Defensive/Upset bio, may hide avatar
        if hormones.cortisol > 0.70:
            bio = random.choice(self.MOOD_BIOS["DEFENSIVE_UPSET"])
            return BioProfileState(
                bio_text=bio,
                mood_category="DEFENSIVE_UPSET",
                requires_avatar_change=True,
                avatar_theme="moody_dark",
            )

        # 2. Sleeping or late night exhaustion -> Night/Sleep bio
        if circadian.get("is_sleeping") or circadian.get("hour_fraction", 12.0) >= 23.5:
            bio = random.choice(self.MOOD_BIOS["LATE_NIGHT_SLEEP"])
            return BioProfileState(
                bio_text=bio,
                mood_category="LATE_NIGHT_SLEEP",
                requires_avatar_change=False,
                avatar_theme="bedroom_ambient",
            )

        # 3. Low serotonin or melancholic -> Tired bio
        if hormones.serotonin < 0.35:
            bio = random.choice(self.MOOD_BIOS["TIRED_MELANCHOLY"])
            return BioProfileState(
                bio_text=bio,
                mood_category="TIRED_MELANCHOLY",
                requires_avatar_change=True,
                avatar_theme="moody_dark",
            )

        # 4. Tech focus during work hours (11:00 AM - 17:30 PM)
        if 11.0 <= circadian.get("hour_fraction", 12.0) < 17.5:
            bio = random.choice(self.MOOD_BIOS["TECH_FOCUSED"])
            return BioProfileState(
                bio_text=bio,
                mood_category="TECH_FOCUSED",
                requires_avatar_change=False,
                avatar_theme="work_office",
            )

        # 5. Default happy / energetic state
        bio = random.choice(self.MOOD_BIOS["JOY_ENERGY"])
        return BioProfileState(
            bio_text=bio,
            mood_category="JOY_ENERGY",
            requires_avatar_change=False,
            avatar_theme="casual_maadi",
        )

    async def apply_autonomous_mutation(self, client: Any = None) -> Optional[str]:
        """
        Evaluates and conditionally mutates living userbot profile on Telegram.
        Respects strict Stealth Anti-Ban rate limits (max 2-3 per day).
        """
        state = self.evaluate_profile_expression()
        now = time.time()

        # Update Bio if allowed and changed
        can_bio, _ = stealth_anti_ban.can_update_bio()
        if can_bio and state.bio_text != self._active_bio and (now - self._last_bio_update_time >= 7200):
            self._active_bio = state.bio_text
            self._last_bio_update_time = now
            stealth_anti_ban.record_bio_update()
            logger.info(f"✨ Living Userbot autonomously mutated Bio: '{state.bio_text}'")

            # Apply to real Telethon client if connected
            if client and hasattr(client, "is_connected") and client.is_connected():
                try:
                    from telethon.tl.functions.account import UpdateProfileRequest
                    await client(UpdateProfileRequest(about=state.bio_text))
                    logger.info("Successfully updated Telegram bio via MTProto.")
                except Exception as exc:
                    logger.warning(f"Failed to update bio via Telethon: {exc}")

            return state.bio_text

        return None


class AutonomousStoriesEngine:
    """
    Subconscious Story Generation & Publishing Engine for Telegram.
    Creates rich multimedia stories when significant emotional or social moments occur.
    """

    STORY_PROMPTS = [
        "ساعة الغروب في القاهرة مع فنجان قهوة رايق.. تفاصيل بسيطة بتفرق في اليوم ☕🌅",
        "لما تحل باج كان مطلع عينك طول اليوم.. إحساس لا يوصف 💻⚡",
        "الهدوء نعمة، ومش كل حاجة تستاهل إنك ترد عليها.. ليلة هادية للجميع 🌙",
        "يا رب يوم لطيف وخفيف على قلوبكم جميعاً ✨",
    ]

    @classmethod
    async def generate_daily_story(cls) -> Dict[str, Any]:
        """
        Creates a structured Telegram story object (caption, background image prompt, ambient sound).
        """
        location = life_sim.get_current_location_state()
        caption = random.choice(cls.STORY_PROMPTS)

        story_payload = {
            "caption": caption,
            "location_name": location.location_name_ar,
            "created_at": time.time(),
            "privacy": "PUBLIC_CONTACTS",
            "ambient_audio": location.ambient_sound_type,
        }
        logger.info(f"📸 Autonomous Stories Engine generated story draft: '{caption[:45]}...'")
        return story_payload


# Global Singleton Instances
autonomous_profile_mutator = AutonomousProfileMutationEngine()
autonomous_stories_engine = AutonomousStoriesEngine()

