"""
PART 2 — TASK 2.1: Realistic Human Read -> Think -> Type State Machine for Userbot (Gg / ريمي)
Patches:
  - aether_human_core/telegram_client/mtproto_manager.py
  - aether_human_core/telegram_client/handlers/dm_handler.py
  - aether_human_core/telegram_client/human_typer.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
MTP = ROOT + r"\aether_human_core\telegram_client\mtproto_manager.py"
DMH = ROOT + r"\aether_human_core\telegram_client\handlers\dm_handler.py"
HTY = ROOT + r"\aether_human_core\telegram_client\human_typer.py"


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


# ───────────────────────── 1. mtproto_manager.py ─────────────────────────
m = rw(MTP)

# 1a. Add conversation timing & state machine dicts in __init__
m = sub(m,
"""        self._user_last_button_click: Dict[int, float] = {}
        self._user_media_cooldown: Dict[Tuple[int, str], float] = {}""",
"""        self._user_last_button_click: Dict[int, float] = {}
        self._user_media_cooldown: Dict[Tuple[int, str], float] = {}
        # Task 2.1: Userbot Read -> Think -> Type state machine tracking
        self._userbot_last_conv_ts: Dict[int, float] = {}
        self._userbot_active_conv_flag: Dict[int, bool] = {}""",
"mtproto: state machine tracking dicts in __init__")

# 1b. Add helper methods for Phase 1, Phase 2, and Selective Reply Filter right before _register_telethon_handlers
m = sub(m,
"""    def _register_telethon_handlers(self) -> None:""",
"""    # =========================================================================
    # Task 2.1: Realistic Human Read -> Think -> Type State Machine Helpers
    # =========================================================================

    DEAD_END_SINGLE_PHRASES = {
        "ماشي", "ماشى", "تمام", "اوك", "أوك", "اوكي", "أوكي", "ok", "okay", "k", "kk",
        "طيب", "خلاص", "فل", "قشطه", "قشطة", "حاضر", "تمام ماشي", "ماشي تمام",
        "اوك تمام", "طيب ماشي", "خلاص ماشي", "تمام يسطا", "ماشي يسطا", "اشطا", "أشطا",
        "👍", "👌", "🤝", "🙏",
    }

    def compute_userbot_phase1_unseen_delay(self, chat_id: int, sender_id: int) -> Tuple[float, bool]:
        \"\"\"
        Phase 1 — Variable Unseen Delay (Before ✓✓ Seen):
        - If Userbot is already in an active rapid conversation with this user (last message < 2 mins ago),
          wait 2–8 seconds before marking Seen.
        - If this is a new message or Userbot was idle/busy, wait a realistic random delay (15 to 90 seconds,
          configurable via settings) before calling client.send_read_acknowledge().
        \"\"\"
        now = time.time()
        last_ts = self._userbot_last_conv_ts.get(chat_id, 0.0)
        elapsed = now - last_ts
        is_active_rapid = (last_ts > 0.0 and elapsed < 120.0)
        self._userbot_active_conv_flag[chat_id] = is_active_rapid

        if is_active_rapid:
            delay = random.uniform(2.0, 8.0)
            return delay, True

        idle_min = float(getattr(settings, "userbot_idle_unseen_min_sec", 15.0))
        idle_max = float(getattr(settings, "userbot_idle_unseen_max_sec", 90.0))
        # Scale slightly shorter if Creator (8287744705) is messaging while idle, still within 15-30s realistic window
        if sender_id == 8287744705:
            delay = random.uniform(idle_min, min(30.0, idle_max))
        else:
            delay = random.uniform(idle_min, idle_max)
        return delay, False

    def compute_userbot_phase2_think_delay(self, message_text: str, sender_id: int, chat_id: int = 0) -> float:
        \"\"\"
        Phase 2 — Human Thinking Pause (After ✓✓ Seen, Before Typing...):
        Once Seen (✓✓) is marked, wait a realistic reading & thinking pause of 15 to 75 seconds
        scaled by message complexity, urgency, and current mood.
        \"\"\"
        think_min = float(getattr(settings, "userbot_think_min_sec", 15.0))
        think_max = float(getattr(settings, "userbot_think_max_sec", 75.0))

        text_clean = (message_text or "").strip()
        words_cnt = len(text_clean.split())

        # Check urgency or Creator priority
        urgent_keywords = ["بسرعة", "بسرعه", "ضروري", "عاجل", "الحقني", "الحقيني", "فوراً", "فورا", "طارئ"]
        is_urgent = (sender_id == 8287744705) or any(uk in text_clean.lower() for uk in urgent_keywords)

        if is_urgent:
            base_think = random.uniform(think_min, min(24.0, think_max))
        elif words_cnt <= 5:
            base_think = random.uniform(think_min, min(32.0, think_max))
        elif words_cnt <= 18:
            base_think = random.uniform(max(think_min, 22.0), min(50.0, think_max))
        else:
            base_think = random.uniform(max(think_min, 35.0), think_max)

        # Mood scaling from endocrine engine
        try:
            from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
            h = endocrine_engine.get_current_state()
            if h.cortisol > 0.65 or h.serotonin < 0.35:
                # Tired or annoyed -> thinks/hesitates longer before typing
                base_think = min(think_max, base_think * 1.25)
            elif h.dopamine > 0.72:
                # Excited/energetic -> towards the quicker end of 15-75s
                base_think = max(think_min, base_think * 0.85)
        except Exception:
            pass

        return round(max(think_min, min(think_max, base_think)), 2)

    def evaluate_selective_reply_filter(
        self,
        message_text: str,
        media_type: str,
        sender_id: int,
        is_active_conv: bool,
    ) -> Tuple[bool, Optional[str]]:
        \"\"\"
        Task 2.1 (4) — Selective Human Reply Filter (Not Obligated to Reply to Everything):
        If a user sends a dead-end message ('ماشي', 'تمام', 'اوك', or a random sticker after an
        active/finished exchange), Userbot can mark it Seen (✓✓) or leave a single reaction (👍)
        and choose NOT to reply.
        Returns: (should_skip_text_reply, optional_reaction_emoji)
        \"\"\"
        raw = (message_text or "").strip()
        if not raw and media_type == "text":
            return True, None

        # Never skip questions, slash commands, or media requests
        if "?" in raw or "؟" in raw or raw.startswith("/"):
            return False, None

        norm = (
            raw.lower()
            .replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            .replace("ة", "ه").replace("ى", "ي")
        )
        norm_stripped = re.sub(r"[.!،,؟?~…]+", "", norm).strip()

        # Never skip if user explicitly calls the bot by name or asks for photo/voice
        must_reply_tokens = ["عمر", "ريمي", "gg", "جي جي", "صور", "صوت", "ريكورد", "فويس", "احكي", "قولي", "رايك"]
        if any(tok in norm_stripped for tok in must_reply_tokens):
            return False, None

        # Case A: Dead-end short closure phrase ('تمام', 'ماشي', 'اوك', etc.)
        if norm_stripped in self.DEAD_END_SINGLE_PHRASES:
            # 65% leave a casual reaction (👍 / 👌 / ❤️), 35% pure Seen (✓✓)
            emoji = random.choice(["👍", "👌", "❤️", None, None])
            return True, emoji

        # Case B: Random sticker after an already active/wrapping conversation
        if media_type == "sticker" and is_active_conv:
            if random.random() < 0.55:
                emoji = random.choice(["😂", "❤️", "👍", None])
                return True, emoji

        return False, None

    def _register_telethon_handlers(self) -> None:""",
"mtproto: Phase 1/2/Selective filter helpers added")

# 1c. Replace the hardcoded 1-3s Seen block in on_new_message with Phase 1 + Selective Reply Filter
m = sub(m,
"""            # 1. Authentic Human Read-Receipt (Seen) via MTProto after 1-3 seconds
            seen_delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(seen_delay)
            from telethon import functions
            try:
                await self.client(functions.messages.ReadHistoryRequest(peer=event.chat_id, max_id=event.id))
                logger.info(f"✓✓ Seen marked via MTProto for chat [{event.chat_id}] (Msg ID: {event.id})")
            except Exception as rx:
                logger.debug(f"ReadHistoryRequest notice: {rx}")""",
"""            # 1. Task 2.1 Phase 1 — Variable Unseen Delay before marking ✓✓ Seen
            if event.is_private:
                unseen_delay, is_active_conv = self.compute_userbot_phase1_unseen_delay(event.chat_id, sender_id)
            else:
                # In groups, mark seen within 2-8s if active or 5-18s if idle so group turn election stays natural
                last_g_ts = self._userbot_last_conv_ts.get(event.chat_id, 0.0)
                is_active_conv = (time.time() - last_g_ts) < 120.0
                unseen_delay = random.uniform(2.0, 6.0) if is_active_conv else random.uniform(5.0, 15.0)

            logger.info(
                f"⏳ [Userbot Phase 1: Unseen Delay] Waiting {unseen_delay:.1f}s before ✓✓ Seen "
                f"in chat [{event.chat_id}] (active_conv={is_active_conv}, Msg ID: {event.id})..."
            )
            await asyncio.sleep(unseen_delay)
            from telethon import functions
            try:
                await self.client.send_read_acknowledge(event.chat_id, max_id=event.id)
                logger.info(f"✓✓ [Userbot Phase 1: Seen] Marked Seen via send_read_acknowledge for chat [{event.chat_id}] (Msg ID: {event.id})")
            except Exception:
                try:
                    await self.client(functions.messages.ReadHistoryRequest(peer=event.chat_id, max_id=event.id))
                    logger.info(f"✓✓ [Userbot Phase 1: Seen] Marked Seen via ReadHistoryRequest for chat [{event.chat_id}] (Msg ID: {event.id})")
                except Exception as rx:
                    logger.debug(f"ReadHistoryRequest notice: {rx}")

            self._userbot_last_conv_ts[event.chat_id] = time.time()

            # 1.5 Task 2.1 (4) — Selective Human Reply Filter for dead-end messages in private chat
            if event.is_private:
                skip_reply, react_emoji = self.evaluate_selective_reply_filter(
                    message_text=msg_text,
                    media_type=media_type,
                    sender_id=sender_id,
                    is_active_conv=is_active_conv,
                )
                if skip_reply:
                    if react_emoji:
                        await asyncio.sleep(random.uniform(1.5, 4.0))
                        await self.send_reaction(
                            chat_id=event.chat_id,
                            message_id=event.id,
                            emoji=react_emoji,
                            is_userbot=True,
                            userbot_client=self.client,
                        )
                    logger.info(
                        f"🤫 [Userbot Selective Reply Filter] Dead-end message '{msg_text[:30]}' from [{sender_name}] "
                        f"left on ✓✓ Seen (reaction={react_emoji}) without text reply."
                    )
                    return""",
"mtproto: on_new_message Phase 1 unseen delay + send_read_acknowledge + selective reply filter")

# 1d. Upgrade send_typing_indicator for Phase 3 continuous SendMessageTypingAction up to 25s
m = sub(m,
"""        sleep_dur = max(0.8, min(duration_sec, 6.0))
        if self._mock_mode:
            logger.debug(f"[Simulation] Typing in chat {chat_id} for {sleep_dur}s...")
            await asyncio.sleep(min(sleep_dur, 2.0))
            return

        if is_userbot or userbot_client is not None:
            active = userbot_client or self.client
            if active:
                try:
                    async with active.action(chat_id, "typing"):
                        await asyncio.sleep(sleep_dur)
                except Exception as exc:
                    logger.debug(f"Telethon typing action exception: {exc}")
            return""",
"""        max_cap = 25.0 if (is_userbot or userbot_client is not None) else 6.0
        sleep_dur = max(0.8, min(duration_sec, max_cap))
        if self._mock_mode:
            logger.debug(f"[Simulation] Typing in chat {chat_id} for {sleep_dur}s...")
            await asyncio.sleep(min(sleep_dur, 2.0))
            return

        if is_userbot or userbot_client is not None:
            active = userbot_client or self.client
            if active:
                try:
                    from telethon import functions, types
                    remaining = sleep_dur
                    while remaining > 0:
                        try:
                            await active(
                                functions.messages.SetTypingRequest(
                                    peer=chat_id,
                                    action=types.SendMessageTypingAction(),
                                )
                            )
                        except Exception:
                            pass
                        step = min(4.0, remaining)
                        await asyncio.sleep(step)
                        remaining -= step
                except Exception as exc:
                    logger.debug(f"Telethon typing action exception: {exc}")
            return""",
"mtproto: send_typing_indicator continuous SendMessageTypingAction loop")

# 1e. Upgrade dispatch_burst_messages for Phase 3 (~3.5 to 5 chars/sec) and inter-bubble pauses
m = sub(m,
"""            # 1. Simulate human typing latency proportional to word count
            words_cnt = len(burst.text.split())
            dynamic_typing_dur = max(burst.typing_delay_sec, min(words_cnt * 0.20, 5.0))
            await self.send_typing_indicator(
                chat_id, dynamic_typing_dur, is_userbot=is_userbot, userbot_client=userbot_client
            )""",
"""            # 1. Task 2.1 Phase 3 — Realistic Slow Human Typing (~3.5 to 5 chars/sec for Userbot)
            if is_userbot or userbot_client is not None:
                cps = random.uniform(3.5, 5.0)
                char_count = max(1, len(burst.text))
                dynamic_typing_dur = max(1.5, min(char_count / cps, 24.0))
                logger.info(
                    f"⌨️ [Userbot Phase 3: Slow Typing] {char_count} chars at {cps:.2f} chars/sec "
                    f"-> typing for {dynamic_typing_dur:.1f}s in chat [{chat_id}]"
                )
            else:
                words_cnt = len(burst.text.split())
                dynamic_typing_dur = max(burst.typing_delay_sec, min(words_cnt * 0.20, 5.0))
            await self.send_typing_indicator(
                chat_id, dynamic_typing_dur, is_userbot=is_userbot, userbot_client=userbot_client
            )""",
"mtproto: dispatch_burst_messages Phase 3 ~3.5-5 chars/sec")

m = sub(m,
"""            # Snappy micro-pause between bubbles
            if i < len(bursts) - 1:
                await asyncio.sleep(random.uniform(0.2, 0.5))""",
"""            if is_userbot or userbot_client is not None:
                self._userbot_last_conv_ts[chat_id] = time.time()

            # Realistic pause between multi-bubble messages
            if i < len(bursts) - 1:
                if is_userbot or userbot_client is not None:
                    await asyncio.sleep(random.uniform(1.8, 3.8))
                else:
                    await asyncio.sleep(random.uniform(0.2, 0.5))""",
"mtproto: inter-bubble pause & conv timestamp update")

ww(MTP, m)

# ───────────────────────── 2. dm_handler.py ─────────────────────────
d = rw(DMH)

d = sub(d,
"""        # 4. Delayed Read Receipt (Seen simulation)
        seen_delay = random.uniform(1.0, 3.5)
        await mtproto_manager.mark_seen(chat_id=sender_id, max_id=message_id, delay_sec=seen_delay)

        # 5. Run cognitive engine with user's private persona
        resp = await cognitive_orchestrator.process_incoming_event(""",
"""        # 4. Delayed Read Receipt (Seen simulation)
        # Note: For Userbot, Phase 1 (variable unseen delay + send_read_acknowledge) already ran in on_new_message.
        if not is_userbot:
            seen_delay = random.uniform(1.0, 3.5)
            await mtproto_manager.mark_seen(chat_id=sender_id, max_id=message_id, delay_sec=seen_delay)

        think_phase_started_at = time.time() if is_userbot else 0.0

        # 5. Run cognitive engine with user's private persona
        resp = await cognitive_orchestrator.process_incoming_event(""",
"dm_handler: avoid duplicate mark_seen for userbot + track think_phase_started_at")

d = sub(d,
"""        # 6. Emotional Ghosting is completely disabled: Every DM receives an authentic human reply
        active_persona_display = target_bot_name if is_userbot else (tenant_persona.persona_name if tenant_persona else "عمر")
        if resp.decision_type in ("GHOST_SEEN", "IGNORE"):
            logger.info(f"Ghosting disabled: Overriding {resp.decision_type} to REPLY for [{sender_name}] in DM.")
            resp.decision_type = "REPLY" """,
"""        # 6. Selective Reply vs Reply Handling
        active_persona_display = target_bot_name if is_userbot else (tenant_persona.persona_name if tenant_persona else "عمر")
        if resp.decision_type in ("GHOST_SEEN", "IGNORE"):
            if is_userbot and sender_id != 8287744705:
                logger.info(f"🤫 [Userbot Selective Reply] Respecting {resp.decision_type} for [{sender_name}] in DM (left on ✓✓ Seen).")
                return
            logger.info(f"Ghosting disabled for official bot: Overriding {resp.decision_type} to REPLY for [{sender_name}] in DM.")
            resp.decision_type = "REPLY"

        # 6.5 Task 2.1 Phase 2 — Human Thinking Pause (After ✓✓ Seen, Before Typing...)
        if is_userbot and resp.raw_response_text and resp.decision_type not in ("GHOST_SEEN", "IGNORE", "REACT_ONLY"):
            target_think_sec = mtproto_manager.compute_userbot_phase2_think_delay(
                message_text=message_text,
                sender_id=sender_id,
                chat_id=sender_id,
            )
            elapsed_llm = (time.time() - think_phase_started_at) if think_phase_started_at > 0 else 0.0
            remaining_think = max(1.5, target_think_sec - elapsed_llm)
            logger.info(
                f"🧠 [Userbot Phase 2: Thinking Pause] User sees ✓✓ Seen while {target_bot_name} thinks for "
                f"{remaining_think:.1f}s (total target={target_think_sec:.1f}s, llm_took={elapsed_llm:.1f}s) before Typing..."
            )
            await asyncio.sleep(remaining_think)""",
"dm_handler: Phase 2 human thinking pause (15-75s) + selective reply support")

# Ensure `import time` is in dm_handler.py
if "import time" not in d:
    d = sub(d, "import random\n", "import random\nimport time\n", "dm_handler: import time")

ww(DMH, d)

# ───────────────────────── 3. human_typer.py ─────────────────────────
h = rw(HTY)
h = sub(h,
"""    @classmethod
    def calculate_typing_delay(
        cls,
        text: str,
        wpm_base: int = 160,
        is_shy: bool = False,
    ) -> float:
        \"\"\"
        Calculates ultra-responsive, snappy human typing duration (0.4s to 1.5s max).
        Fast enough to feel instant while preserving authentic human typing UX.
        \"\"\"
        word_count = max(1, len(text.split()))
        jitter = random.uniform(0.3, 0.6)
        total_delay = max(0.4, min(1.5, (word_count * 0.05) + jitter))
        if is_shy:
            total_delay = min(1.8, total_delay + 0.3)
        return round(total_delay, 2)""",
"""    @classmethod
    def calculate_typing_delay(
        cls,
        text: str,
        wpm_base: int = 160,
        is_shy: bool = False,
        is_userbot: bool = False,
    ) -> float:
        \"\"\"
        Calculates human typing duration.
        For Userbot: realistic human speed (~3.5 to 5.0 characters per second).
        For Official Bots: responsive typing duration.
        \"\"\"
        if is_userbot:
            cps = random.uniform(3.5, 5.0)
            char_len = max(1, len(text))
            total_delay = max(1.5, min(24.0, char_len / cps))
            if is_shy:
                total_delay = min(25.0, total_delay + 1.2)
            return round(total_delay, 2)

        word_count = max(1, len(text.split()))
        jitter = random.uniform(0.3, 0.6)
        total_delay = max(0.4, min(1.5, (word_count * 0.05) + jitter))
        if is_shy:
            total_delay = min(1.8, total_delay + 0.3)
        return round(total_delay, 2)""",
"human_typer: realistic ~3.5-5 chars/sec calculate_typing_delay")

ww(HTY, h)
print("Done Task 2.1 patch.")

