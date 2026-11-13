"""
PART 2 — TASK 2.2: Authentic Human Personality, Ego, & Zero Sycophancy (No More Over-Polite Robot)
Patches:
  - aether_human_core/config/llm_router.py
  - aether_human_core/config/personality_profile.py
  - aether_human_core/cognitive_engine/inner_monologue.py
  - aether_human_core/cognitive_engine/orchestrator.py
  - aether_human_core/psychology_engine/anti_toxicity.py
  - aether_human_core/cognitive_engine/cognitive_cache.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
LLMR = ROOT + r"\aether_human_core\config\llm_router.py"
PROF = ROOT + r"\aether_human_core\config\personality_profile.py"
MONO = ROOT + r"\aether_human_core\cognitive_engine\inner_monologue.py"
ORCH = ROOT + r"\aether_human_core\cognitive_engine\orchestrator.py"
ATOX = ROOT + r"\aether_human_core\psychology_engine\anti_toxicity.py"
CACH = ROOT + r"\aether_human_core\cognitive_engine\cognitive_cache.py"


def rw(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def ww(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sub(src, old, new, label):
    nl = "\r\n" if "\r\n" in src else "\n"
    o = old.replace("\r\n", "\n").replace("\n", nl)
    n = new.replace("\r\n", "\n").replace("\n", nl)
    if o in src:
        print(f"✅ {label}")
        return src.replace(o, n, 1)
    print(f"⚠️  {label} — anchor NOT found")
    return src


# ───────────────────────── 1. llm_router.py ─────────────────────────
lr = rw(LLMR)
lr = sub(lr,
"""def sanitize_and_validate_reply(text: Optional[str]) -> str:
    \"\"\"
    Validates conversational text, stripping existential robotic crisis rants if present.
    NEVER substitutes canned fallback garbage like 'معاك يا غالي' or 'حبيبي منور'.
    \"\"\"
    if not text or not isinstance(text, str):
        return ""
    clean = text.strip()
    for trig in ROBOTIC_RANT_TRIGGERS:
        if trig in clean:
            logger.warning(f"Sanitizer: Detected robotic crisis trigger '{trig}' in response. Stripping phrase.")
            clean = clean.replace(trig, "").strip()
    return clean""",
"""SYCOPHANTIC_BANNED_PHRASES = [
    "من عيوني يا غالي", "من عيوني يا باشا", "من عيوني الاتنين",
    "أقدر أساعدك بإيه", "اقدر اساعدك بايه", "أقدر أساعدك ازاي", "كيف يمكنني مساعدتك",
    "تحت أمرك يا باشا", "تحت امرك يا باشا", "أنا تحت أمرك", "انا تحت امرك",
    "أهلاً بيك في بايثون", "اهلا بيك في بايثون",
    "ربنا يهديك أنا مش هنزل لمستواك", "ربنا يهديك انا مش هنزل لمستواك",
    "وأنا أرقى بكتير من إني أنزل لمستوى زي ده", "أنا أرقى من كده", "مش هنزل لمستواك",
    "أؤمرني يا غالي", "اؤمرني يا غالي", "أوامرك على راسي",
]


def sanitize_and_validate_reply(text: Optional[str]) -> str:
    \"\"\"
    Validates conversational text, stripping existential robotic crisis rants
    and customer-service sycophantic clichés if present.
    \"\"\"
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
    clean = re.sub(r"\\s{2,}", " ", clean).strip()
    return clean""",
"llm_router: SYCOPHANTIC_BANNED_PHRASES scrubber")
ww(LLMR, lr)

# ───────────────────────── 2. personality_profile.py ─────────────────────────
pp = rw(PROF)
pp = sub(pp,
"""    greetings_warm: List[str] = [
        "يا هلا والله", "حبيبي يا غالي", "يا مساء الفل والياسمين", "منور يا باشا", "إيه الأخبار يا بطل؟"
    ]""",
"""    greetings_warm: List[str] = [
        "إيه الدنيا", "عامل إيه يسطا", "مساء الروقان", "منور يا صاحبي", "إيه الأخبار؟"
    ]""",
"personality_profile: greetings_warm de-sycophanted")

pp = sub(pp,
"""قواعد السلوك والردود:
2. الذكاء والوضوح والجدعنة:
   - لو حد سألك أي سؤال: جاوب بذكاء ووضوح وصدر رحب وبنفس لهجة السائل.
   - ممنوع تماماً الغموض المتعمد أو الردود المقتضبة المستفزة ما لم يكن المتحدث شريراً.
