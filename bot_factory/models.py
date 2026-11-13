"""
Bot Factory Data Models & Schema for Project Aether-Human (V2.0).
Defines Multi-Tenant Official Bot and MTProto Userbot instances, genders, and configurations.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class BotPlatformType(str, Enum):
    OFFICIAL_BOT = "OFFICIAL_BOT"       # Standard Telegram BotFather Token
    MTPROTO_USERBOT = "MTPROTO_USERBOT" # Living Telegram User Account (Telethon/Pyrogram session)


class BotGender(str, Enum):
    MALE = "MALE"       # ولد - تصريف المذكر
    FEMALE = "FEMALE"   # بنت - تصريف المؤنث والرقة الأنثوية


class BotInstanceConfig(BaseModel):
    instance_id: str
    bot_type: BotPlatformType
    token_or_session: str
    name: str
    gender: BotGender = BotGender.MALE
    age: int = 22
    bio: str = ""
    avatar_url: Optional[str] = None
    template_code: str = "CUSTOM"
    system_prompt: str = ""
    primary_dialect: str = "egyptian"  # 100% Free-text dialect (e.g. لهجة عراقية بغدادية, لهجة فضائية, خليط مصري على فصحى)
    origin_location: str = ""          # 100% Free-text origin (e.g. كوكب زحل, بغداد) - NEVER default to Cairo!
    chattiness_level: float = 0.5      # 0.0 to 1.0 group interaction rate
    voice_profile: Optional[str] = None # TTS voice override ID
    voice_pitch: int = 0               # Pitch adjustment -20Hz to +20Hz
    voice_rate: int = 0                # Speech rate adjustment -30% to +30%
    custom_rules: str = ""             # Arbitrary custom behavioral rules
    relationship_creator: str = ""     # Relationship with creator/owner
    visual_dna: str = ""               # Persistent locked physical face blueprint for 100% consistent selfies
    base_identity_seed: int = 0        # Unique base biometric seed for this bot
    owner_id: int = 0         # Telegram user_id of the admin who created/owns this bot (strict isolation)
    created_at: float = Field(default_factory=time.time)
    is_active: bool = False
    notes: str = ""

    def get_display_label(self) -> str:
        gender_icon = "👧" if self.gender == BotGender.FEMALE else "👦"
        type_icon = "🤖" if self.bot_type == BotPlatformType.OFFICIAL_BOT else "👤"
        status_icon = "🟢" if self.is_active else "⚪"
        return f"{status_icon} {gender_icon} {self.name} ({type_icon} {self.bot_type.value})"

