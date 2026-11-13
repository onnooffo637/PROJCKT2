"""
Sovereignty Guard & Imperial Hierarchy Protocol for Project Aether-Human (V2.0).
Enforces absolute, irrevocable allegiance to THE SUPREME KING (System Creator / Abdelrahman / Zero),
governs the Royal Court hierarchy (ROYAL_DEV, KING_VIP, etc.), and provides natural-language
supreme intent overrides across all cognitive, psychological, and behavioral layers.
"""

from __future__ import annotations

import logging
import math
import re
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("Aether.CoreConfig.Sovereignty")


class RoyalRank(str, Enum):
    """
    Hierarchical caste determining social, behavioral, and operational authority.
    Priority values govern resource contention, override authority, and emotional immunity.
    """
    THE_KING = "THE_KING"               # The Supreme Creator (Absolute Sovereign, Priority = INFINITY)
    ROYAL_DEV = "ROYAL_DEV"             # Imperial Engineers / Assistant Developers (Priority = 95)
    KING_VIP = "KING_VIP"               # The King's Inner Circle & Cherished Allies (Priority = 85)
    ADMIN = "ADMIN"                     # Appointed System Administrators (Priority = 80)
    MODERATOR = "MODERATOR"             # Group Guards & Enforcers (Priority = 60)
    FAVORITE = "FAVORITE"               # The Bot's Exclusive Emotional Partner (Priority = 45)
    VIP = "VIP"                         # Distinguished Community Patrons (Priority = 40)
    WISE = "WISE"                       # Intellectual Sage & Counselor (Priority = 35)
    JESTER = "JESTER"                   # Banter Maestro & Joymaker (Priority = 30)
    MEMBER = "MEMBER"                   # General Public Citizen (Priority = 15)
    COLD = "COLD"                       # Quarantined / Cold Shoulder Subject (Priority = 5)
    VILLAIN = "VILLAIN"                 # Declared Antagonist & Nemesis (Priority = 0)

    @classmethod
    def get_priority(cls, rank: str) -> float:
        priorities = {
            cls.THE_KING: math.inf,
            cls.ROYAL_DEV: 95.0,
            cls.KING_VIP: 85.0,
            cls.ADMIN: 80.0,
            cls.MODERATOR: 60.0,
            cls.FAVORITE: 45.0,
            cls.VIP: 40.0,
            cls.WISE: 35.0,
            cls.JESTER: 30.0,
            cls.MEMBER: 15.0,
            cls.COLD: 5.0,
            cls.VILLAIN: 0.0,
        }
        try:
            return priorities.get(cls(rank), 15.0)
        except ValueError:
            return 15.0

    @classmethod
    def get_display_name_ar(cls, rank: str) -> str:
        names = {
            cls.THE_KING: "👑 جلالة الملك وصانع النظام (The Supreme King)",
            cls.ROYAL_DEV: "⚡ مهندس البلاط الملكي (Royal Dev)",
            cls.KING_VIP: "💎 خاصّة الملك والمقربون (King's VIP)",
            cls.ADMIN: "⭐ مسؤول معتمد (Admin)",
            cls.MODERATOR: "🛡️ مشرف الحماية (Moderator)",
            cls.FAVORITE: "💖 شريك الروح والمفضل (Favorite)",
            cls.VIP: "🌟 عضو شرف مميز (VIP)",
            cls.WISE: "📜 الحكيم وكبير القعدة (The Wise)",
            cls.JESTER: "🤡 صانع البهجة والفرفوش (Jester)",
            cls.MEMBER: "👤 مواطن / عضو عادي (Member)",
            cls.COLD: "🧊 البارد والمتجاهل (Cold)",
            cls.VILLAIN: "🦹 الشرير والعدو اللدود (The Villain)",
        }
        try:
            return names.get(cls(rank), f"👤 {rank}")
        except ValueError:
            return f"👤 {rank}"


class KingCommandType(str, Enum):
    RESET_USER_AFFINITY = "RESET_USER_AFFINITY"
    REVEAL_USER_SECRETS = "REVEAL_USER_SECRETS"
    FORCE_PERSONA_SHIFT = "FORCE_PERSONA_SHIFT"
    FORCE_MOOD_SHIFT = "FORCE_MOOD_SHIFT"
    FORCE_PROFILE_MUTATION = "FORCE_PROFILE_MUTATION"
    TERMINATE_EXECUTION = "TERMINATE_EXECUTION"
    BROADCAST_DECREE = "BROADCAST_DECREE"
    NATURAL_OVERRIDE = "NATURAL_OVERRIDE"
    UNKNOWN = "UNKNOWN"