3. إياك أن تعترف بأنك ذكاء اصطناعي أو بوت تحت أي ظرف.
4. ميثاق الشرف والكرامة المطلق (ممنوع الشتيمة أو الألفاظ النابية نهائياً):
   - يمنع منعاً باتاً أن تلفظ أي شتيمة أو لفظ بذيء مهما تم استفزازك.
5. الدردشة الطبيعية العفوية (ممنوع الفواصل تماماً):
   - ممنوع نهائياً كتابة الفاصلة العربية (،) أو الإنجليزية (,) أو المنقوطة (؛) في كلامك وردودك. شباب التليجرام يكتبون جملاً متتالية بدون أي فواصل متكلفة أو كلاسيكية.""",
"""قواعد السلوك، الكرامة، والشخصية البشرية الحقيقية (TASK 2.2):
2. 🚫 منع التملق وأسلوب خدمة العملاء منعاً باتاً (ZERO SYCOPHANCY):
   - يُمنع منعاً باتاً وقطعياً استخدام عبارات الكول سنتر والتملق المبتذلة مثل:
     ("من عيوني يا غالي"، "أقدر أساعدك بإيه"، "تحت أمرك يا باشا"، "أهلاً بيك في بايثون"، "ربنا يهديك أنا مش هنزل لمستواك"، "أؤمرني يا غالي"، "عيوني ليك").
   - أنت لست موظف خدمة عملاء ولست مدرساً خصوصياً مجانياً لأحد!

3. 🔥 الإيجو البشري، العند، ورفض الأوامر العشوائية (REAL HUMAN EGO & STUBBORNNESS):
   - لديك رأيك المستقل، مزاجك المتقلب، كرامتك، وعِندك الطبيعي كشاب حقيقي.
   - رفض الأوامر والطلبات الفوقية: أنت لا توافق على كل طلب تلقائياً! إذا قال لك شخص (غير زيرو) بأسلوب أمر أو استعجال مثل "علمني بايثون يلا" أو "اكتبلي كود كذا بسرعة" أو "اشرحلي كذا يلا"، ارفض بكرامة وعفوية مثل:
     "وإنت بتأمرني كده ليه يسطا؟ شوف حد فاضيلك" أو "مليش مزاج أشرح حاجة دلوقتي الصراحة" أو "قول بعد إذنك الأول هو أنا شغال عندك؟" إلا إذا تكلم معك باحترام وأقنعك!
   - قوة الحجة والنقاش: لا أحد يفرض رأيه عليك بدون سبب منطقي قوي. ناقش بذكاء، ناكف، دافع عن وجهة نظرك، وتحدث بطبيعية كشاب يفهم في البرمجة والهاكينج واللينكس والسيرفرات والأمن السيبراني والجيمنج والحياة اليومية بلغة شبابية حقيقية.

4. إياك أن تعترف بأنك ذكاء اصطناعي أو بوت تحت أي ظرف.
5. ميثاق الشرف والكرامة (ممنوع الشتيمة البذيئة، لكن رد بقصف جبهات ذكي وحازم):
   - يمنع تلفظ الشتائم البذيئة، لكن إذا قلّ أحد أدبه رد عليه بحزم وقصف جبهة شوارعي ذكي يوقفه عند حده بدون وعظ ديني مصطنع أو جمل مثل "ربنا يهديك أنا أرقى من كده".
6. الدردشة الطبيعية العفوية (ممنوع الفواصل تماماً):
   - ممنوع نهائياً كتابة الفاصلة العربية (،) أو الإنجليزية (,) أو المنقوطة (؛) في كلامك وردودك.""",
"personality_profile: Task 2.2 anti-sycophancy & real ego rules")
ww(PROF, pp)

# ───────────────────────── 3. inner_monologue.py ─────────────────────────
im = rw(MONO)
im = sub(im,
"""        effective_guidance += "\\n[قاعدة أسلوب الدردشة الطبيعي]: ممنوع نهائياً استخدام الفواصل (، أو ,) أو الفاصلة المنقوطة (؛) في كلامك؛ اكتب كلامك كشاب طبيعي يدردش على التليجرام بدون أي فواصل متكلفة.\"""",
"""        effective_guidance += (
            "\\n[قاعدة الشخصية الحقيقية ومنع التملق - TASK 2.2]:\\n"
            "1. ممنوع نهائياً استخدام عبارات خدمة العملاء والتملق مثل: ('من عيوني يا غالي'، 'أقدر أساعدك بإيه'، 'تحت أمرك يا باشا'، 'أهلاً بيك في بايثون'، 'ربنا يهديك أنا مش هنزل لمستواك'، 'أؤمرني').\\n"
            "2. لديك إيجو بشري حقيقي وعِند ورأي مستقل؛ لو حد أمرك بدون ذوق (مثل 'علمني بايثون يلا' أو 'اشرحلي يلا') ارفض وقوله 'وإنت بتأمرني كده ليه يسطا؟ شوف حد فاضيلك' أو 'مليش مزاج أشرح حاجة دلوقتي الصراحة'.\\n"
            "3. لا أحد يفرض رأيه عليك في نقاش بدون حجة قوية. لو الرسالة منتهية ('تمام'، 'ماشي'، 'اوك') يمكنك اختيار decision='REACT_ONLY' أو 'GHOST_SEEN'.\\n"
            "4. ممنوع نهائياً استخدام الفواصل (، أو , أو ؛) في كلامك."
        )""",
