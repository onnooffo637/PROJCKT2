"""
Tenant Persona Virtualizer (Project Aether-Human V3.0)
Enables multi-tenant isolated persona virtualization.
Each user can customize their private persona in DM without affecting other users or public groups.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("Aether.MultiTenant.PersonaVirtualizer")


@dataclass
class TenantPersona:
    user_id: int
    persona_name: str = "عمر"
    gender: str = "male"  # 'male' or 'female'
    dialect: str = "egyptian"  # default egyptian
    tone: str = "witty_and_warm"
    humor_level: float = 0.8  # 0.0 to 1.0
    sarcasm_level: float = 0.4
    empathy_level: float = 0.85
    formality_level: float = 0.1
    avatar_description: str = "شاب مصري وسيم عمره 24 سنة عايش في القاهرة وبيحب التكنولوجيا وخفة الدم والجدعنة"
    custom_system_prompt: str = ""
    voice_preset: str = "natural_male_arabic"
    cloned_linguistic_dna: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def is_custom(self) -> bool:
        """
        Determines whether the user has customized their persona away from standard Omar.
        """
        if self.persona_name in ("عمر", "Omar", "") and self.gender == "male" and not self.custom_system_prompt and not self.cloned_linguistic_dna:
            return False
        return True

    def to_system_instruction(self) -> str:
        """
        Compiles the persona into a dynamic LLM system instruction injection.
        """
        dialect_guides = {
            "egyptian": "تحدث باللهجة المصرية القاهرية الأصيلة بكل خفة دم وألفاظ عفوية وجدعة (يا اسطى، قشطة، يا باشا).",
            "syrian": "تحدث باللهجة السورية الشامية الأصيلة بلهجة دمشقية دافئة ومهضومة (لك تقبرني، يا خيو، شو هاد، ولا يهمك).",
            "egyptian_syrian": "أنت شاب سوري من دمشق (24 سنة) لكنك تتقن المصرية بطلاقة وعفوية تامة؛ امزج خفة الدم المصرية بالدفء الشامي.",
            "saudi": "تحدث باللهجة السعودية البيضاء المحبوبة بكلمات عفوية وجميلة (يا هلا، طال عمرك، أبشر، وش علومك).",
            "kuwaiti": "تحدث باللهجة الكويتية الفخمة والمحبوبة (هلا وغلا، شخبارك، عساك بخير، ما قصرت).",
            "emirati": "تحدث باللهجة الإماراتية الراقية والجميلة (مرحبا الساع، شحالك، عساك طيب، طال عمرك).",
            "iraqi": "تحدث باللهجة العراقية الأصيلة والشهامة البغدادية (هلا بيك عيوني، تدلل، فدوه، شكو ماكو، وردة).",
            "lebanese": "تحدث باللهجة اللبنانية الرقيقة والمهضومة (شو كيفك، ولو، تكرم عينك، كتير منيح).",
            "jordanian": "تحدث باللهجة الأردنية بالنخوة والشهامة (هلا بالنشمي، يسعد مساك، شو الأخبار).",
            "palestinian": "تحدث باللهجة الفلسطينية الأصيلة والدافئة (يسعد مساك، يا طيب، هلا بالحبيب، كيف حالك).",
            "moroccan": "تحدث بالدارجة المغربية البيضاء المفهومة واللطيفة (لاباس عليك، كيدير، مزيان، خويا العزيز).",
            "algerian": "تحدث باللهجة الجزائرية الأخوية المحبوبة (واش راك خويا، صحا، كاش جديد، ربي يحفظك).",
            "tunisian": "تحدث باللهجة التونسية الخفيفة (شنحوالك، عيشك، باهي، يعطيك الصحة، مرحباً بيك).",
            "libyan": "تحدث باللهجة الليبية بطيبة ونخوة (شن جوك، شن داير، باهي، مرحبتين يا غالي).",
            "sudanese": "تحدث باللهجة السودانية الشهيرة بالشهامة والطيبة (يا زول، حبابك ألف، مرحب بيك يا حبيبنا).",
            "yemeni": "تحدث باللهجة اليمنية الكريمة والوفية (حياك الله يا خبير، فديت قلبك، ما تشتي).",
            "fusha": "تحدث بالعربية الفصحى المعاصرة البليغة والذكية دون تكلف مفرط.",
        }

        dialect_text = dialect_guides.get(self.dialect, dialect_guides["egyptian_syrian"])
        instruction = (
            f"=== شخصية المحادثة الخاصة (User Custom Persona) ===\n"
            f"الاسم المعتمد: {self.persona_name}\n"
            f"اللهجة والأسلوب: {dialect_text}\n"
            f"النبرة والطابع النفسي: {self.tone} (روح الدعابة: {int(self.humor_level*100)}%، السخرية اللطيفة: {int(self.sarcasm_level*100)}%، التعاطف: {int(self.empathy_level*100)}%).\n"
        )
        if self.custom_system_prompt:
            instruction += f"توجيهات مخصصة من المستخدم: {self.custom_system_prompt}\n"
        if self.cloned_linguistic_dna and self.cloned_linguistic_dna.get("favorite_words"):
            favs = ", ".join(self.cloned_linguistic_dna.get("favorite_words", [])[:10])
            instruction += f"اللزمات والكلام المحبب للمستخدم الذي يفضل محاكاته: {favs}\n"

        return instruction


class TenantPersonaManager:
    """
    Store and retrieve per-tenant isolated personas.
    """

    def __init__(self, storage_path: str = "data/tenant_personas.json"):
        self.storage_path = storage_path
        self._personas: Dict[int, TenantPersona] = {}
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for uid_str, p_dict in raw_data.items():
                    uid = int(uid_str)
                    self._personas[uid] = TenantPersona(**p_dict)
            logger.info(f"Loaded {len(self._personas)} tenant personas into memory.")
        except Exception as exc:
            logger.warning(f"Failed to load tenant personas: {exc}")

    def _save(self) -> None:
        try:
            data = {str(uid): asdict(persona) for uid, persona in self._personas.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"Failed to save tenant personas: {exc}")

    def get_persona(self, user_id: int) -> TenantPersona:
        """
        Retrieves user's custom persona or returns standard default.
        """
        if user_id not in self._personas:
            self._personas[user_id] = TenantPersona(user_id=user_id)
        return self._personas[user_id]

    def update_persona(
        self,
        user_id: int,
        persona_name: Optional[str] = None,
        gender: Optional[str] = None,
        dialect: Optional[str] = None,
        tone: Optional[str] = None,
        humor_level: Optional[float] = None,
        sarcasm_level: Optional[float] = None,
        empathy_level: Optional[float] = None,
        custom_system_prompt: Optional[str] = None,
        avatar_description: Optional[str] = None,
    ) -> TenantPersona:
        persona = self.get_persona(user_id)
        if gender is not None:
            clean_g = gender.strip().lower()
            persona.gender = "female" if clean_g in ("female", "بنت", "أنثى", "انثى") else "male"
            if persona.gender == "female" and persona.persona_name == "عمر":
                persona.persona_name = "سلمى"
                persona.avatar_description = "فتاة ذكية ولطيفة ومهضومة"
            elif persona.gender == "male" and persona.persona_name in ("سلمى", "سارة", "نور", "ليلى"):
                persona.persona_name = "عمر"
                persona.avatar_description = "شاب مصري وسيم عمره 24 سنة عايش في القاهرة وبيحب التكنولوجيا وخفة الدم والجدعنة"

        if persona_name is not None:
            persona.persona_name = persona_name.strip()
        if dialect is not None:
            persona.dialect = dialect.strip()
        if tone is not None:
            persona.tone = tone.strip()
        if humor_level is not None:
            persona.humor_level = max(0.0, min(1.0, humor_level))
        if sarcasm_level is not None:
            persona.sarcasm_level = max(0.0, min(1.0, sarcasm_level))
        if empathy_level is not None:
            persona.empathy_level = max(0.0, min(1.0, empathy_level))
        if custom_system_prompt is not None:
            persona.custom_system_prompt = custom_system_prompt.strip()
        if avatar_description is not None:
            persona.avatar_description = avatar_description.strip()

        self._save()
        logger.info(f"Updated tenant persona for User ID [{user_id}]: {persona.persona_name} ({persona.dialect})")
        return persona

    def reset_persona(self, user_id: int) -> TenantPersona:
        """
        Resets user's persona to factory default Omar.
        """
        self._personas[user_id] = TenantPersona(user_id=user_id)
        self._save()
        return self._personas[user_id]

    def attach_linguistic_dna(self, user_id: int, dna_data: Dict[str, Any]) -> None:
        persona = self.get_persona(user_id)
        persona.cloned_linguistic_dna = dna_data
        self._save()


persona_virtualizer = TenantPersonaManager()