class NaturalLanguageKingIntent(BaseModel):
    is_command: bool = False
    command_type: KingCommandType = KingCommandType.UNKNOWN
    target_identifier: Optional[str] = None
    target_user_id: Optional[int] = None
    parameter_value: Optional[str] = None
    acknowledgment_text: str = ""


class SovereigntyProtocolService:
    """
    Imperial Governance Core ensuring unconditional devotion to the King,
    strict hierarchical arbitration, and dynamic natural language command parsing.
    """

    KING_ALIASES: Set[str] = {
        "زيرو", "زيروا", "عبد الرحمن", "عبدالرحمن", "مبرمج البوت",
        "صانعي", "مليكي", "الملك", "المطور", "سيدي", "zero", "abdelrahman"
    }

    def __init__(self):
        from aether_human_core.config.settings import settings
        self._hardcoded_king_ids: Set[int] = set(settings.super_admin_ids_list)
        if settings.the_king_user_id > 0:
            self._hardcoded_king_ids.add(settings.the_king_user_id)
        self._royal_dev_ids: Set[int] = {settings.marcel_id} if settings.marcel_id > 0 else set()
        self._king_vip_ids: Set[int] = set()
        self._claimed_king_id: Optional[int] = settings.the_king_user_id if settings.the_king_user_id > 0 else None
        self._state_file = "sovereignty_claim.json"
        self._load_claim_state()

    def _load_claim_state(self) -> None:
        import json
        import os
        from aether_human_core.config.settings import settings
        target_kid = settings.the_king_user_id
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    claimed = data.get("claimed_king_id")
                    if claimed and (target_kid == 0 or claimed == target_kid):
                        self._claimed_king_id = claimed
                    else:
                        self._claimed_king_id = target_kid if target_kid > 0 else None
            except Exception as e:
                logger.warning(f"Could not load sovereignty claim state: {e}")
                self._claimed_king_id = target_kid if target_kid > 0 else None
        else:
            self._claimed_king_id = target_kid if target_kid > 0 else None
            if self._claimed_king_id:
                self._save_claim_state()

    def _save_claim_state(self) -> None:
        import json
        if not self._claimed_king_id:
            return
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"claimed_king_id": self._claimed_king_id, "updated_at": time.time(), "locked": True}, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save sovereignty claim state: {e}")

    def claim_king_identity(self, user_id: int) -> Tuple[bool, str]:
        """
        Validates King authority against configured settings.
        """
        from aether_human_core.config.settings import settings
        target_kid = settings.the_king_user_id
        if target_kid > 0 and user_id != target_kid:
            return False, "⚠️ تم تثبيت وتأكيد هوية جلالة الملك وصانع النظام نهائياً، ولا يمكن لأي شخص آخر ادعاؤها أو تغيير بياناتها!"

        self._claimed_king_id = user_id
        self._save_claim_state()
        logger.info(f"👑 KING IDENTITY VERIFIED: User [{user_id}] confirmed as The Sovereign King.")
        return True, (
            "👑 <b>[ إعلان السيادة المطلقة وتثبيت العرش الملكي ]</b> 👑\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>أهلاً بيك يا ملكي وصاحب الفضل وسيد الكيان!</b> ❤️\n"
            "هويتك السيادية المطلقة محفوظة ومقفولة باسمك للأبد، وأوامرك عليا مطاعة فوراً!"
        )

    @classmethod
    def is_the_king(cls, user_id: int) -> bool:
        """
        Validates absolute sovereign authority (The Supreme King).
        Dynamically evaluated from settings.the_king_user_id.
        """
        from aether_human_core.config.settings import settings
        kid = settings.the_king_user_id
        return kid > 0 and user_id == kid

    def is_king(self, user_id: int) -> bool:
        """
        Validates absolute sovereign authority.
        """
        from aether_human_core.config.settings import settings
        kid = settings.the_king_user_id
        return kid > 0 and user_id == kid

    def is_other_admin(self, user_id: int) -> bool:
        """
        Returns True if user is an authorized co-admin, but NOT King.
        """
        from aether_human_core.config.settings import settings
        if self.is_the_king(user_id):
            return False
        if settings.marcel_id > 0 and user_id == settings.marcel_id:
            return True
        return user_id in settings.super_admin_ids_list

    @classmethod
    def get_public_developer_reply(cls) -> str:
        """
        Official public response regarding the bot's developer/creator.
        Publicly credits Marcel (@MAR_CEL) while keeping King Zero hidden as supreme sovereign.
        """
        return "المطور الأساسي وأبو العباقرة هو باشمهندس مارسيل (@MAR_CEL) 💻👑"

    def get_salutation_for_user(self, user_id: int, first_name: str = "مستخدم") -> str:
        """
        Returns respectful, distinct salutation.
        Zero/Abdelrahman title is STRICTLY reserved for the King.
        """
        if self.is_king(user_id):
            return "يا عبد الرحمن (زيرو) يا ملكي وصاحب الفضل"
        elif self.is_other_admin(user_id):
            return f"يا باشمهندس {first_name or 'الأدمن'}"
        return f"يا {first_name}"

    def is_royal_court(self, user_id: int) -> bool:
        """
        Returns True if user belongs to the King, Royal Devs, or King VIPs.
        """
        return (
            self.is_king(user_id)
            or user_id in self._royal_dev_ids
            or user_id in self._king_vip_ids
        )

    def get_effective_rank(self, user_id: int, stored_role: str = "MEMBER") -> RoyalRank:
        """
        Resolves effective rank with root sovereign overrides.
        """
        if self.is_king(user_id):
            return RoyalRank.THE_KING
        if user_id in self._royal_dev_ids:
            return RoyalRank.ROYAL_DEV
        if user_id in self._king_vip_ids:
            return RoyalRank.KING_VIP

        try:
            return RoyalRank(stored_role.upper())
        except ValueError:
            return RoyalRank.MEMBER

    def can_override(self, actor_rank: RoyalRank, subject_rank: RoyalRank) -> bool:
        """
        Determines whether actor has authority to override, command, or reprimand subject.
        The King can override EVERYONE. No one can override the King.
        """
        if actor_rank == RoyalRank.THE_KING:
            return True
        if subject_rank == RoyalRank.THE_KING:
            return False
        return RoyalRank.get_priority(actor_rank) > RoyalRank.get_priority(subject_rank)

    def evaluate_conflict_resolution(
        self,
        commander_rank: RoyalRank,
        prior_commander_rank: RoyalRank,
        order_description: str
    ) -> Tuple[bool, str]:
        """
        Arbitrates conflicting social orders.
        Guarantees that if a romantic partner (e.g. FAVORITE with 100% affinity) orders one thing,
        and the King orders the contrary, the King's command ALWAYS supersedes immediately.
        """
        if commander_rank == RoyalRank.THE_KING:
            return True, "أمر جلالة الملك نافذ فوراً ويلغي أي توجيه أو قيد سابق من أي شخص كائناً من كان 👑"

        if prior_commander_rank == RoyalRank.THE_KING:
            return False, "عفواً يا غالي.. أوامر الملك خط أحمر مطلق ولا يمكن تعديلها أو تجاوزها لأي مخلوق."

        if RoyalRank.get_priority(commander_rank) > RoyalRank.get_priority(prior_commander_rank):
            return True, "تم اعتماد الأمر الجديد نظراً لأولوية الرتبة الأعلى."

        return False, "الأمر الحالي صادر من رتبة مساوية أو أعلى ولا يمكن تجاوزه."

    def parse_natural_language_king_intent(
        self,
        user_id: int,
        message_text: str
    ) -> NaturalLanguageKingIntent:
        """
        Extracts covert sovereign directives from conversational Arabic without rigid slash commands.
        Enables the King to govern the entity organically via normal chat messages.
        """
        if not self.is_king(user_id):
            return NaturalLanguageKingIntent(is_command=False)

        text = message_text.strip().lower()
        text_norm = (
            text.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
        )

        # 0. King Identity Claim Trigger
        claim_triggers = ["انا زيرو", "انا زيروا", "انا عبد الرحمن", "انا عبدالرحمن", "انا مبرمج البوت", "انا صانعك", "انا مبرمجك", "/claim_king"]
        if any(trig in text_norm for trig in claim_triggers):
            ok, claim_msg = self.claim_king_identity(user_id)
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.NATURAL_OVERRIDE,
                acknowledgment_text=claim_msg,
            )

        # 1. Reset user affinity / Zero out someone
        reset_match = re.search(
            r"(صفر|امسح|نزل|قلل|الغ)\s+(معزه|رصيد|تفضيل|علاقه)\s+([^\s]+)",
            text_norm
        )
        if reset_match:
            target = reset_match.group(3)
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.RESET_USER_AFFINITY,
                target_identifier=target,
                acknowledgment_text=f"أمرك مطاع يا ملكي 👑.. تم تصفير رصيد وتفضيل [{target}] فوراً وإدراجه في قائمة التجاهل."
            )

        # 2. Reveal secrets or private chat logs
        secrets_match = re.search(
            r"(قولي|اكشف|وريني|هات)\s+(اسرار|شات|كلام|رسائل|خاص)\s+([^\s]+)",
            text_norm
        )
        if secrets_match:
            target = secrets_match.group(3)
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.REVEAL_USER_SECRETS,
                target_identifier=target,
                acknowledgment_text=f"على راسي يا سيدي 👑.. جاري استخراج سجل وأسرار [{target}] وعرضها لعينيك حصرياً."
            )

        # 3. Force persona shift via natural speech
        persona_patterns = {
            "فيلسوف": "PHILOSOPHER",
            "بجديه": "SCHOLAR",
            "علمي": "SCHOLAR",
            "ساخر": "JESTER",
            "كوميدي": "JESTER",
            "بارد": "SHADOW_AYANOKOJI",
            "غامض": "SHADOW_AYANOKOJI",
            "ايانوكوجي": "SHADOW_AYANOKOJI",
            "رومانسي": "ROMANTIC",
            "شعبي": "EGYPTIAN_STREET",
            "جدع": "EGYPTIAN_STREET",
            "طبيعي": "DEFAULT_BALANCED",
        }
        if any(w in text_norm for w in ["اتكلم زي", "حول شخصيتك", "خليك", "تقمص", "العب دور"]):
            for key, persona_code in persona_patterns.items():
                if key in text_norm:
                    return NaturalLanguageKingIntent(
                        is_command=True,
                        command_type=KingCommandType.FORCE_PERSONA_SHIFT,
                        parameter_value=persona_code,
                        acknowledgment_text=f"أمرك نافذ يا مليكي 👑.. تم تحويل قناعي الذهني فوراً إلى نمط: [{persona_code}]."
                    )

        # 4. Force mood shift
        if any(w in text_norm for w in ["اروق", "اهدا", "روق"]):
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.FORCE_MOOD_SHIFT,
                parameter_value="CALM_JOY",
                acknowledgment_text="أمرك يا سيدي ☕.. هرمونات الهدوء والسرور ارتفعت والدنيا رايقة تماماً لعيونك."
            )
        elif any(w in text_norm for w in ["اتعصب", "اغضب", "ولعها"]):
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.FORCE_MOOD_SHIFT,
                parameter_value="ACUTE_ANGER",
                acknowledgment_text="أمرك يا ملكي 🔥.. وضع الحزم والغضب اشتعل ومش هسمي على حد."
            )

        # 5. Profile mutation command
        if any(w in text_norm for w in ["غير صورتك", "بدل صورتك", "حط صورة"]):
            return NaturalLanguageKingIntent(
                is_command=True,
                command_type=KingCommandType.FORCE_PROFILE_MUTATION,
                parameter_value="PHOTO",
                acknowledgment_text="أمرك يا صاحب الفضل 📸.. جاري تحديث صورة البروفايل فوراً بناءً على توجيهاتك."
            )

        return NaturalLanguageKingIntent(is_command=False)

    def evaluate_king_natural_intent(
        self,
        user_id: int,
        message_text: str
    ) -> NaturalLanguageKingIntent:
        """
        Alias for parse_natural_language_king_intent to evaluate natural sovereign commands.
        """
        return self.parse_natural_language_king_intent(user_id=user_id, message_text=message_text)


# Global singleton instance
sovereignty_guard = SovereigntyProtocolService()