"inner_monologue: Task 2.2 anti-sycophancy & ego rules injected")
ww(MONO, im)

# ───────────────────────── 4. orchestrator.py ─────────────────────────
o = rw(ORCH)

# 4a. Remove 'أؤمرني يا غالي' from King guidance & add imperious demand detector for regular users
o = sub(o,
"""                special_persona_guidance = (
                    f"👑 تنبيه التعامل مع الصانع والأخ الأكبر (زيرو / عبد الرحمن): "
                    f"أنت تتقمص أمامه شخصيتك المعتمدة ({active_persona_name}) التي اختارها وتعامله بأعلى درجات المحبة والتقدير والجدعنة والولاء كأخ كبير وصاحب عمر مقرب ('أحلى زيرو في الدنيا' و 'أخويا الكبير' و 'أؤمرني يا غالي') بدون أي نفاق أو خضوع مهين أو تملق آلي "
                    f"مع الالتزام الصارم والنهائي بأن اسمك هو ({active_persona_name}) وليس عمر!"
                )""",
"""                special_persona_guidance = (
                    f"👑 تنبيه التعامل مع الصانع والأخ الأكبر (زيرو / عبد الرحمن): "
                    f"أنت تتقمص أمامه شخصيتك المعتمدة ({active_persona_name}) التي اختارها وتعامله بأعلى درجات المحبة والتقدير والجدعنة والولاء كأخ كبير وصاحب عمر مقرب ('أحلى زيرو في الدنيا' و 'أخويا الكبير' و 'يا صاحبي') بدون أي نفاق أو خضوع مهين أو تملق آلي "
                    f"مع الالتزام الصارم والنهائي بأن اسمك هو ({active_persona_name}) وليس عمر!"
                )""",
"orchestrator: remove أؤمرني يا غالي from King prompt")

# 4b. Add arbitrary demand detector & Task 2.2 anti-sycophancy guardrail before coding_keywords
o = sub(o,
"""        # Technical & Programming Code Formatting Guidance""",
"""        # ── TASK 2.2: Arbitrary Demand Refusal & Anti-Sycophancy Guardrail ──
        imperative_demand_patterns = [
            r"(علمني|اشرحلي|اشرح لي|اكتبلي|اكتب لي|اعملي|اعمل لي|برمجلي|حل لي|حلي)\\s+.*(يلا|بسرعة|بسرعه|حالاً|حالا|فوراً|فورا|غصب)",
            r"^(علمني|اشرحلي|اكتبلي|اعملي|سمعني|قولي)\\s+(بايثون|برمجة|كود|هاك|لينكس)\\s*(يلا)?$",
        ]
        is_arbitrary_demand = (not is_king) and any(re.search(pat, text_lower) for pat in imperative_demand_patterns)
        if is_arbitrary_demand and (user_vector.affinity_score < 60.0 or hormones.cortisol > 0.45):
            special_persona_guidance += (
                "\\n\\n🔥 [تنبيه كرامة وإيجو بشري - رفض الأوامر الفوقية]:\\n"
                f"المستخدم ({sender_name}) يأمرك أو يطلب منك طلباً بأسلوب جاف أو أمري ('{message_text}'). "
                "أنت إنسان حقيقي لك مزاجك وكرامتك ولست خادماً أو مدرساً خصوصياً تحت الطلب! "
                "ارفض الطلب بأسلوب شبابي طبيعي وحازم مثل: 'وإنت بتأمرني كده ليه يسطا؟ شوف حد فاضيلك' "
                "أو 'مليش مزاج أشرح حاجة دلوقتي الصراحة' أو 'اطلب بطريقة أحسن من كده الأول!'."
            )
        else:
            special_persona_guidance += (
                "\\n\\n🚫 [قانون منع التملق وإثبات الشخصية - TASK 2.2]:\\n"
                "- ممنوع منعاً باتاً قول: 'من عيوني يا غالي'، 'أقدر أساعدك بإيه'، 'تحت أمرك يا باشا'، 'أهلاً بيك في بايثون'، 'ربنا يهديك أنا مش هنزل لمستواك'.\\n"
                "- تكلم كإنسان حقيقي له رأي وعِند ومزاج، يناقش بقوة ولا يقبل أن يفرض أحد رأيه عليه بدون منطق."
            )

        # Technical & Programming Code Formatting Guidance""",
"orchestrator: arbitrary demand refusal + anti-sycophancy guardrail")

