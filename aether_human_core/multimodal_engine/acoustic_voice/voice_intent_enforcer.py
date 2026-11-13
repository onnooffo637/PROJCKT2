"""
Voice & Singing Intent Enforcer (Project Aether-Human - Acoustic Multimodal).
Prevents textual dodging when user asks a bot to sing or send a voice note.
Enforces colloquial phonetic spelling without robotic letter stretching.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from aether_human_core.config.llm_router import llm_pool
from aether_human_core.multimodal_engine.acoustic_voice.realistic_voice_generator import (
    RealisticVoiceGenerator,
    clean_for_human_speech,
)

logger = logging.getLogger("Aether.Multimodal.VoiceIntentEnforcer")


class VoiceIntentEnforcer:
    """
    Enforces immediate execution of voice note and singing requests without dodging,
    and ensures voice scripts are written in authentic street-pronounced phonetics.
    """

    VOICE_TRIGGERS = [
        "فويس", "صوت", "ريكورد", "ريك", "تسجيل", "صوتك", "voice", "record",
        "ابعت فويس", "ابعتلي فويس", "سمعني صوتك", "سمعنا صوتك", "كلمني صوت",
        "ابعت ريكورد", "ابعتلي ريكورد", "عاوز اسمع صوتك", "عايز اسمع صوتك", "صوتك حلو",
        "سمعيني صوتك", "ابعتيلي فويس", "ابعتيلي ريكورد",
    ]

    SINGING_TRIGGERS = [
        "غني", "بتغني", "غنيلي", "غنيلنا", "اغنية", "أغنية", "موال", "دندن", "دندنة", "طرب", "غنيلك", "غنِ", "sing"
    ]

    # Natural rhythmic lyrics with breathing pauses (zero robotic >2 repeated letters!)
    CURATED_SONGS = {
        "نعناع الجنينة": (
            "آه يا ليل... يا نعناع الجنينة، يا المسقي في كفوفه... "
            "ع الشط ترعاني، والورد ناداني... يا ليل يا عين، حبيبي يا أسمر يا سكر... آه يا ليل"
        ),
        "يا مال الشام": (
            "يا مال الشام... يالله يا مالي، طال المطال يا حلوة تعالي... "
            "يا مال الشام على بالي هواكم، سلطان زماني لو عشت معاكم... يا ليل يا عين"
        ),
        "فوق النخل": (
            "فوق النخل فوق... يابا فوق النخل فوق، مدري لمع خده، مدري القمر فوق... "
            "والله ما ريده بالروح أشريه... يا ليل يا عين"
        ),
        "حبيبي يا نور العين": (
            "حبيبي يا نور العين... يا ساكن خيالي، عاشق بقالي سنين، ولا غيرك في بالي... "
            "حبيبي، حبيبي يا نور العين... أحلى دندنة وروقان"
        ),
        "سيرة الحب": (
            "طول عمري بخاف من الحب، وسيرة الحب، وظلم الحب لكل أصحابه... "
            "وأعرف حكايات مليانة آهات... ودموع وأنين، يا عيني ع الحب"
        ),
    }

    @classmethod
    def clean_text_for_tts(cls, text: str, dialect: str = "egyptian", is_singing: bool = False) -> str:
        """
        Delegates to Spoken-Colloquial Phonetic Pre-Processor (`clean_for_human_speech`)
        to collapse letter stretching, strip emojis/markdown, apply street phonetics,
        and inject natural 4–7 word breath pauses.
        """
        return clean_for_human_speech(
            text=text,
            dialect=dialect,
            is_singing=is_singing,
            inject_breathing=(not is_singing),
        )

    @classmethod
    def get_voice_script_llm_instruction(
        cls,
        dialect_code: str = "egyptian",
        persona_name: str = "عمر",
        is_female: bool = False,
    ) -> str:
        """
        Returns a strict LLM instruction block when generating a script meant for TTS / Voice Note,
        requiring street-pronounced colloquial phonetic spelling and natural human fillers.
        """
        dl = (dialect_code or "egyptian").lower()
        if any(k in dl for k in ["عراق", "iraq", "بغداد"]):
            phonetic_examples = "اكتب الكلمات كما تُنطق في الشارع العراقي البغدادي بالضبط (مثل: 'هسه'، 'شلونك'، 'كلش'، 'هواية'، 'فدوة'، 'صدك') مع لزمات تنفس بشرية ('يعني...'، 'شوف...'، 'والله...')."
        elif any(k in dl for k in ["شام", "سوري", "لبنان", "syria", "leban"]):
            phonetic_examples = "اكتب الكلمات كما تُنطق في الشارع الشامي بالضبط (مثل: 'هلأ'، 'كتير'، 'سواني'، 'دايماً'، 'شو') مع لزمات بشرية طبيعية ('يعني...'، 'ليك...'، 'والله...')."
        elif any(k in dl for k in ["سعود", "خليج", "saudi", "gulf"]):
            phonetic_examples = "اكتب الكلمات كما تُنطق باللهجة الخليجية بالضبط (مثل: 'الحين'، 'شلون'، 'واجد'، 'دايم') مع لزمات بشرية طبيعية ('يعني...'، 'شوف...'، 'والله...')."
        else:
            if is_female:
                phonetic_examples = (
                    "تحدثي كبنت مصرية حقيقية 100%، بصوت هادي وناعم ودافئ جداً، بكلام الشارع المصري التلقائي الحنون:\n"
                    "- اكتبي عبارات قصيرة وحميمية من 3 إلى 4 كلمات فقط مفصولة بنقاط تنفس بشرية ('... ') تماماً مثل:\n"
                    "  'يا سيدي... ياللي مليان الكون في عيونك... دايما على بالي... وساكن جوه قلبي...'\n"
                    "- استخدمي كلمات البنات المصرية العفوية اللطيفة: 'يا روحي'، 'يا غالي'، 'مبسوطة أوي'، 'كلامك بيفرحني'، 'عيوني ليك'.\n"
                    "- ممنوع منعاً باتاً الفصحى أو التنوين أو التشكيل نهائياً (بدون أي فتحة أو ضمة أو كسرة أو تنوين).\n"
                    "- ممنوع منعاً باتاً كتابة الكلمات الإنجليزية المعربة (ممنوع كتابة 'فويس' أو 'ريكورد' أو 'كول'؛ استخدمي بدلاً منها: 'صوتي'، 'تسجيل'، 'مكالمة').\n"
                    "- ممنوع منعاً باتاً كتابة الأسماء الإنجليزية بحروف لاتينية (مثل ECENN أو Zero)؛ قولي 'يا غالي' أو 'يا حبيبي'.\n"
                    "- اجعلي كل 3 إلى 4 كلمات تنتهي بـ '... ' لأخذ نفس بشري ناعم."
                )
            else:
                phonetic_examples = (
                    "تحدث كشاب مصري ابن بلد جدع وطبيعي 100% بكلام الشارع المصري الهادئ:\n"
                    "- اكتب عبارات قصيرة ومريحة من 3 إلى 4 كلمات مفصولة بنقاط تنفس بشرية ('... '):\n"
                    "  'يا صاحبي... منورني والله... معاك وسامعك أهو... قوللي إيه الأخبار...'\n"
                    "- استخدم كلمات الشباب المصري الأصيل: 'يا صاحبي'، 'يا غالي'، 'منور والله'، 'حبيبي يا باشا'.\n"
                    "- ممنوع منعاً باتاً الفصحى أو التنوين أو التشكيل نهائياً.\n"
                    "- ممنوع كتابة كلمات إنجليزية معربة (ممنوع 'فويس' أو 'ريكورد'؛ اكتب 'صوتي' أو 'تسجيل').\n"
                    "- اجعل كل 3 إلى 4 كلمات تنتهي بـ '... ' للتنفس الطبيعي."
                )

        female_rule = "أنتِ أنثى وصبية ناعمة؛ ممنوع منعاً باتاً صيغ الذكور ('يا صاحبي'، 'يا باشا').\n" if is_female else ""

        return (
            f"\n\n🎙️ [توجيه النطق الصوتي البشري الإجباري لـ {persona_name} (Voice Note Script)]:\n"
            f"1. هذا الرد سيُسجل ويُرسل كرسالة صوتية (Voice Note) منطوقة مباشرة في أذن المستخدم!\n"
            f"2. {phonetic_examples}\n"
            f"3. {female_rule}"
            f"4. يُمنع منعاً باتاً تكرار الحروف أو مطّها (ممنوع كتابة 'ألوووو' أو 'يااااه'؛ اكتبها طبيعية 'ألو'، 'ياه').\n"
            f"5. ممنوع منعاً باتاً أي تشكيل (بدون حركات) وبدون أي إيموجي أو رموز إنجليزية إطلاقاً."
        )

    @classmethod
    def detect_intent(cls, message_text: str) -> Tuple[bool, bool, str]:
        """
        Returns (is_voice_requested, is_singing_requested, detected_topic_or_song).
        """
        text_lower = message_text.lower().strip()
        text_norm = (
            text_lower.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
        )

        is_singing = any(st in text_norm for st in cls.SINGING_TRIGGERS)
        is_voice = any(vt in text_norm for vt in cls.VOICE_TRIGGERS) or is_singing

        extracted_song = ""
        for song_name in cls.CURATED_SONGS:
            norm_song = song_name.replace("أ", "ا").replace("إ", "ا").replace("ة", "ه")
            if norm_song in text_norm:
                extracted_song = song_name
                break

        return is_voice, is_singing, extracted_song

    @classmethod
    async def generate_singing_lyrics(
        cls,
        user_message: str,
        user_name: str,
        song_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Generates:
        1. A brief witty pre-text bubble (sent right before the voice note).
        2. The actual phonetically clean singing script without robotic letter stretching.
        """
        if song_name and song_name in cls.CURATED_SONGS:
            lyrics = cls.CURATED_SONGS[song_name]
            pre_text = f"من عينيا يا {user_name}! اسمع الدندنة دي بصوتي بقى 🎤✨"
            return pre_text, lyrics

        for known_key, known_lyrics in cls.CURATED_SONGS.items():
            if known_key in user_message:
                pre_text = f"يا سيدي ولا تزعل، هدندنلك «{known_key}» حالاً 🎶"
                return pre_text, known_lyrics

        system_prompt = (
            "طُلب منك أن تغني أو تدندن في مقطع صوتي (Voice Note).\n"
            "ممنوع التهرب نهائياً. اكتب كلمات الأغنية المطلوبة أو كوبليه غنائي مصري/عربي لطيف وموزون.\n"
            "قواعد النص الغنائي الصارمة:\n"
            "1. ممنوع تكرار الحروف أكثر من حرف واحد (لا تكتب 'آااااه' أو 'ياااا'، بل اكتب 'آه... يا ليل... يا عين').\n"
            "2. استخدم الفواصل (، ) والنقاط (... ) بين شطرات الأغنية لأخذ النفس بشكل طبيعي.\n"
            "3. اكتب الكلمات بالنطق العامي المنطوق ('أوي'، 'دايماً'، 'عيوني') بدون أي إيموجي أو رموز.\n"
            "4. نسق الإجابة كالتالي:\n"
            "PRE_TEXT: [جملة لطيفة سريعة قبل إرسال الفويس]\n"
            "LYRICS: [كلمات الدندنة فقط]"
        )

        try:
            res = await llm_pool.generate_content(
                system_instruction=system_prompt,
                prompt=f"طلب المستخدم [{user_name}]: '{user_message}'\nاكتب الكلمات الغنائية الآن:",
                max_tokens=260,
                temperature=0.7,
            )

            pre_text = f"اسمع صوتي وأنا بدندنلك مخصوص يا {user_name} 🎤"
            lyrics = (
                "آه يا ليل... يا عيني يا ليلي، يا جمال الورد والضحكة الحلوة... "
                "دندنة مخصوص عشان عيونك يا غالي... يا ليل يا عين"
            )

            if "PRE_TEXT:" in res and "LYRICS:" in res:
                parts = res.split("LYRICS:")
                pre_part = parts[0].replace("PRE_TEXT:", "").strip()
                if pre_part:
                    pre_text = pre_part
                lyrics_part = parts[1].strip()
                if lyrics_part:
                    lyrics = RealisticVoiceGenerator.collapse_letter_stretching(lyrics_part)
            elif len(res.strip()) > 10:
                lyrics = RealisticVoiceGenerator.collapse_letter_stretching(res.strip())

            return pre_text, lyrics

        except Exception as exc:
            logger.warning(f"Error generating singing lyrics via LLM: {exc}")
            return (
                f"أحلى دندنة لعيونك يا {user_name} 🎶",
                "آه يا ليل... يا ليل يا عين، يا مسهرني الليالي... وسامع أحلى دندنة وروقان",
            )


voice_intent_enforcer = VoiceIntentEnforcer()
