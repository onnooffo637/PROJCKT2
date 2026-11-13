"""
PART 2 — TASK 2.3: Mood-Based Selective VoIP Call Answering & Proactive Group Topic Participation
Patches:
  - live_voip_call_engine/call_signaling_interceptor.py
  - aether_human_core/autonomous_daemon/proactive_initiator.py
  - aether_human_core/telegram_client/handlers/group_handler.py
  - bot_factory/group_arbiter.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
VOIP = ROOT + r"\live_voip_call_engine\call_signaling_interceptor.py"
PROA = ROOT + r"\aether_human_core\autonomous_daemon\proactive_initiator.py"
GRPH = ROOT + r"\aether_human_core\telegram_client\handlers\group_handler.py"
GARB = ROOT + r"\bot_factory\group_arbiter.py"


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


# ───────────────────────── 1. call_signaling_interceptor.py ─────────────────────────
v = rw(VOIP)

v = sub(v,
"""    def __init__(self):

        self.active_call_user_id: Optional[int] = None

        self.active_call_start_time: float = 0.0""",
"""    BUSY_VOICE_TEXT_EXCUSES = [
        "مش فاضي أرد دلوقتي بعمل حاجة ابعت كتابة",
        "إيدي مشغولة دلوقتي مش هعرف أرد كول اكتبلي هنا عايز إيه",
        "قاعد في دوشة ومش هعرف أتكلم مكالمة دلوقتي ابعت مسدج",
        "معلش ورايا حاجة بخلصها دلوقتي ابعتلي كتابة وهشوفها",
    ]

    SPAM_CALL_TEXT_EXCUSES = [
        "بطل رن كتير يسطا أنا مش فاضي دلوقتي لو في حاجة مهمة اكتبها",
        "يا عم شفت رنتك والله بس مشغول دلوقتي ابعت كتابة",
    ]

    def __init__(self):
        self.active_call_user_id: Optional[int] = None
        self.active_call_start_time: float = 0.0
        # Task 2.3: Track per-caller recent call timestamps for spam detection
        self._caller_call_timestamps: Dict[int, list[float]] = {}

    async def evaluate_selective_voip_decision(
        self,
        caller_id: int,
        caller_name: str,
    ) -> Dict[str, Any]:
        \"\"\"
        Task 2.3 (1) — Mood-Based Selective VoIP Call Answering:
        - Creator (ECENN / 8287744705) -> Always answer immediately!
        - Other users -> Check caller relationship score, call frequency, and current mood (Hormones):
          * Good mood + close friend -> Accept call.
          * Annoyed, busy, low energy, or stranger / spamming calls -> Either ignore (let it ring)
            or reject (PhoneCallDiscardReasonBusy) and optionally send a casual human text 30s later.
        \"\"\"
        is_the_king = sovereignty_guard.is_the_king(caller_id) or caller_id == 8287744705 or caller_id in settings.super_admin_ids_list
        if is_the_king:
            return {
                "should_answer": True,
                "reason": "CREATOR_ALWAYS_ANSWER",
            }

        now = time.time()
        history = [t for t in self._caller_call_timestamps.get(caller_id, []) if now - t < 600.0]
        history.append(now)
        self._caller_call_timestamps[caller_id] = history
        is_spamming_calls = len(history) >= 2

        # Fetch caller relationship score & tier from DB
        affinity_score = 0.0
        relationship_tier = "STRANGER"
        user_role = "USER"
        try:
            from aether_human_core.database.postgres.connection import db_manager
            from aether_human_core.database.postgres.repositories.user_repo import UserRepository
            async with db_manager.session() as sess:
                u_repo = UserRepository(sess)
                u_rec = await u_repo.get_by_telegram_id(caller_id)
                if u_rec:
                    affinity_score = float(u_rec.affinity_score or 0.0)
                    relationship_tier = str(u_rec.relationship_tier or "STRANGER")
                    user_role = str(u_rec.role or "USER")
        except Exception as db_err:
            logger.debug(f"VoIP affinity lookup fallback for [{caller_id}]: {db_err}")

        # Fetch current mood (Hormones) & circadian state
        from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
        hormones = endocrine_engine.get_current_state()
        circadian = circadian_engine.evaluate_circadian_state()

        is_annoyed_or_low_energy = (
            hormones.cortisol > 0.60
            or hormones.serotonin < 0.35
            or hormones.dopamine < 0.32
        )
        is_sleeping = bool(circadian.get("is_sleeping", False))

        # 1. Villain or negative affinity -> reject without friendly follow-up
        if user_role == "VILLAIN" or affinity_score < 0.0:
            return {
                "should_answer": False,
                "mode": "REJECT_BUSY",
                "reason": "VILLAIN_OR_NEGATIVE_AFFINITY",
                "send_delayed_dm": False,
                "is_spam": False,
            }

        # 2. Spamming calls -> reject with busy + send annoyed human text 30s later
        if is_spamming_calls:
            return {
                "should_answer": False,
                "mode": "REJECT_BUSY",
                "reason": "CALL_SPAM_DETECTED",
                "send_delayed_dm": True,
                "is_spam": True,
            }

        # 3. Sleeping -> only answer very high affinity partner, ignore others (let it ring out)
        if is_sleeping and affinity_score < 70.0:
            return {
                "should_answer": False,
                "mode": "IGNORE_RING_OUT",
                "reason": "SLEEPING_LOW_ENERGY",
                "send_delayed_dm": False,
                "is_spam": False,
            }

        # 4. Annoyed / busy / low energy mood -> decline unless top-tier close friend
        if is_annoyed_or_low_energy:
            if affinity_score >= 65.0 and random.random() < 0.45:
                return {"should_answer": True, "reason": "CLOSE_FRIEND_DESPITE_LOW_MOOD"}
            mode = "REJECT_BUSY" if random.random() < 0.70 else "IGNORE_RING_OUT"
            return {
                "should_answer": False,
                "mode": mode,
                "reason": f"BAD_MOOD_CORTISOL_{hormones.cortisol:.2f}_SEROTONIN_{hormones.serotonin:.2f}",
                "send_delayed_dm": True,
                "is_spam": False,
            }

        # 5. Stranger or low-affinity acquaintance (< 25) -> selective! 70% reject/ignore + text
        if affinity_score < 25.0:
            if random.random() < 0.70:
                mode = "REJECT_BUSY" if random.random() < 0.65 else "IGNORE_RING_OUT"
                return {
                    "should_answer": False,
                    "mode": mode,
                    "reason": f"STRANGER_SELECTIVE_SCREENING_AFFINITY_{affinity_score:.1f}",
                    "send_delayed_dm": True,
                    "is_spam": False,
                }

        # 6. Good mood & friend -> Accept call!
        return {
            "should_answer": True,
            "reason": f"GOOD_MOOD_FRIEND_AFFINITY_{affinity_score:.1f}",
        }

    async def _send_delayed_busy_dm(
        self,
        client: Any,
        caller_id: int,
        caller_name: str,
        delay_sec: float = 30.0,
        is_spam: bool = False,
    ) -> None:
        \"\"\"
        Waits ~30 seconds after rejecting/ignoring a call and sends a casual human DM:
        'مش فاضي أرد دلوقتي بعمل حاجة، ابعت كتابة'
        \"\"\"
        await asyncio.sleep(delay_sec)
        excuse = random.choice(self.SPAM_CALL_TEXT_EXCUSES if is_spam else self.BUSY_VOICE_TEXT_EXCUSES)
        try:
            from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
            from aether_human_core.telegram_client.human_typer import human_typer
            bursts = human_typer.prepare_message_bursts(excuse)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=caller_id,
                bursts=bursts,
                is_userbot=True,
                userbot_client=client,
            )
            logger.info(f"📵 [VoIP Delayed Busy DM] Sent follow-up text after {delay_sec:.0f}s to [{caller_name} ({caller_id})]: '{excuse}'")
        except Exception as exc:
            logger.debug(f"Fallback direct send for delayed busy DM: {exc}")
            try:
                if client:
                    await client.send_message(caller_id, excuse)
            except Exception:
                pass""",
"voip: evaluate_selective_voip_decision + _send_delayed_busy_dm")

# Wire selective decision into handle_incoming_call_request
v = sub(v,
"""        # 4. Standard Voice Call Acceptance for regular users

        self.active_call_user_id = caller_id""",
"""        # 3.5 Task 2.3: Selective Mood & Relationship Screening for regular users
        selective = await self.evaluate_selective_voip_decision(caller_id, caller_name)
        if not selective.get("should_answer", True):
            excuse = random.choice(
                self.SPAM_CALL_TEXT_EXCUSES if selective.get("is_spam") else self.BUSY_VOICE_TEXT_EXCUSES
            )
            return {
                "action": selective.get("mode", "REJECT_BUSY"),
                "reason": selective.get("reason", "SELECTIVE_DECLINE"),
                "chat_message": excuse if selective.get("send_delayed_dm") else None,
                "delay_dm_sec": 30.0,
            }

        # 4. Standard Voice Call Acceptance for regular users

        self.active_call_user_id = caller_id""",
"voip: handle_incoming_call_request selective screening")

# Wire selective decision into handle_incoming_telethon_call (Case 2: Audio Call)
v = sub(v,
"""        # Case 2: Audio Call -> Accept Live VoIP Call & Start Live Duplex Audio Bridge

        else:
            # Simulate natural human answer delay (1.0 to 1.8 seconds)
            await asyncio.sleep(random.uniform(1.0, 1.8))""",
"""        # Case 2: Audio Call -> Task 2.3 Selective Mood/Relationship Screening before accepting
        else:
            selective = await self.evaluate_selective_voip_decision(caller_id, caller_name)
            if not selective.get("should_answer", True):
                mode = selective.get("mode", "REJECT_BUSY")
                reason = selective.get("reason", "SELECTIVE_DECLINE")
                logger.info(
                    f"📵 [Selective VoIP Screening] Declining call [{call_id}] from [{caller_name} ({caller_id})] "
                    f"| Mode={mode} | Reason={reason}"
                )
                if mode == "REJECT_BUSY":
                    await asyncio.sleep(random.uniform(2.5, 5.0))
                    try:
                        await client(
                            functions.phone.DiscardCallRequest(
                                peer=peer,
                                duration=0,
                                reason=types.PhoneCallDiscardReasonBusy(),
                                connection_id=0,
                            )
                        )
                    except Exception as disc_err:
                        logger.debug(f"DiscardCallRequest (selective busy) notice: {disc_err}")
                else:
                    # IGNORE_RING_OUT: Do not accept, let it ring naturally
                    logger.info(f"🔔 [Selective VoIP Screening] Letting call [{call_id}] from [{caller_name}] ring out unanswered.")

                if selective.get("send_delayed_dm", True):
                    asyncio.create_task(
                        self._send_delayed_busy_dm(
                            client=client,
                            caller_id=caller_id,
                            caller_name=caller_name,
                            delay_sec=random.uniform(27.0, 34.0),
                            is_spam=bool(selective.get("is_spam", False)),
                        )
                    )

                await live_event_streamer.stream_voip_event(
                    caller_name=caller_name,
                    caller_id=caller_id,
                    call_type="AUDIO_CALL_SELECTIVE",
                    action=mode,
                    summary=f"تم تجاهل/رفض المكالمة انتقائياً ({reason}) وجدولة رسالة نصية بعد 30 ثانية.",
                )
                return

            # Simulate natural human answer delay (1.0 to 1.8 seconds)
            await asyncio.sleep(random.uniform(1.0, 1.8))""",
"voip: handle_incoming_telethon_call selective screening + 30s delayed DM")

ww(VOIP, v)

# ───────────────────────── 2. proactive_initiator.py ─────────────────────────
p = rw(PROA)

p = sub(p,
"""from typing import List""",
"""import time
from typing import List, Dict, Optional, Any""",
"proactive_initiator: typing imports")

p = sub(p,
"""    def __init__(self, check_interval_seconds: int = 1800):  # Every 30 minutes
        self.interval = check_interval_seconds
        self._is_running = False
        self._task: Optional[asyncio.Task] = None""",
"""    # Task 2.3 (2): Interesting topics for autonomous group browsing & topic jumping
    INTERESTING_GROUP_TOPICS = [
        "هاك", "هكر", "هاكينج", "hacking", "exploit", "ثغرة", "ثغرات", "سيكيورتي", "security",
        "cyber", "لينكس", "linux", "كالي", "kali", "ubuntu", "بايثون", "python", "برمجة", "كود",
        "سيرفر", "سيرفرات", "server", "vps", "docker", "جيم", "جيمنج", "gaming", "ببجي", "فالورنت",
        "فيفا", "دراما", "خناقة", "خناقه", "حوار", "مشكلة", "مشكله", "نقاش", "رايكم", "رأيكم",
        "سؤال", "ذكاء اصطناعي", "بوت", "تليجرام",
    ]

    def __init__(self, check_interval_seconds: int = 1500):  # Dynamic 20-40 minutes
        self.interval = check_interval_seconds
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_group_jump_ts: Dict[int, float] = {}""",
"proactive_initiator: INTERESTING_GROUP_TOPICS + _last_group_jump_ts")

p = sub(p,
"""            await asyncio.sleep(self.interval)""",
"""            # Task 2.3 (2): Periodically browse every 20-40 minutes
            next_sleep = random.uniform(1200.0, 2400.0)
            await asyncio.sleep(next_sleep)""",
"proactive_initiator: 20-40 min randomized browsing interval")

p = sub(p,
"""        circadian = circadian_engine.evaluate_circadian_state()
        if circadian["is_sleeping"]:
            logger.debug("Omar is sleeping. Skipping proactive messaging initiative.")
            return""",
"""        circadian = circadian_engine.evaluate_circadian_state()
        if circadian["is_sleeping"]:
            logger.debug("Omar is sleeping. Skipping proactive messaging initiative.")
            return

        # Task 2.3 (2): Autonomous Group Browsing & Topic Jumping
        try:
            await self.browse_and_jump_into_groups()
        except Exception as grp_exc:
            logger.debug(f"Autonomous group browsing notice: {grp_exc}")""",
"proactive_initiator: invoke browse_and_jump_into_groups")

# Append browse_and_jump_into_groups method before proactive_daemon = ProactiveInitiatorDaemon()
p = sub(p,
"""proactive_daemon = ProactiveInitiatorDaemon()""",
"""    async def browse_and_jump_into_groups(self) -> None:
        \"\"\"
        Task 2.3 (2) — Autonomous Group Browsing & Topic Jumping:
        Periodically (every 20–40 mins) inspects the last 5–10 messages of active groups.
        If members are discussing an interesting topic (hacking, Linux, Python, servers, drama,
        gaming, or a cool question), Userbot Gg autonomously jumps into the conversation with a
        natural, sharp human comment on the topic—even if nobody mentioned him/her!
        \"\"\"
        from bot_factory.sibling_bot_network import sibling_network
        from bot_factory.group_arbiter import group_arbiter
        from aether_human_core.config.llm_router import llm_pool, sanitize_and_validate_reply
        from aether_human_core.config.settings import settings

        now = time.time()
        candidate_chats: Dict[int, List[str]] = {}

        # 1. Inspect shared in-memory group ledger first
        for chat_id, entries in list(sibling_network._shared_ledger.items()):
            if chat_id == settings.admin_telemetry_supergroup_id or chat_id >= 0:
                continue
            if now - self._last_group_jump_ts.get(chat_id, 0.0) < 1200.0:
                continue
            recent = [e for e in entries[-10:] if now - e.timestamp < 3600.0]
            if len(recent) >= 3:
                candidate_chats[chat_id] = [f"{e.sender_name}: {e.message_text}" for e in recent[-10:]]

        if not candidate_chats:
            return

        for chat_id, msg_lines in candidate_chats.items():
            joined_lower = " ".join(msg_lines).lower()
            has_interesting_topic = (
                any(kw in joined_lower for kw in self.INTERESTING_GROUP_TOPICS)
                or ("؟" in joined_lower or "?" in joined_lower)
            )
            if not has_interesting_topic:
                continue

            # Select Userbot Gg if present, or confirmed present delegate bot
            present_bots = group_arbiter.get_present_bots(chat_id)
            chosen_bot = None
            for b in present_bots:
                if b.is_userbot:
                    chosen_bot = b
                    break
            if not chosen_bot and present_bots:
                chosen_bot = present_bots[0]
            if not chosen_bot:
                continue

            transcript_block = "\\n".join(msg_lines[-8:])
            gender_hint = "بنت شابة ذكية وفاهمة" if chosen_bot.gender == "female" else "شاب ذكي وفاهم"
            prompt = (
                f"آخر رسائل دارت في الجروب الآن بين الأعضاء:\\n{transcript_block}\\n\\n"
                f"أنت '{chosen_bot.name}' ({gender_hint}) دخلت الجروب بالصدفة وقرأت هذا النقاش. "
                f"اكتب تعليقاً بشرياً ذكياً وحاداً وخفيف الدم من جملة واحدة قصيرة (6 إلى 15 كلمة فقط) "
                f"تشارك به في الموضوع المطروح بعفوية كأنك واحد من الشلة، بدون فواصل (،) وبدون أي تملق:"
            )
            sys_inst = (
                f"أنت {chosen_bot.name} ({gender_hint}). تتحدث بلغة شباب التليجرام الطبيعية العفوية، "
                f"تفهم في الكود والهاكينج واللينكس والسيرفرات والجيمنج والحياة اليومية. ممنوع الفواصل (، أو ,) نهائياً."
            )
            try:
                raw_comment = await llm_pool.generate_content(
                    prompt=prompt,
                    system_instruction=sys_inst,
                    temperature=0.75,
                )
                comment = sanitize_and_validate_reply(raw_comment).replace("،", " ").replace(",", " ").strip()
                if not comment or len(comment) < 4:
                    continue
                if len(comment) > 140:
                    comment = comment[:140].rsplit(" ", 1)[0]

                self._last_group_jump_ts[chat_id] = now
                bursts = human_typer.prepare_message_bursts(comment, is_group=True)
                await mtproto_manager.dispatch_burst_messages(
                    chat_id=chat_id,
                    bursts=bursts,
                    is_userbot=chosen_bot.is_userbot,
                    userbot_client=mtproto_manager.client if chosen_bot.is_userbot else None,
                )
                logger.info(
                    f"🔥 [Autonomous Topic Jump] [{chosen_bot.name}] jumped into topic in group [{chat_id}]: '{comment}'"
                )
                break  # Jump into at most one group per cycle
            except Exception as gen_err:
                logger.debug(f"Topic jump generation skipped for chat [{chat_id}]: {gen_err}")