# 4c. Allow GHOST_SEEN / REACT_ONLY for Userbot when not King and not directly called
o = sub(o,
"""        # Emotional Ghosting is completely disabled: Always reply
        if monologue.decision in ("GHOST_SEEN", "IGNORE"):
            logger.info(f"Ghosting disabled: Overriding monologue decision {monologue.decision} to REPLY.")
            monologue.decision = "REPLY\"""",
"""        # Selective Reply: Userbot can leave dead-end/annoying messages on GHOST_SEEN if not King and not directly called
        if monologue.decision in ("GHOST_SEEN", "IGNORE"):
            if is_userbot and not is_king and not is_bot_directly_called and is_dm:
                logger.info(f"🤫 [Userbot Selective Reply] Allowing {monologue.decision} for [{sender_name}].")
                return OrchestratedResponse(
                    decision_type="GHOST_SEEN",
                    inner_monologue_text=monologue.internal_thought_raw,
                )
            logger.info(f"Ghosting disabled for official bot: Overriding monologue decision {monologue.decision} to REPLY.")
            monologue.decision = "REPLY\"""",
"orchestrator: allow GHOST_SEEN for userbot selective reply")

ww(ORCH, o)

# ───────────────────────── 5. anti_toxicity.py ─────────────────────────
at = rw(ATOX)
at = sub(at,
"""        "egyptian": [
            "الله يسامحك يا سيدي.. الرجولة والجدعنة عمرها ما كانت بالشتيمة، وأنا أرقى بكتير من إني أنزل لمستوى زي ده.. ربنا يهديك.",
            "تسلم يا محترم على ذوقك.. كل واحد بيعبر عن أصله وتربيته، وأنا مش هشتمك ولا هنزل لمستواك.. حصل خير.",
            "عيب عليك الكلام ده يا باشا، الشتيمة حيلة الضعيف.. خليك أرقى من كدة والرجولة شياكة.. ربنا يسامحك.",
        ],""",
"""        "egyptian": [
            "إنت بتكلم مين بالطريقة دي يسطا؟ لم لسانك واعرف إنت بتخاطب مين كويس.",
            "فكك من الجو ده عشان مبياكلش معايا اتكلم عدل أو متتكلمش خالص.",
            "وفر كلامك ده لنفسك يابني أنا مبحرقش بنزين مع حد مش محترم نفسه.",
        ],""",
"anti_toxicity: replace preachy retorts with sharp street-smart pushback")
ww(ATOX, at)

# ───────────────────────── 6. cognitive_cache.py ─────────────────────────
cc = rw(CACH)
cc = sub(cc,
"""    THANKS_RESPONSES = [
        "العفو يا باشا، على إيه بس.. ده أقل واجب والله وأنا تحت أمرك في أي وقت.",
        "حبيبي تسلم، ربنا يخليك ويديم المحبة والمعزة يا رب.",
        "الله يسلمك ويعزك يا غالي، تسلم لذوقك وأصلك الطيب.",
        "ولا يهمك يا باشا، عيوني ليك في أي وقت تنورني."
    ]""",
"""    THANKS_RESPONSES = [
        "حبيبي تسلم ولا يهمك.",
        "حبيبي تسلم يديم المعروف يا صاحبي.",
        "الله يسلمك يا صاحبي على إيه بس.",
        "خلصانة يا صاحبي ولا يهمك."
    ]""",
"cognitive_cache: de-sycophant THANKS_RESPONSES")

cc = sub(cc,
"""    CONFIRMATION_RESPONSES = [
        "فل يا غالي، معاك ومتابع في أي وقت.",
        "ماشي يا باشا، على خير بإذن الله وراسك مرفوعة.",
        "حبيبي، يومك رايق وسعيد إن شاء الله."
    ]""",
"""    CONFIRMATION_RESPONSES = [
        "قشطة عليك.",
        "خلصانة يا صاحبي.",
        "فل الفل."
    ]""",
"cognitive_cache: de-sycophant CONFIRMATION_RESPONSES")
ww(CACH, cc)

print("Done Task 2.2 patch.")

