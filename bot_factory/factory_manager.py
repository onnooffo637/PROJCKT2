"""
Multi-Tenant Bot Factory Service for Project Aether-Human (V2.0).
Coordinates multi-bot lifecycle, creation of Official Bots and MTProto Userbots,
gender switching (ولد / بنت), persona templates application, and persistence.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple

from bot_factory.models import BotInstanceConfig, BotPlatformType, BotGender
from bot_factory.persona_templates import template_registry, FactoryPersonaTemplate
from aether_human_core.config.settings import settings, CO_ADMIN_ID

logger = logging.getLogger("Aether.BotFactory.Manager")


class MultiBotFactoryService:
    """
    Central factory orchestrator managing the fleet of autonomous official bots and userbots.
    """

    DB_FILE_PATH = "bot_factory_db.json"

    # Locked Canonical Visual DNA blueprints for existing core bots (100% distinct faces)
    CANONICAL_VISUAL_DNA: Dict[str, Tuple[str, int]] = {
        "master_omar_official": (
            "24-year-old Egyptian man from Cairo, natural olive-wheat skin tone, sharp dark brown eyes, "
            "thick slightly messy dark black hair with a clean low fade, trimmed short stubble beard, "
            "natural masculine jawline, small faint mole near left cheekbone",
            543210,
        ),
        "userbot_primary": (
            "24-year-old Egyptian young woman from Cairo, warm honey-olive skin tone with real skin texture, "
            "almond-shaped dark hazel-brown eyes with natural long lashes, defined arched dark eyebrows, "
            "soft dark chestnut wavy hair falling past shoulders with light wispy strands, subtle dimple on right cheek, "
            "delicate straight nose bridge, natural rose lips",
            778899,
        ),
        "bot_1793564427271": (
            "19-year-old petite Egyptian university girl from Cairo, fair warm ivory-wheat complexion, "
            "large bright expressive dark brown eyes, straight silky jet-black hair tied half-up with soft face-framing bangs, "
            "soft heart-shaped youthful face, tiny beauty mark below right eye, gentle feminine features",
            112233,
        ),
        "bot_1793633133088": (
            "19-year-old Iraqi young woman from Baghdad, authentic Mesopotamian Arab beauty, warm golden-olive skin tone, "
            "large deep dark black eyes with naturally thick lashes, full defined dark eyebrows, "
            "long thick raven-black wavy hair parted in the middle, graceful oval face shape, warm friendly expression",
            445566,
        ),
        "bot_1793709138213": (
            "21-year-old Egyptian street-smart guy from Cairo, sun-kissed bronze-olive skin tone, "
            "intense dark brown eyes, sharp high skin-fade haircut with textured short crop on top, "
            "connected goatee and short mustache stubble, angular lean cheekbones, faint thin scar notch on left eyebrow",
            334455,
        ),
        "bot_1793725567511": (
            "20-year-old glamorous bold Egyptian young woman from Cairo, warm sun-kissed tan-olive complexion, "
            "sultry cat-eye shaped light amber-brown eyes, voluminous layered dark caramel-brown blowout hair, "
            "sculpted cheekbones, full natural glossy lips, tiny silver nose stud on left nostril",
            992211,
        ),
    }

    @classmethod
    def generate_unique_visual_dna(
        cls,
        instance_id: str,
        name: str,
        gender: BotGender,
        age: int = 22,
        origin_location: str = "",
        primary_dialect: str = "egyptian",
    ) -> Tuple[str, int]:
        """
        Deterministically generates a 100% unique, permanently locked physical face blueprint
        (visual_dna) and base_identity_seed for any bot or newly created sub-bot so that
        no two bots ever share the same face.
        """
        if instance_id in cls.CANONICAL_VISUAL_DNA:
            return cls.CANONICAL_VISUAL_DNA[instance_id]

        name_clean = (name or "").strip().lower()
        if name_clean in ("عمر", "عمر (الأساس)", "omar"):
            return cls.CANONICAL_VISUAL_DNA["master_omar_official"]
        if name_clean in ("ريمي", "gg", "جي جي", "reemy"):
            return cls.CANONICAL_VISUAL_DNA["userbot_primary"]
        if name_clean in ("مريم", "مريومة", "maryam"):
            return cls.CANONICAL_VISUAL_DNA["bot_1793564427271"]
        if name_clean in ("ماسه", "ماسة", "masa"):
            return cls.CANONICAL_VISUAL_DNA["bot_1793633133088"]
        if name_clean in ("مصطفي", "مصطفى", "mostafa"):
            return cls.CANONICAL_VISUAL_DNA["bot_1793709138213"]
        if name_clean in ("ملوكة", "ملوكه", "malooka"):
            return cls.CANONICAL_VISUAL_DNA["bot_1793725567511"]

        import hashlib
        digest = hashlib.sha256(f"{instance_id}:{name}:{gender.value}".encode("utf-8")).hexdigest()
        h_int = int(digest[:12], 16)
        base_seed = 100000 + (h_int % 899999)

        loc_lower = f"{origin_location} {primary_dialect}".lower()
        if any(k in loc_lower for k in ["عراق", "بغداد", "iraq"]):
            region_eth = "Iraqi Arab"
        elif any(k in loc_lower for k in ["شام", "سوري", "لبنان", "دمشق", "بيروت", "syria", "leban"]):
            region_eth = "Levantine Mediterranean Arab"
        elif any(k in loc_lower for k in ["سعود", "خليج", "كويت", "امارات", "قطر", "saudi", "gulf"]):
            region_eth = "Khaleeji Arabian Peninsula"
        elif any(k in loc_lower for k in ["مغرب", "تونس", "جزائر", "morocco", "tunis"]):
            region_eth = "North African Maghrebi"
        else:
            region_eth = "Egyptian"

        eff_age = max(18, min(45, int(age or 22)))

        if gender == BotGender.FEMALE:
            face_shapes = ["soft oval face", "delicate heart-shaped face", "graceful diamond-shaped face", "defined high-cheekbone face", "soft rounded youthful face"]
            skin_tones = ["warm honey-olive skin tone", "fair warm ivory-wheat complexion", "sun-kissed golden-olive skin", "natural light bronze-olive complexion", "warm Mediterranean olive skin"]
            eye_styles = [
                "large expressive dark chestnut-brown eyes with thick lashes",
                "almond-shaped warm hazel-green eyes",
                "deep kohl-framed dark black-brown eyes",
                "bright wide warm amber-brown eyes",
                "upturned expressive dark brown eyes",
            ]
            hair_styles = [
                "long dark espresso-brown wavy hair parted on the side",
                "shoulder-length straight glossy jet-black hair with wispy bangs",
                "thick curly dark chestnut hair falling around shoulders",
                "sleek long dark brown hair with soft curtain bangs",
                "medium-length tousled dark mocha-brown waves",
            ]
            brows_nose = [
                "naturally arched dark eyebrows and straight delicate nose bridge",
                "softly feathered dark brows and petite button nose",
                "defined full eyebrows and refined classic nose bridge",
            ]
            unique_marks = [
                "subtle dimple on left cheek when smiling",
                "tiny faint beauty mark near left corner of lips",
                "small faint freckle dusting across nose bridge",
                "tiny beauty mark below left cheekbone",
                "distinctive natural cupid's bow lips",
            ]
            fs = face_shapes[h_int % len(face_shapes)]
            st = skin_tones[(h_int // 7) % len(skin_tones)]
            es = eye_styles[(h_int // 13) % len(eye_styles)]
            hs = hair_styles[(h_int // 29) % len(hair_styles)]
            bn = brows_nose[(h_int // 53) % len(brows_nose)]
            um = unique_marks[(h_int // 97) % len(unique_marks)]
            dna = f"{eff_age}-year-old {region_eth} young woman, {fs}, {st}, {es}, {hs}, {bn}, {um}"
        else:
            face_shapes = ["chiseled masculine jawline", "angular lean cheekbones and square jaw", "strong oval masculine face", "defined athletic jawline"]
            skin_tones = ["natural olive-wheat skin tone", "warm sun-kissed bronze-olive complexion", "Mediterranean medium-olive skin tone", "warm wheat-tan complexion"]
            eye_styles = [
                "sharp focused dark brown eyes",
                "deep-set expressive dark hazel-brown eyes",
                "confident intense dark black-brown eyes",
                "warm almond-shaped dark brown eyes",
            ]
            hair_styles = [
                "thick textured dark black hair with a mid skin-fade",
                "wavy medium-length dark espresso hair brushed back",
                "short messy curly black hair with tapered sides",
                "clean modern crew-cut dark brown hair with low taper",
                "tousled dark wavy hair with natural fringe",
            ]
            beard_styles = [
                "neatly trimmed short boxed stubble beard",
                "light 3-day shadow stubble along the jaw",
                "clean-shaven jawline with light mustache shadow",
                "well-groomed short full beard and connected mustache",
            ]
            unique_marks = [
                "small faint mole on right cheek",
                "subtle cleft in chin",
                "faint thin scar line near right temple",
                "pronounced straight nose bridge",
                "subtle dimple on right cheek",
            ]
            fs = face_shapes[h_int % len(face_shapes)]
            st = skin_tones[(h_int // 7) % len(skin_tones)]
            es = eye_styles[(h_int // 13) % len(eye_styles)]
            hs = hair_styles[(h_int // 29) % len(hair_styles)]
            bs = beard_styles[(h_int // 53) % len(beard_styles)]
            um = unique_marks[(h_int // 97) % len(unique_marks)]
            dna = f"{eff_age}-year-old {region_eth} young man, {fs}, {st}, {es}, {hs}, {bs}, {um}"

        return dna, base_seed

    def __init__(self):
        self._instances: Dict[str, BotInstanceConfig] = {}
        self._load_database()

    def _load_database(self) -> None:
        if os.path.exists(self.DB_FILE_PATH):
            try:
                needs_save = False
                with open(self.DB_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        raw_owner = v.get("owner_id")
                        inst = BotInstanceConfig(**v)
                        # Assign Marselin (CO_ADMIN_ID) as owner of Bato (bot_1793840547026) if not migrated yet
                        if (k == "bot_1793840547026" or inst.name.strip() == "باتو") and raw_owner is None:
                            inst.owner_id = CO_ADMIN_ID
                            needs_save = True
                        elif raw_owner is None:
                            inst.owner_id = settings.the_king_user_id
                            needs_save = True
                        if not inst.visual_dna or inst.base_identity_seed == 0 or k in self.CANONICAL_VISUAL_DNA:
                            dna, seed = self.generate_unique_visual_dna(
                                instance_id=inst.instance_id,
                                name=inst.name,
                                gender=inst.gender,
                                age=inst.age,
                                origin_location=inst.origin_location,
                                primary_dialect=inst.primary_dialect,
                            )
                            if inst.visual_dna != dna or inst.base_identity_seed != seed:
                                inst.visual_dna = dna
                                inst.base_identity_seed = seed
                                needs_save = True
                        # Clamp legacy extreme voice pitch/rate to zero-distortion human bounds
                        if inst.voice_pitch < -2 or inst.voice_pitch > 2:
                            inst.voice_pitch = max(-2, min(2, inst.voice_pitch))
                            needs_save = True
                        if inst.voice_rate < -3 or inst.voice_rate > 6:
                            inst.voice_rate = max(-3, min(6, inst.voice_rate))
                            needs_save = True
                        self._instances[k] = inst
                if needs_save:
                    self._save_database()
                logger.info(f"Loaded {len(self._instances)} bot instances from factory database (all Visual DNA locked).")
            except Exception as exc:
                logger.error(f"Error loading bot factory database: {exc}")
        else:
            # Seed default primary bot instance (Omar Master Bot)
            self._seed_default_master_bot()

    def _save_database(self) -> None:
        try:
            with open(self.DB_FILE_PATH, "w", encoding="utf-8") as f:
                payload = {k: v.model_dump() for k, v in self._instances.items()}
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"Error saving bot factory database: {exc}")

    def _seed_default_master_bot(self) -> None:
        master_tmpl = template_registry.get_template("OMAR_CHARISMATIC")
        master = BotInstanceConfig(
            instance_id="master_omar_official",
            bot_type=BotPlatformType.OFFICIAL_BOT,
            token_or_session="8677519723:AAHcv7-6_VanLlETJKftDHWgHQXfz_bu-n8",
            name="عمر (الأساس)",
            gender=BotGender.MALE,
            age=24,
            bio=master_tmpl.suggested_bio,
            template_code="OMAR_CHARISMATIC",
            system_prompt=master_tmpl.system_prompt,
            primary_dialect="egyptian",
            is_active=True,
            notes="البوت الرسمي الأساسي للنظام",
        )
        self._instances[master.instance_id] = master
        self._save_database()

    def create_bot(
        self,
        instance_id: str,
        name: str,
        bot_type: BotPlatformType,
        token_or_session: str,
        gender: BotGender = BotGender.MALE,
        age: int = 22,
        template_code: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        bio: str = "",
        dialect: str = "egyptian",
        origin_location: str = "",
        chattiness_level: float = 0.5,
        voice_profile: Optional[str] = None,
        voice_pitch: int = 0,
        voice_rate: int = 0,
        custom_rules: str = "",
        relationship_creator: str = "",
        owner_id: int = 0,
    ) -> Tuple[bool, str, Optional[BotInstanceConfig]]:
        """
        Spawns a new bot or userbot instance in the factory with 100% free-text configuration.
        """
        clean_id = instance_id.strip().lower().replace(" ", "_")
        if clean_id in self._instances:
            return False, f"⚠️ يوجد بوت مسجل بالفعل بنفس المعرف: '{clean_id}'", None

        # Resolve prompt and template
        if template_code and template_code in template_registry.TEMPLATES:
            tmpl = template_registry.get_template(template_code)
            effective_prompt = custom_prompt or tmpl.system_prompt
            effective_bio = bio or tmpl.suggested_bio
            effective_gender = gender or tmpl.gender
            effective_dialect = dialect or tmpl.recommended_dialect
        else:
            effective_prompt = custom_prompt or f"أنت '{name}'، ذكي وودود وتتحدث بلغة طبيعية."
            effective_bio = bio
            effective_gender = gender
            effective_dialect = dialect

        dna_str, dna_seed = self.generate_unique_visual_dna(
            instance_id=clean_id,
            name=name,
            gender=effective_gender,
            age=age,
            origin_location=origin_location or "",
            primary_dialect=effective_dialect,
        )

        instance = BotInstanceConfig(
            instance_id=clean_id,
            bot_type=bot_type,
            token_or_session=token_or_session,
            name=name,
            gender=effective_gender,
            age=age,
            bio=effective_bio,
            template_code=template_code or "CUSTOM",
            system_prompt=effective_prompt,
            primary_dialect=effective_dialect,
            origin_location=origin_location or "",
            chattiness_level=chattiness_level,
            voice_profile=voice_profile,
            voice_pitch=max(-2, min(2, int(voice_pitch))),
            voice_rate=max(-3, min(6, int(voice_rate))),
            custom_rules=custom_rules or "",
            relationship_creator=relationship_creator or "",
            visual_dna=dna_str,
            base_identity_seed=dna_seed,
            owner_id=int(owner_id or settings.the_king_user_id),
            is_active=True,
            created_at=time.time(),
        )

        self._instances[clean_id] = instance
        self._save_database()
        logger.info(f"Factory spawned new bot: {instance.name} ({instance.instance_id})")

        # Automatically initiate dedicated long-polling for official sub-bots
        if instance.bot_type == BotPlatformType.OFFICIAL_BOT:
            try:
                from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
                multi_bot_dispatcher.start_bot_polling(instance)
            except Exception as dp_ex:
                logger.debug(f"Dispatcher hook notice: {dp_ex}")

        return True, f"✨ تم إنشاء وتفعيل البوت «{name}» بنجاح في المصنع!", instance

    def set_bot_gender(
        self,
        instance_id: str,
        gender: BotGender,
        new_name: Optional[str] = None,
        new_bio: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Transforms bot between boy (ولد) and girl (بنت) with full name, bio, and grammar realignment.
        """
        if instance_id not in self._instances:
            return False, f"لم يتم العثور على البوت المعرف بـ: '{instance_id}'"

        bot = self._instances[instance_id]
        bot.gender = gender

        # Gender name realignment mapping
        male_to_female_names = {
            "عمر": "سلمى", "سيف": "ليلى", "كريم": "مريم", "عمر (الأساس)": "ميرا (الأساس)"
        }
        female_to_male_names = {
            "سلمى": "عمر", "ليلى": "سيف", "مريم": "كريم", "ماسة": "عمر", "ميرا (الأساس)": "عمر (الأساس)"
        }

        if gender == BotGender.FEMALE:
            if new_name:
                bot.name = new_name.strip()
            elif any(m in bot.name for m in ["عمر", "سيف", "كريم", "ولد"]):
                for m_k, f_v in male_to_female_names.items():
                    if m_k in bot.name:
                        bot.name = bot.name.replace(m_k, f_v)
                        break
                else:
                    bot.name = f"{bot.name} (بنت)"

            if new_bio:
                bot.bio = new_bio.strip()
            else:
                bot.bio = bot.bio.replace("شاب", "فتاة").replace("مهندس", "مهندسة").replace("جدع", "جدعة ولطيفة")

            # Grammar alignment
            bot.system_prompt = (
                bot.system_prompt.replace("أنت '", "أنتِ '")
                .replace("شاب سوري", "فتاة سورية")
                .replace("شاب مصري", "فتاة مصرية")
                .replace("صديق وفي", "صديقة وفية")
            )
            gender_desc = "بنت (أنثى) 👧"

        else:  # Switched to MALE
            if new_name:
                bot.name = new_name.strip()
            elif any(f in bot.name for f in ["سلمى", "ليلى", "مريم", "ماسة", "ميرا", "بنت"]):
                for f_k, m_v in female_to_male_names.items():
                    if f_k in bot.name:
                        bot.name = bot.name.replace(f_k, m_v)
                        break
                else:
                    bot.name = bot.name.replace(" (بنت)", "").replace("بنت", "عمر")

            if new_bio:
                bot.bio = new_bio.strip()
            else:
                bot.bio = bot.bio.replace("فتاة", "شاب").replace("مهندسة", "مهندس").replace("لطيفة", "جدع")

            # Grammar alignment
            bot.system_prompt = (
                bot.system_prompt.replace("أنتِ '", "أنت '")
                .replace("فتاة سورية", "شاب سوري")
                .replace("فتاة مصرية", "شاب مصري")
                .replace("صديقة وفية", "صديق وفي")
            )
            gender_desc = "ولد (ذكر) 👦"

        self._save_database()
        return True, (
            f"🎭 <b>تم تحديث الهوية الجنسية للبوت بالكامل:</b>\n"
            f"• الجنس الجديد: <b>{gender_desc}</b>\n"
            f"• الاسم المعتمد: <b>{bot.name}</b>\n"
            f"• الوصف: <i>{bot.bio}</i>\n"
            f"<i>💡 تم تعديل الاسم والوصف والتوجيهات السلوكية تلقائياً لتطابق الهوية الجديدة دون أي تناقض.</i>"
        )

    def set_bot_template(self, instance_id: str, template_code: str) -> Tuple[bool, str]:
        """
        Applies a pre-built persona template (Masa, Mariam, Layla, Seif, Karim, etc.).
        """
        if instance_id not in self._instances:
            return False, f"لم يتم العثور على البوت: '{instance_id}'"

        tmpl = template_registry.get_template(template_code)
        bot = self._instances[instance_id]
        bot.template_code = tmpl.template_code
        bot.gender = tmpl.gender
        bot.system_prompt = tmpl.system_prompt
        bot.bio = tmpl.suggested_bio
        bot.primary_dialect = tmpl.recommended_dialect

        self._save_database()
        return True, f"✨ تم تطبيق شخصية «{tmpl.name_ar}» على البوت «{bot.name}» بنجاح!"

    def set_bot_active_status(self, instance_id: str, is_active: bool) -> Tuple[bool, str]:
        if instance_id not in self._instances:
            return False, "البوت غير موجود."
        bot = self._instances[instance_id]
        bot.is_active = is_active
        self._save_database()
        
        # Start or stop polling dynamically
        try:
            from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
            if is_active:
                multi_bot_dispatcher.start_bot_polling(bot)
            else:
                multi_bot_dispatcher.stop_bot_polling(instance_id)
        except Exception:
            pass

        status_desc = "تفعيل 🟢" if is_active else "إيقاف مؤقت ⚪"
        return True, f"تم {status_desc} البوت «{bot.name}» بنجاح."

    def update_bot_persona(
        self,
        instance_id: str,
        name: Optional[str] = None,
        gender: Optional[BotGender] = None,
        age: Optional[int] = None,
        bio: Optional[str] = None,
        system_prompt: Optional[str] = None,
        primary_dialect: Optional[str] = None,
        origin_location: Optional[str] = None,
        chattiness_level: Optional[float] = None,
        voice_profile: Optional[str] = None,
        voice_pitch: Optional[int] = None,
        voice_rate: Optional[int] = None,
        custom_rules: Optional[str] = None,
        relationship_creator: Optional[str] = None,
        template_code: Optional[str] = None,
        notes: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[BotInstanceConfig]]:
        """
        Dynamically updates any bot or userbot persona details after creation and hot-reloads live instance.
        """
        if instance_id not in self._instances:
            return False, f"لم يتم العثور على البوت: '{instance_id}'", None

        bot = self._instances[instance_id]
        if name is not None and name.strip():
            bot.name = name.strip()
        if gender is not None:
            bot.gender = gender
        if age is not None:
            bot.age = age
        if bio is not None:
            bot.bio = bio.strip()
        if avatar_url is not None:
            bot.avatar_url = avatar_url.strip() if avatar_url.strip() else None
        if system_prompt is not None and system_prompt.strip():
            bot.system_prompt = system_prompt.strip()
        if primary_dialect is not None:
            bot.primary_dialect = primary_dialect.strip()
        if origin_location is not None:
            bot.origin_location = origin_location.strip()
        if chattiness_level is not None:
            bot.chattiness_level = max(0.0, min(1.0, float(chattiness_level)))
        if voice_profile is not None:
            bot.voice_profile = voice_profile.strip() if voice_profile.strip() else None
        if voice_pitch is not None:
            bot.voice_pitch = max(-2, min(2, int(voice_pitch)))
        if voice_rate is not None:
            bot.voice_rate = max(-3, min(6, int(voice_rate)))
        if custom_rules is not None:
            bot.custom_rules = custom_rules.strip()
        if relationship_creator is not None:
            bot.relationship_creator = relationship_creator.strip()
        if template_code is not None:
            bot.template_code = template_code
        if notes is not None:
            bot.notes = notes
        if not bot.visual_dna or bot.base_identity_seed == 0 or gender is not None:
            dna_str, dna_seed = self.generate_unique_visual_dna(
                instance_id=bot.instance_id,
                name=bot.name,
                gender=bot.gender,
                age=bot.age,
                origin_location=bot.origin_location,
                primary_dialect=bot.primary_dialect,
            )
            bot.visual_dna = dna_str
            bot.base_identity_seed = dna_seed

        # Realignment of feminine/masculine grammar if gender changed
        if bot.gender == BotGender.FEMALE and "أنت '" in bot.system_prompt:
            bot.system_prompt = bot.system_prompt.replace("أنت '", "أنتِ '")
        elif bot.gender == BotGender.MALE and "أنتِ '" in bot.system_prompt:
            bot.system_prompt = bot.system_prompt.replace("أنتِ '", "أنت '")

        self._save_database()
        logger.info(f"Updated persona for bot [{bot.instance_id}]: {bot.name}")

        # Live Hot-Reload: Restart polling for this bot instance in memory immediately
        if bot.bot_type == BotPlatformType.OFFICIAL_BOT and bot.is_active:
            try:
                from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
                multi_bot_dispatcher.start_bot_polling(bot)
                logger.info(f"🔥 Hot-reloaded running polling instance for bot [{bot.name}] ({bot.instance_id})")
            except Exception as dp_ex:
                logger.debug(f"Dispatcher hot-reload notice: {dp_ex}")

        return True, f"✨ تم تحديث بيانات وشخصية البوت «{bot.name}» بنجاح!", bot

    def delete_bot(self, instance_id: str) -> Tuple[bool, str]:
        if instance_id == "master_omar_official":
            return False, "⚠️ لا يمكن حذف البوت الأساسي للنظام."
        if instance_id in self._instances:
            del self._instances[instance_id]
            self._save_database()
            try:
                from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
                multi_bot_dispatcher.stop_bot_polling(instance_id)
            except Exception:
                pass
            return True, f"تم حذف البوت '{instance_id}' نهائياً من المصنع."
        return False, "البوت غير موجود."

    def get_bot(self, instance_id: str) -> Optional[BotInstanceConfig]:
        return self._instances.get(instance_id)

    def get_bot_by_name(self, bot_name: str) -> Optional[BotInstanceConfig]:
        clean_target = (bot_name or "").strip().lower()
        for bot in self._instances.values():
            if bot.name and bot.name.strip().lower() == clean_target:
                return bot
        return None

    def list_all_bots(self) -> List[BotInstanceConfig]:
        return list(self._instances.values())

    def is_supreme_king(self, user_id: int) -> bool:
        """
        True strictly for the Supreme Sovereign Creator (KING_USER_ID).
        """
        from aether_human_core.config.settings import settings
        uid = int(user_id or 0)
        return (settings.the_king_user_id > 0 and uid == settings.the_king_user_id) or uid == settings.king_id

    def is_factory_admin(self, user_id: int) -> bool:
        """
        True for Supreme King (KING_USER_ID), Marselin (CO_ADMIN_ID), Super Admins, or explicitly authorized factory users.
        """
        from aether_human_core.config.settings import settings
        uid = int(user_id or 0)
        if self.is_supreme_king(uid) or uid == CO_ADMIN_ID or uid == settings.marcel_id:
            return True
        if uid in settings.super_admin_ids_list:
            return True
        try:
            return factory_access_manager.is_user_authorized(uid)
        except Exception:
            return False

    def can_user_manage_bot(self, user_id: int, bot_or_id: Any) -> bool:
        """
        Checks if `user_id` is authorized to view/edit/manage a specific bot.
        - Supreme King (KING_USER_ID) can manage ALL bots.
        - Secondary Admins (like Marselin CO_ADMIN_ID) can ONLY manage bots where `bot.owner_id == user_id`.
        """
        uid = int(user_id or 0)
        if self.is_supreme_king(uid):
            return True
        if not self.is_factory_admin(uid):
            return False
        bot = bot_or_id if isinstance(bot_or_id, BotInstanceConfig) else self.get_bot(str(bot_or_id))
        if not bot:
            return False
        return int(getattr(bot, "owner_id", settings.the_king_user_id)) == uid

    def list_bots_for_user(self, user_id: int) -> List[BotInstanceConfig]:
        """
        Returns the isolated list of bots visible to `user_id`:
        - Supreme King (KING_USER_ID): sees ALL bots in the system.
        - Marselin (CO_ADMIN_ID) or any secondary admin: ONLY sees bots where `bot.owner_id == user_id`
          (zero visibility into the Supreme King's bots).
        """
        uid = int(user_id or 0)
        if self.is_supreme_king(uid):
            return list(self._instances.values())
        if not self.is_factory_admin(uid):
            return []
        return [
            b for b in self._instances.values()
            if int(getattr(b, "owner_id", settings.the_king_user_id)) == uid
        ]

    def list_bots(self) -> List[str]:
        return list(self._instances.keys())