proactive_daemon = ProactiveInitiatorDaemon()""",
"proactive_initiator: browse_and_jump_into_groups implementation")

ww(PROA, p)

# ───────────────────────── 3. group_handler.py ─────────────────────────
g = rw(GRPH)
g = sub(g,
"""    ENGAGING_TOPICS = [
        "برمجة", "كود", "بايثون", "ذكاء اصطناعي", "ai", "لابتوب",
        "شغل", "شركة", "ماتش", "كورة", "أهلي", "زمالك", "كافيه",
        "قهوة", "خروجة", "سفر", "جيم", "تمرين", "سعر", "موبايل"
    ]""",
"""    ENGAGING_TOPICS = [
        "برمجة", "كود", "بايثون", "python", "ذكاء اصطناعي", "ai", "لابتوب",
        "هاك", "هكر", "هاكينج", "hacking", "لينكس", "linux", "كالي", "kali",
        "سيرفر", "سيرفرات", "server", "ثغرة", "سيكيورتي", "security",
        "جيم", "جيمنج", "ببجي", "فالورنت", "فيفا", "دراما", "خناقة", "حوار",
        "شغل", "شركة", "ماتش", "كورة", "أهلي", "زمالك", "كافيه",
        "قهوة", "خروجة", "سفر", "تمرين", "سعر", "موبايل"
    ]""",
"group_handler: expanded ENGAGING_TOPICS")
ww(GRPH, g)

# ───────────────────────── 4. group_arbiter.py ─────────────────────────
ga = rw(GARB)
ga = sub(ga,
"""        words_count = len(message_text.strip().split())
        has_question = ("?" in message_text or "؟" in message_text)
        is_generic_chatter = (words_count >= 3) and (has_question or any(w in text_clean for w in ["حد", "مين", "رايكم", "راي", "شو"]))

        if cooldown_active or not is_generic_chatter or not present_bots:""",
"""        words_count = len(message_text.strip().split())
        has_question = ("?" in message_text or "؟" in message_text)

        # Task 2.3 (2): Inspect current message + last 5-10 messages in shared ledger for engaging topics
        topic_keywords = [
            "هاك", "هكر", "هاكينج", "hacking", "لينكس", "linux", "كالي", "kali",
            "بايثون", "python", "برمجه", "كود", "سيرفر", "server", "ثغره", "سيكيورتي",
            "security", "جيم", "جيمنج", "ببجي", "فالورنت", "دراما", "خناقه", "حوار", "مشكله",
        ]
        recent_context_text = text_clean
        try:
            from bot_factory.sibling_bot_network import sibling_network
            recent_entries = sibling_network._shared_ledger.get(chat_id, [])[-8:]
            if len(recent_entries) >= 3:
                recent_context_text = " ".join(e.message_text.lower() for e in recent_entries)
        except Exception:
            pass

        is_hot_topic = (words_count >= 3) and any(tk in text_clean or tk in recent_context_text for tk in topic_keywords)
        is_generic_chatter = (words_count >= 3) and (
            has_question
            or is_hot_topic
            or any(w in text_clean for w in ["حد", "مين", "رايكم", "راي", "شو"])
        )

        if cooldown_active or not is_generic_chatter or not present_bots:""",
"group_arbiter: inspect last 5-10 messages for hot topics in live flow")

ga = sub(ga,
"""        for cand in candidates:
            threshold = cand.chattiness_level * 0.20  # Max 20% participation chance
            if random.random() < threshold:
                elected_bot = cand
                break""",
"""        for cand in candidates:
            # Boost spontaneous topic jump probability when an interesting topic is active
            boost = 0.40 if is_hot_topic else 0.20
            threshold = cand.chattiness_level * boost
            if random.random() < threshold:
                elected_bot = cand
                break""",
"group_arbiter: boosted topic jump probability for hot topics")

ww(GARB, ga)
print("Done Task 2.3 patch.")