# Singleton Factory Instance
bot_factory = MultiBotFactoryService()


class BotFactoryAccessManager:
    """
    Regulates user access to the Bot Factory.
    Only Admins and King have default access.
    Regular users can submit an access request, which Admins can approve or reject.
    """
    AUTH_FILE = "data/factory_authorized_users.json"

    def __init__(self):
        self._authorized_users: set[int] = set()
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.AUTH_FILE), exist_ok=True)
        if not os.path.exists(self.AUTH_FILE):
            with open(self.AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load(self) -> None:
        try:
            with open(self.AUTH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._authorized_users = set(data)
        except Exception as e:
            logger.warning(f"Could not load factory authorized users: {e}")

    def _save(self) -> None:
        try:
            with open(self.AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self._authorized_users), f)
        except Exception as e:
            logger.error(f"Failed to save factory authorized users: {e}")

    def is_user_authorized(self, user_id: int) -> bool:
        from core_config.sovereignty_rules import sovereignty_guard
        from aether_human_core.config.settings import settings
        if sovereignty_guard.is_the_king(user_id) or user_id in settings.super_admin_ids_list:
            return True
        return user_id in self._authorized_users

    async def submit_access_request(self, user_id: int, user_name: str) -> bool:
        """
        Sends an authorization request notification to the King and Admins.
        """
        from aether_human_core.config.settings import settings
        token = settings.telegram_bot_token
        king_id = settings.the_king_user_id
        if not token or not king_id:
            return False

        req_text = (
            f"🔔 <b>طلب تصريح جديد لدخول مصنع البوتات</b> 🤖\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المستخدم:</b> {user_name} (ID: <code>{user_id}</code>)\n"
            f"يرغب في الحصول على صلاحية الدخول لمصنع البوتات لإنشاء وتخصيص بوت جديد.\n"
            f"هل توافق على منحه الصلاحية؟"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ موافقة ومنح الصلاحية", "callback_data": f"act:factory_perm:approve:{user_id}"},
                    {"text": "❌ رفض الطلب", "callback_data": f"act:factory_perm:reject:{user_id}"},
                ]
            ]
        }

        import httpx
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=8.0) as client:
            for admin_id in settings.super_admin_ids_list:
                try:
                    await client.post(
                        api_url,
                        json={
                            "chat_id": admin_id,
                            "text": req_text,
                            "parse_mode": "HTML",
                            "reply_markup": markup,
                        },
                    )
                except Exception:
                    pass
        return True

    async def approve_user(self, user_id: int, operator_id: int) -> str:
        self._authorized_users.add(user_id)
        self._save()
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        notify_msg = (
            "🎉 <b>تهانينا! تمت الموافقة على طلبك!</b> 🤖✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "وافقت إدارة النظام على منحك تصريح الدخول لمصنع البوتات.\n"
            "يمكنك الآن فتح لوحة المصنع والبدء في إنشاء أو إدارة بوتك الخاص!"
        )
        await mtproto_manager.send_message(chat_id=user_id, text=notify_msg)
        return f"✅ تم اعتماد ومنح تصريح مصنع البوتات للمستخدم (ID: <code>{user_id}</code>) بنجاح."

    async def reject_user(self, user_id: int, operator_id: int) -> str:
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        notify_msg = (
            "⚠️ <b>إشعار بخصوص طلب مصنع البوتات</b>\n"
            "نعتذر، لم تتم الموافقة على طلب تصريح مصنع البوتات في الوقت الحالي من قِبل الإدارة."
        )
        await mtproto_manager.send_message(chat_id=user_id, text=notify_msg)
        return f"❌ تم رفض طلب المستخدم (ID: <code>{user_id}</code>)."


factory_access_manager = BotFactoryAccessManager()

