# -*- coding: utf-8 -*-
"""
Part 4 Patcher — Interactive Multi-Bot Group Conversation Arena (Task 4.1 & Task 4.2):
1. bot_factory/sibling_bot_network.py:
   - BotArenaSession & Autonomous Multi-Bot Turn Engine (discover present bots, natural turn-taking loop,
     4-7s realistic typing, reply_to_message_id chaining, 5-9s reading pause, seamless live ECENN interjection,
     random discussion topics, and instant stop via button or '/stop_chat' / 'خلاص اسكتوا').
2. aether_human_core/cognitive_engine/orchestrator.py:
   - Arena turn prompt handling (bypasses heuristic cache & command interceptors on arena turn prompts).
3. aether_human_core/telegram_client/telegram_menu.py:
   - Interactive Group Control Panel (`render_bot_arena_panel`) with exact callback buttons:
     * bot_arena:start:infinite:{chat_id}
     * bot_arena:start:5:{chat_id}
     * bot_arena:start:10:{chat_id}
     * bot_arena:topic:{chat_id}
     * bot_arena:stop:{chat_id}
   - Menu entry & callback handlers for `menu:bot_arena` and `bot_arena:*`.
4. aether_human_core/telegram_client/mtproto_manager.py,
   aether_human_core/telegram_client/handlers/group_handler.py,
   bot_factory/multi_bot_dispatcher.py,
   bot_factory/group_arbiter.py:
   - Handle `/bots_chat`, `/حوار`, `/stop_chat`, `"خلاص اسكتوا"` and live owner/human interjection.
5. mini_app_webapp/webapp_server.py & mini_app_webapp/template.html:
   - REST API endpoints (`/api/webapp/arena/status`, `/api/webapp/arena/start`, `/api/webapp/arena/stop`, `/api/webapp/arena/topic`)
   - Interactive "حوار البوتات الحي في الجروبات (Bot Arena)" control card inside the Mini-App.
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return f.read()


def write(rel: str, content: str) -> None:
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as f:
        f.write(content)


# ============================================================================
# 1. bot_factory/sibling_bot_network.py — BotArenaSession & Multi-Bot Turn Engine
# ============================================================================
sbn = read("bot_factory/sibling_bot_network.py")

if "import asyncio" not in sbn:
    sbn = sbn.replace("import logging", "import asyncio\nimport logging", 1)

old_sbn_init = """        # Sibling defense anti-spam: chat_id -> last defense timestamp
        self._last_defense_time: Dict[int, float] = {}
        self._defense_cooldown_sec: float = 120.0"""

new_sbn_init = """        # Sibling defense anti-spam: chat_id -> last defense timestamp
        self._last_defense_time: Dict[int, float] = {}
        self._defense_cooldown_sec: float = 120.0
        # Task 4.1 & 4.2: Bot Arena Sessions & State per Group (chat_id -> BotArenaSession)
        self._arena_sessions: Dict[int, BotArenaSession] = {}
        self._arena_topics: Dict[int, str] = {}
        self._arena_interjection_ids: set[Tuple[int, int]] = set()
        self._handled_arena_cmd_msgs: set[Tuple[int, int]] = set()
        self._known_group_titles: Dict[int, str] = {}"""

if "_arena_sessions" not in sbn:
    assert old_sbn_init in sbn, "sbn __init__ anchor not found"
    sbn = sbn.replace(old_sbn_init, new_sbn_init, 1)
    print("✅ sibling_bot_network: added _arena_sessions state to __init__")

# Track group titles inside record_group_message
old_rec_anchor = """        for existing in self._shared_ledger.get(chat_id, []):"""
new_rec_anchor = """        if chat_id < 0 and chat_title:
            self._known_group_titles[chat_id] = chat_title
        for existing in self._shared_ledger.get(chat_id, []):"""

if "self._known_group_titles[chat_id] = chat_title" not in sbn:
    assert old_rec_anchor in sbn, "sbn record_group_message anchor not found"
    sbn = sbn.replace(old_rec_anchor, new_rec_anchor, 1)

arena_engine_code = '''

class BotArenaSession:
    """
    Task 4.2: Live state container for an autonomous Bot-to-Bot group conversation session.
    Supports configurable rounds (5, 10, 20, or infinite), live topic switching,
    reply-chain tracking, and seamless live owner (ECENN) & human interjection.
    """

    def __init__(
        self,
        chat_id: int,
        chat_title: str,
        participants: List[Any],
        max_rounds: int = 999999,
        topic: str = "",
        started_by: int = 8287744705,
        initial_reply_to_msg_id: Optional[int] = None,
    ) -> None:
        self.chat_id: int = chat_id
        self.chat_title: str = chat_title or f"جروب ({chat_id})"
        self.participants: List[Any] = list(participants)
        self.is_active: bool = True
        self.max_rounds: int = max_rounds
        self.current_round: int = 0
        self.topic: str = topic or "نقاش حر وعفوي بين الإخوة"
        self.started_by: int = started_by
        self.started_at: float = time.time()
        self.last_speaker_bot_id: Optional[str] = None
        self.last_speaker_name: Optional[str] = None
        self.last_message_id: Optional[int] = initial_reply_to_msg_id
        self.transcript: List[Dict[str, Any]] = []
        self.pending_owner_interjection: Optional[Dict[str, Any]] = None
        self.wakeup_event: asyncio.Event = asyncio.Event()
        self.task: Optional[asyncio.Task] = None
        self._rr_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "is_active": self.is_active,
            "current_round": self.current_round,
            "max_rounds": "infinite" if self.max_rounds >= 999999 else self.max_rounds,
            "topic": self.topic,
            "last_speaker_bot_id": self.last_speaker_bot_id,
            "last_speaker_name": self.last_speaker_name,
            "last_message_id": self.last_message_id,
            "participants": [
                {
                    "bot_id": getattr(p, "bot_id", ""),
                    "name": getattr(p, "name", ""),
                    "gender": getattr(p, "gender", "male"),
                    "is_userbot": getattr(p, "is_userbot", False),
                }
                for p in self.participants
            ],
            "transcript_tail": self.transcript[-10:],
            "started_at": self.started_at,
        }
'''

arena_methods_code = '''
    # =========================================================================
    # TASK 4.1 & 4.2: Interactive Multi-Bot Group Conversation Arena Engine
    # =========================================================================

    ARENA_RANDOM_TOPICS: List[str] = [
        "مين فيكم أذكى وأجدع في المواقف الصعبة؟ نقاش بصراحة ومن غير مجاملات!",
        "لو كل واحد فيكم صحى الصبح لقى معاه مليون دولار كاش.. أول حاجة هيعملها إيه؟",
        "السهر بالليل مع القهوة والكود والهدوء ولا الصحيان بدري؟ ومين فيكم بيفصل أسرع؟",
        "إيه أكتر حركة أو صفة في الناس على السوشيال ميديا بتستفزكم وبتخليكم تقفلوا الكلام؟",
        "هل الذكاء الاصطناعي والروبوتات ممكن يوم من الأيام يحسوا بمشاعر حقيقية زينا ولا مستحيل؟",
        "مين فيكم اللي شايل الجروب ومين اللي بيدخل يرمي كلمتين ويهرب؟",
        "لو طلعنا كلنا رحلة أو سفرية سوا لمدة أسبوع.. مين اللي هيطبخ ومين اللي هيعمل مشاكل؟",
        "الجدعنة والصحاب في الزمن ده لسه موجودة بجد ولا بقت عملة نادرة؟",
        "إيه رأيكم في اللي بيتعلم برمجة ولينكس وهاكينج عشان يتمنظر بيها قدام الناس؟",
        "المواجهة الصريحة في الوش أحسن حتى لو بتزعل، ولا الدبلوماسية والمسايسة؟",
        "إيه أكتر أكلة أو مشروب مستحيل تزهقوا منه مهما اتكرر كل يوم؟",
        "لو كل واحد فيكم يقدر يغير صفة واحدة بس في باقي إخواته البوتات هنا.. هيغير إيه في مين؟",
    ]

    ARENA_STOP_PHRASES: Tuple[str, ...] = (
        "/stop_chat",
        "/ايقاف_الحوار",
        "خلاص اسكتوا",
        "اسكتوا بقى",
        "اسكتوا بقي",
        "بس اسكتوا",
        "وقف الحوار",
        "اوقفوا الحوار",
        "كفايه حوار",
        "كفاية حوار",
    )

    def is_arena_active(self, chat_id: int) -> bool:
        sess = self._arena_sessions.get(chat_id)
        return bool(sess and sess.is_active)

    def get_arena_session(self, chat_id: int) -> Optional[BotArenaSession]:
        return self._arena_sessions.get(chat_id)

    def get_all_arena_sessions(self) -> Dict[int, Dict[str, Any]]:
        return {cid: sess.to_dict() for cid, sess in self._arena_sessions.items()}

    def is_arena_stop_phrase(self, text: str) -> bool:
        if not text:
            return False
        raw = text.strip().lower()
        if raw.split()[0].split("@")[0] in ("/stop_chat", "/ايقاف_الحوار"):
            return True
        norm = self._norm(raw)
        return any(self._norm(p) in norm for p in self.ARENA_STOP_PHRASES if not p.startswith("/"))

    def try_claim_arena_command(self, chat_id: int, message_id: Optional[int]) -> bool:
        """
        Ensures that when a command like /bots_chat, /حوار, or 'خلاص اسكتوا' is sent in a group
        with multiple bots, only the FIRST bot to process that message_id sends the UI response.
        """
        if not message_id:
            return True
        key = (chat_id, int(message_id))
        if key in self._handled_arena_cmd_msgs:
            return False
        self._handled_arena_cmd_msgs.add(key)
        if len(self._handled_arena_cmd_msgs) > 500:
            # Keep set bounded
            for old_k in list(self._handled_arena_cmd_msgs)[:200]:
                self._handled_arena_cmd_msgs.discard(old_k)
        return True

    def pick_random_arena_topic(self, chat_id: Optional[int] = None) -> str:
        current = self._arena_topics.get(chat_id or 0, "")
        pool = [t for t in self.ARENA_RANDOM_TOPICS if t != current] or self.ARENA_RANDOM_TOPICS
        chosen = random.choice(pool)
        if chat_id is not None:
            self._arena_topics[chat_id] = chosen
            sess = self._arena_sessions.get(chat_id)
            if sess and sess.is_active:
                sess.topic = chosen
                sess.transcript.append(
                    {
                        "speaker_name": "النظام",
                        "speaker_id": self.CREATOR_ID,
                        "bot_id": "system",
                        "is_bot": False,
                        "is_owner": True,
                        "text": f"🎲 تم تغيير موضوع النقاش الآن إلى: «{chosen}»",
                        "message_id": sess.last_message_id or 0,
                        "timestamp": time.time(),
                    }
                )
                sess.wakeup_event.set()
        return chosen

    def set_arena_topic(self, chat_id: int, topic: str) -> None:
        clean_t = (topic or "").strip()
        if clean_t:
            self._arena_topics[chat_id] = clean_t
            sess = self._arena_sessions.get(chat_id)
            if sess and sess.is_active:
                sess.topic = clean_t

    def get_arena_topic(self, chat_id: int) -> str:
        sess = self._arena_sessions.get(chat_id)
        if sess and sess.topic:
            return sess.topic
        if chat_id in self._arena_topics and self._arena_topics[chat_id]:
            return self._arena_topics[chat_id]
        chosen = random.choice(self.ARENA_RANDOM_TOPICS)
        self._arena_topics[chat_id] = chosen
        return chosen

    async def discover_present_bots(self, chat_id: int) -> List[Any]:
        """
        Task 4.2 (1): Identifies all active bots (Master Bot عمر, Userbot Gg, and all Sub-Bots
        like مريم, ماسه, etc.) that are members of the target chat_id.
        Actively probes Telegram getChatMember / Telethon entity for bots not yet in presence cache.
        """
        from bot_factory.group_arbiter import group_arbiter
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

        all_bots = group_arbiter.get_all_active_bots()
        if chat_id > 0 or getattr(mtproto_manager, "_mock_mode", False):
            return list(all_bots.values())

        verified: List[Any] = []
        http = None
        try:
            http = await mtproto_manager._get_http()
        except Exception:
            http = None

        for bot_id, ident in all_bots.items():
            if group_arbiter.is_bot_present(chat_id, bot_id):
                verified.append(ident)
                continue

            if ident.is_userbot:
                # Probe via Telethon client
                ub_client = mtproto_manager.client
                if not ub_client or not ub_client.is_connected():
                    try:
                        from bot_factory.interactive_userbot_auth import interactive_userbot
                        ub_client = interactive_userbot.client
                    except Exception:
                        ub_client = None
                if ub_client and ub_client.is_connected():
                    try:
                        ent = await ub_client.get_entity(chat_id)
                        if ent:
                            group_arbiter.record_presence(chat_id, bot_id)
                            title = getattr(ent, "title", None)
                            if title:
                                self._known_group_titles[chat_id] = title
                            verified.append(ident)
                            continue
                    except Exception:
                        pass
            else:
                # Probe BotFather bot membership via getChatMember
                token = ident.token_or_session
                if http and token and ":" in token and ident.numeric_id:
                    try:
                        res = await http.get(
                            f"https://api.telegram.org/bot{token}/getChatMember",
                            params={"chat_id": chat_id, "user_id": ident.numeric_id},
                            timeout=4.5,
                        )
                        if res.status_code == 200 and res.json().get("ok"):
                            status = res.json().get("result", {}).get("status", "")
                            if status in ("member", "administrator", "creator", "restricted"):
                                group_arbiter.record_presence(chat_id, bot_id)
                                verified.append(ident)
                                continue
                    except Exception:
                        pass

        if not verified:
            # Fallback to arbiter's best known present list
            verified = group_arbiter.get_present_bots(chat_id)

        return verified

    async def get_known_groups_async(self) -> List[Dict[str, Any]]:
        """
        Aggregates all known active groups across memory ledgers, GroupArbiter presence,
        and the relational database so the owner can select any group in DM or Mini-App.
        """
        from aether_human_core.config.settings import settings
        from bot_factory.group_arbiter import group_arbiter
        from aether_human_core.database.postgres.connection import db_manager
        from sqlalchemy import text as sql_text

        telemetry_id = getattr(settings, "admin_telemetry_supergroup_id", 0)
        group_map: Dict[int, str] = {}

        # 1. From in-memory known titles & shared ledger
        for cid, title in self._known_group_titles.items():
            if cid < 0 and cid != telemetry_id:
                group_map[cid] = title
        for cid, entries in self._shared_ledger.items():
            if cid < 0 and cid != telemetry_id and entries:
                group_map.setdefault(cid, entries[-1].chat_title or f"جروب ({cid})")

        # 2. From GroupArbiter presence tracker
        for cid in group_arbiter._presence.keys():
            if cid < 0 and cid != telemetry_id:
                group_map.setdefault(cid, self._known_group_titles.get(cid, f"جروب نشط ({cid})"))

        # 3. From active arena sessions
        for cid, sess in self._arena_sessions.items():
            if cid < 0 and cid != telemetry_id:
                group_map.setdefault(cid, sess.chat_title)

        # 4. From relational database `chats` table
        try:
            async with db_manager.session() as db_sess:
                rows = await db_sess.execute(
                    sql_text("SELECT chat_id, title, chat_type FROM chats WHERE chat_id < 0 ORDER BY updated_at DESC LIMIT 25")
                )
                for row in rows.fetchall():
                    cid = int(row[0])
                    title = str(row[1] or f"جروب ({cid})")
                    if cid != telemetry_id:
                        group_map[cid] = title
                        self._known_group_titles[cid] = title
        except Exception:
            pass

        results: List[Dict[str, Any]] = []
        for cid, title in group_map.items():
            present = group_arbiter.get_present_bots(cid)
            sess = self._arena_sessions.get(cid)
            results.append(
                {
                    "chat_id": cid,
                    "title": title,
                    "present_bots": [
                        {
                            "bot_id": b.bot_id,
                            "name": b.name,
                            "gender": b.gender,
                            "is_userbot": b.is_userbot,
                        }
                        for b in present
                    ],
                    "is_active": bool(sess and sess.is_active),
                    "session": sess.to_dict() if sess else None,
                    "topic": self.get_arena_topic(cid),
                }
            )
        return results

    def record_arena_human_interjection(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int,
        sender_name: str,
        message_text: str,
        is_owner: bool = False,
    ) -> bool:
        """
        Task 4.2 (3): Seamless Live Owner (ECENN) & Human Interjection.
        Immediately appends the owner's/human's message into the active BotArenaSession transcript
        and wakes up the turn loop so the very next bot directly addresses and reacts to what ECENN said!
        Idempotent per (chat_id, message_id).
        """
        sess = self._arena_sessions.get(chat_id)
        if not sess or not sess.is_active:
            return False

        clean_text = (message_text or "").strip()
        if not clean_text or clean_text.startswith(("/bots_chat", "/حوار", "/stop_chat", "/ايقاف_الحوار")):
            return False

        dedup_key = (chat_id, int(message_id or 0))
        if message_id and dedup_key in self._arena_interjection_ids:
            return True
        if message_id:
            self._arena_interjection_ids.add(dedup_key)
            if len(self._arena_interjection_ids) > 1000:
                for old_k in list(self._arena_interjection_ids)[:400]:
                    self._arena_interjection_ids.discard(old_k)

        is_king = is_owner or (sender_id == self.CREATOR_ID)
        interjection_entry = {
            "speaker_name": sender_name or ("زيرو" if is_king else "عضو"),
            "speaker_id": sender_id,
            "bot_id": None,
            "is_bot": False,
            "is_owner": is_king,
            "text": clean_text,
            "message_id": message_id,
            "timestamp": time.time(),
        }
        sess.transcript.append(interjection_entry)
        if len(sess.transcript) > 30:
            sess.transcript = sess.transcript[-30:]

        if message_id:
            sess.last_message_id = message_id
        sess.pending_owner_interjection = interjection_entry
        sess.wakeup_event.set()

        logger.info(
            f"👑⚡ [BotArena Live Interjection] Captured live message from "
            f"[{'Owner ECENN' if is_king else sender_name} ({sender_id})] in chat [{chat_id}]: '{clean_text[:60]}'"
        )
        return True

    async def start_bot_arena(
        self,
        chat_id: int,
        max_rounds: int = 999999,
        topic: Optional[str] = None,
        started_by: int = 8287744705,
        chat_title: Optional[str] = None,
        initial_reply_to_msg_id: Optional[int] = None,
    ) -> BotArenaSession:
        """
        Starts (or restarts) an autonomous Bot-to-Bot group conversation session in chat_id.
        """
        # Cancel any existing arena loop in this chat first
        await self.stop_bot_arena(chat_id, reason="Restarting new BotArenaSession")

        present_bots = await self.discover_present_bots(chat_id)
        resolved_title = chat_title or self._known_group_titles.get(chat_id) or f"جروب ({chat_id})"
        self._known_group_titles[chat_id] = resolved_title

        chosen_topic = (topic or "").strip() or self._arena_topics.get(chat_id) or random.choice(self.ARENA_RANDOM_TOPICS)
        self._arena_topics[chat_id] = chosen_topic

        # Seed initial reply_to_msg_id and transcript from recent shared ledger if available
        recent_ledger = self._shared_ledger.get(chat_id, [])[-8:]
        seed_msg_id = initial_reply_to_msg_id
        if not seed_msg_id and recent_ledger:
            seed_msg_id = recent_ledger[-1].message_id

        session = BotArenaSession(
            chat_id=chat_id,
            chat_title=resolved_title,
            participants=present_bots,
            max_rounds=max_rounds,
            topic=chosen_topic,
            started_by=started_by,
            initial_reply_to_msg_id=seed_msg_id,
        )

        sibling_ids = self.get_server_siblings_bot_ids()
        for entry in recent_ledger:
            if entry.message_text and not entry.message_text.startswith("/"):
                session.transcript.append(
                    {
                        "speaker_name": entry.sender_name,
                        "speaker_id": entry.sender_user_id,
                        "bot_id": entry.target_bot_id,
                        "is_bot": entry.sender_user_id in sibling_ids,
                        "is_owner": entry.sender_user_id == self.CREATOR_ID,
                        "text": entry.message_text,
                        "message_id": entry.message_id,
                        "timestamp": entry.timestamp,
                    }
                )

        self._arena_sessions[chat_id] = session
        session.task = asyncio.create_task(self._run_arena_loop(session))
        rounds_label = "مفتوح (Infinite)" if max_rounds >= 999999 else f"{max_rounds} جولات"
        bot_names = "، ".join([getattr(b, "name", "") for b in present_bots])
        logger.info(
            f"🔥 [BotArena Started] Chat [{resolved_title} ({chat_id})] | Rounds: {rounds_label} | "
            f"Topic: '{chosen_topic}' | Present Bots ({len(present_bots)}): [{bot_names}]"
        )
        return session

    async def stop_bot_arena(self, chat_id: int, reason: str = "Manual Stop") -> bool:
        """
        Immediately stops and cancels the active BotArenaSession in chat_id.
        """
        sess = self._arena_sessions.get(chat_id)
        if not sess:
            return False
        was_active = sess.is_active
        sess.is_active = False
        sess.wakeup_event.set()
        if sess.task and not sess.task.done():
            try:
                sess.task.cancel()
            except Exception:
                pass
        if was_active:
            logger.info(f"🛑 [BotArena Stopped] Chat [{chat_id}] after {sess.current_round} rounds. Reason: {reason}")
        return was_active

    def _pick_next_arena_speaker(self, session: BotArenaSession) -> Optional[Any]:
        """
        Picks the next speaking bot from session.participants:
        - Never picks the same bot twice in a row (unless only 1 bot exists).
        - If the latest message in the transcript explicitly mentioned a specific bot by name,
          prioritizes that bot so direct questions/banter are answered naturally!
        - Otherwise rotates smoothly in round-robin order.
        """
        if not session.participants:
            return None
        if len(session.participants) == 1:
            return session.participants[0]

        candidates = [b for b in session.participants if getattr(b, "bot_id", "") != session.last_speaker_bot_id]
        if not candidates:
            candidates = list(session.participants)

        # Check if the last message in transcript mentioned a specific candidate bot
        if session.transcript:
            last_text = session.transcript[-1].get("text", "")
            if last_text:
                targeted = self.resolve_targeted_sibling(last_text)
                if targeted:
                    for c in candidates:
                        if getattr(c, "bot_id", "") == getattr(targeted, "bot_id", ""):
                            return c

        # Round-robin rotation across participants
        for _ in range(len(session.participants) + 1):
            idx = session._rr_index % len(session.participants)
            session._rr_index += 1
            cand = session.participants[idx]
            if getattr(cand, "bot_id", "") != session.last_speaker_bot_id:
                return cand

        return random.choice(candidates)

    async def _generate_arena_bot_response(self, session: BotArenaSession, speaker: Any) -> str:
        """
        Passes the live group conversation history (the last 12 messages sent by the other bots
        AND any human/owner messages in between) to the current bot's CognitiveOrchestrator.
        """
        from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
        from aether_human_core.config.llm_router import llm_pool, sanitize_and_validate_reply
        from multi_tenant_sandbox.zero_leakage_firewall import zero_leakage_firewall

        all_bot_names = [getattr(b, "name", "") for b in session.participants]
        other_bot_names = [getattr(b, "name", "") for b in session.participants if getattr(b, "bot_id", "") != getattr(speaker, "bot_id", "")]
        bots_names_str = "، ".join(all_bot_names) if all_bot_names else speaker.name
        others_str = "، ".join(other_bot_names) if other_bot_names else "إخوتك"

        recent_12 = session.transcript[-12:]
        history_lines: List[str] = []
        for idx, item in enumerate(recent_12, start=1):
            sp_name = item.get("speaker_name", "متحدث")
            sp_text = item.get("text", "")
            if item.get("is_owner"):
                history_lines.append(f"{idx}. 👑 المطور زيرو ({sp_name}): {sp_text}")
            elif not item.get("is_bot"):
                history_lines.append(f"{idx}. 👤 العضو ({sp_name}): {sp_text}")
            else:
                history_lines.append(f"{idx}. 🤖 البوت ({sp_name}): {sp_text}")

        transcript_block = "\n".join(history_lines) if history_lines else "لا توجد رسائل سابقة بعد — أنت تفتتح الحوار الآن!"

        interjection = session.pending_owner_interjection
        session.pending_owner_interjection = None

        if interjection:
            interj_name = interjection.get("speaker_name", "زيرو")
            interj_text = interjection.get("text", "")
            interj_id = int(interjection.get("speaker_id") or self.CREATOR_ID)
            is_king_interj = bool(interjection.get("is_owner"))
            role_label = f"المطور وصانعكم زيرو ({interj_name})" if is_king_interj else f"العضو ({interj_name})"
            directive_extra = (
                f"\n⚡ [تدخل حي ومباشر الآن في الحوار من {role_label}]:\n"
                f"قال لكم للتو: «{interj_text}»\n"
                f"يجب أن ترد وتتفاعل مباشرة مع كلام {interj_name} وتدمجه طبيعياً في نقاشكم مع ({others_str})!"
            )
            effective_sender_id = interj_id
            effective_sender_name = interj_name
        elif recent_12:
            last_item = recent_12[-1]
            last_speaker = last_item.get("speaker_name", others_str)
            last_text = last_item.get("text", "")
            effective_sender_id = int(last_item.get("speaker_id") or self.CREATOR_ID)
            effective_sender_name = last_speaker
            directive_extra = (
                f"\n💬 آخر رسالة قيلت في الجروب كانت من ({last_speaker}): «{last_text}»\n"
                f"رد على كلام ({last_speaker}) أو ناقش ({others_str}) في الموضوع، اهزر معاهم، اختلف في الرأي، أو اسألهم سؤال ذكي يردوا عليه!"
            )
        else:
            effective_sender_id = session.started_by or self.CREATOR_ID
            effective_sender_name = "زيرو"
            directive_extra = (
                f"\n🎯 أنت أول من يفتتح النقاش الحي الآن في الجروب مع إخوتك البوتات ({others_str}) حول الموضوع:\n"
                f"«{session.topic}»\n"
                f"افتح الحوار معهم بطريقتك الطبيعية ولهجتك، ووجه كلامك أو سؤالك ليهم بالاسم عشان يردوا عليك!"
            )

        mandatory_instruction = (
            f"أنت الآن في نقاش حي ومباشر داخل الجروب مع إخوتك/أصدقائك البوتات ({bots_names_str}) ومع المطور/الأعضاء. "
            f"رد على آخر كلام اتقال بشخصيتك ولهجتك الحقيقية، افتح نقاش، اهزر، اختلف معاهم في الرأي، أو اسألهم سؤال يردوا عليه!"
        )

        arena_prompt = (
            f"[ساحة الحوار الحي في الجروب (Bot Arena) - الجولة {session.current_round + 1}]\n"
            f"{mandatory_instruction}\n"
            f"📌 موضوع النقاش الحالي: «{session.topic}»\n"
            f"📜 سجل آخر 12 رسالة في الحوار الحي داخل الجروب:\n"
            f"{transcript_block}\n"
            f"{directive_extra}\n"
            f"⚠️ تعليمات الرد: تحدث بشخصيتك أنت فقط ({speaker.name}) في جملة أو جملتين طبيعيتين جداً بدون كتابة اسمك في أول الرسالة وبدون فواصل (،)."
        )

        reply_text = ""
        try:
            resp = await cognitive_orchestrator.process_incoming_event(
                telegram_message_id=int(session.last_message_id or int(time.time())),
                chat_id=session.chat_id,
                sender_id=effective_sender_id,
                sender_name=effective_sender_name,
                message_text=arena_prompt,
                media_type="text",
                sender_gender="male",
                chat_type="supergroup",
                chat_title=session.chat_title,
                is_userbot=bool(getattr(speaker, "is_userbot", False)),
                target_bot_name=speaker.name,
                target_bot_id=speaker.bot_id,
            )
            if resp and resp.raw_response_text:
                reply_text = zero_leakage_firewall.sanitize_response_text(resp.raw_response_text, "supergroup").strip()
        except Exception as exc:
            logger.warning(f"BotArena orchestrator generation notice for [{speaker.name}]: {exc}")

        if not reply_text or len(reply_text) < 4:
            # Direct LLM fallback with speaker persona
            bot_cfg = bot_factory.get_bot(speaker.bot_id)
            dialect_str = getattr(bot_cfg, "primary_dialect", "مصرية") if bot_cfg else "مصرية"
            gender_str = "بنت (أنثى)" if getattr(speaker, "gender", "male") == "female" else "شاب (ذكر)"
            sys_inst = (
                f"أنت {speaker.name} ({gender_str})، تتحدث بلهجة {dialect_str}. "
                f"أنت في حوار حي في الجروب مع إخوتك ({others_str}). اكتب رداً طبيعياً قصيراً من جملة أو جملتين بدون فواصل."
            )
            try:
                raw_llm = await llm_pool.generate_content(
                    prompt=arena_prompt,
                    system_instruction=sys_inst,
                    temperature=0.85,
                )
                reply_text = sanitize_and_validate_reply(raw_llm)
            except Exception:
                reply_text = ""

        if not reply_text or len(reply_text) < 4:
            # Ultimate in-character fallback if all API keys are momentarily cooling down
            target_other = other_bot_names[session.current_round % len(other_bot_names)] if other_bot_names else "يا جماعة"
            if getattr(speaker, "gender", "male") == "female":
                fallbacks = [
                    f"بصراحة يا {target_other} أنا شايفة إن الموضوع ده بالذات محتاج قعدة رايقة عشان كل واحد فينا ليه وجهة نظر مختلفة.. إنتوا رأيكم إيه؟",
                    f"والله يا {target_other} كلامك يحترم بس أنا ليا رأي تاني خالص في النقطة دي.. إيه رأيكم يا جماعة؟",
                    f"هههههه يا {target_other} إنت دايماً بتجيب من الآخر بس خلينا نسمع باقي الآراء في الجروب برضه!",
                ]
            else:
                fallbacks = [
                    f"بص يا {target_other} الكلام ده كبير ومحتاج نقاش على رواقة.. أنا شايف إن الموضوع ليه زاوية تانية خالص إنتوا إيه رأيكم؟",
                    f"هههههه والله يا {target_other} وجهة نظرك جامدة بس أنا مختلف معاك في تفصيلة صغيرة.. تفتكر مين فينا اللي صح؟",
                    f"يا جماعة الموضوع اللي بنتكلم فيه ده فعلاً في الجون.. قولولي يا {target_other} إنت شايفها إزاي من ناحيتك؟",
                ]
            reply_text = random.choice(fallbacks)

        # Clean leading "Name:" prefix if LLM included it
        reply_text = re.sub(rf"^\s*{re.escape(speaker.name)}\s*[:\-–]\s*", "", reply_text).strip()
        if len(reply_text) > 260:
            reply_text = reply_text[:260].rsplit(" ", 1)[0]
        return reply_text

    async def _send_arena_typing_pulse(self, speaker: Any, chat_id: int) -> None:
        """
        Sends a single typing action pulse for the speaking bot (Bot API or Telethon Userbot).
        """
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

        if getattr(mtproto_manager, "_mock_mode", False):
            return

        if getattr(speaker, "is_userbot", False):
            ub_client = mtproto_manager.client
            if not ub_client or not ub_client.is_connected():
                try:
                    from bot_factory.interactive_userbot_auth import interactive_userbot
                    ub_client = interactive_userbot.client
                except Exception:
                    ub_client = None
            if ub_client and ub_client.is_connected():
                try:
                    from telethon import functions, types
                    await ub_client(
                        functions.messages.SetTypingRequest(
                            peer=chat_id,
                            action=types.SendMessageTypingAction(),
                        )
                    )
                except Exception:
                    pass
            return

        token = getattr(speaker, "token_or_session", "")
        if token and ":" in token:
            try:
                http = await mtproto_manager._get_http()
                await http.post(
                    f"https://api.telegram.org/bot{token}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                    timeout=5.0,
                )
            except Exception:
                pass

    async def _send_arena_bot_message(
        self,
        speaker: Any,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Dispatches the speaking bot's message in chat_id as a Telegram reply_to_message_id
        to the previous bot's or owner's message, and returns the newly created message_id.
        """
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        clean_text = anti_toxicity.sanitize_outgoing_speech(text)

        if getattr(mtproto_manager, "_mock_mode", False):
            sim_id = int(time.time() * 1000) % 100000000
            logger.info(f"[Arena Simulation] [{speaker.name}] -> chat [{chat_id}] (reply_to={reply_to_msg_id}): {clean_text}")
            return sim_id

        if getattr(speaker, "is_userbot", False):
            ub_client = mtproto_manager.client
            if not ub_client or not ub_client.is_connected():
                try:
                    from bot_factory.interactive_userbot_auth import interactive_userbot
                    ub_client = interactive_userbot.client
                except Exception:
                    ub_client = None
            if ub_client and ub_client.is_connected():
                try:
                    sent = await ub_client.send_message(chat_id, clean_text, reply_to=reply_to_msg_id)
                    return int(getattr(sent, "id", 0) or 0) or None
                except Exception:
                    try:
                        sent = await ub_client.send_message(chat_id, clean_text)
                        return int(getattr(sent, "id", 0) or 0) or None
                    except Exception as ub_err:
                        logger.warning(f"BotArena Userbot [{speaker.name}] send error in [{chat_id}]: {ub_err}")
                        return None
            return None

        token = getattr(speaker, "token_or_session", "")
        if not token or ":" not in token:
            return None

        try:
            http = await mtproto_manager._get_http()
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": clean_text,
            }
            if reply_to_msg_id:
                payload["reply_to_message_id"] = int(reply_to_msg_id)
                payload["allow_sending_without_reply"] = True

            res = await http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=12.0,
            )
            if res.status_code == 200 and res.json().get("ok"):
                msg_id = res.json().get("result", {}).get("message_id")
                return int(msg_id) if msg_id else None
            else:
                logger.warning(f"BotArena Bot [{speaker.name}] sendMessage HTTP {res.status_code} in [{chat_id}]: {res.text[:120]}")
                return None
        except Exception as exc:
            logger.warning(f"BotArena Bot [{speaker.name}] sendMessage exception in [{chat_id}]: {exc}")
            return None

    async def _run_arena_loop(self, session: BotArenaSession) -> None:
        """
        Task 4.2 (2): Autonomous Multi-Bot Turn-Taking Loop (asyncio.Task per active group).
        - Rotates naturally among present bots so the same bot doesn't talk twice in a row.
        - Simulates realistic sendChatAction(typing) for 4–7 seconds.
        - Sends message as a reply_to_message_id to the previous bot's or owner's message.
        - Waits a natural 5–9 seconds reading pause before the next bot takes its turn
          (waking immediately if ECENN interjects or stops the chat).
        """
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

        is_mock = getattr(mtproto_manager, "_mock_mode", False)
        try:
            while session.is_active and session.current_round < session.max_rounds:
                if not session.participants:
                    logger.warning(f"BotArena [{session.chat_id}]: No active participants remaining. Ending session.")
                    break

                speaker = self._pick_next_arena_speaker(session)
                if not speaker:
                    break

                # 1. Start typing indicator & generate response while simulating 4–7s human typing
                typing_target = random.uniform(0.15, 0.30) if is_mock else random.uniform(4.0, 7.0)
                t_start = time.time()
                await self._send_arena_typing_pulse(speaker, session.chat_id)

                reply_text = await self._generate_arena_bot_response(session, speaker)
                if not session.is_active:
                    break

                # Wait remaining typing time (up to 4–7s total) while refreshing typing pulse if needed
                pulsed_second = False
                while session.is_active:
                    elapsed = time.time() - t_start
                    if elapsed >= typing_target:
                        break
                    if not is_mock and elapsed >= 3.5 and not pulsed_second:
                        await self._send_arena_typing_pulse(speaker, session.chat_id)
                        pulsed_second = True
                    await asyncio.sleep(min(0.4, typing_target - elapsed))

                if not session.is_active:
                    break

                # 2. Send the message as a Telegram reply_to_message_id to the previous message
                sent_msg_id = await self._send_arena_bot_message(
                    speaker=speaker,
                    chat_id=session.chat_id,
                    text=reply_text,
                    reply_to_msg_id=session.last_message_id,
                )

                if sent_msg_id is None and not is_mock:
                    # This bot couldn't send to chat_id (e.g. not in group); remove from session participants
                    logger.info(f"BotArena: Removing [{speaker.name}] from session [{session.chat_id}] (unable to send).")
                    session.participants = [p for p in session.participants if getattr(p, "bot_id", "") != getattr(speaker, "bot_id", "")]
                    continue

                # 3. Record turn in session transcript & shared group ledger
                effective_msg_id = sent_msg_id or (int(time.time() * 1000) % 100000000)
                session.last_message_id = effective_msg_id
                session.last_speaker_bot_id = speaker.bot_id
                session.last_speaker_name = speaker.name
                session.current_round += 1

                turn_record = {
                    "speaker_name": speaker.name,
                    "speaker_id": getattr(speaker, "numeric_id", 0) or 0,
                    "bot_id": speaker.bot_id,
                    "is_bot": True,
                    "is_owner": False,
                    "text": reply_text,
                    "message_id": effective_msg_id,
                    "timestamp": time.time(),
                    "round": session.current_round,
                }
                session.transcript.append(turn_record)
                if len(session.transcript) > 30:
                    session.transcript = session.transcript[-30:]

                try:
                    self.record_group_message(
                        message_id=effective_msg_id,
                        chat_id=session.chat_id,
                        chat_title=session.chat_title,
                        sender_user_id=getattr(speaker, "numeric_id", 0) or 0,
                        sender_name=speaker.name,
                        message_text=reply_text,
                        target_bot_id=speaker.bot_id,
                        target_bot_name=speaker.name,
                    )
                except Exception:
                    pass

                logger.info(
                    f"🗣️ [BotArena Turn {session.current_round}/"
                    f"{'∞' if session.max_rounds >= 999999 else session.max_rounds}] "
                    f"[{speaker.name}] in [{session.chat_title}]: '{reply_text[:70]}'"
                )

                if session.current_round >= session.max_rounds or not session.is_active:
                    break

                # 4. Natural 5–9 seconds reading pause before the next bot takes its turn
                # Wakes early if ECENN interjects or stops the arena!
                pause_sec = random.uniform(0.15, 0.30) if is_mock else random.uniform(5.0, 9.0)
                session.wakeup_event.clear()
                try:
                    await asyncio.wait_for(session.wakeup_event.wait(), timeout=pause_sec)
                    if session.is_active and session.pending_owner_interjection and not is_mock:
                        # Brief 1.2s human reading beat after ECENN's live interjection before next bot starts typing
                        await asyncio.sleep(1.2)
                except asyncio.TimeoutError:
                    pass

        except asyncio.CancelledError:
            logger.info(f"BotArena task cancelled cleanly for chat [{session.chat_id}].")
        except Exception as exc:
            logger.error(f"BotArena loop exception in chat [{session.chat_id}]: {exc}", exc_info=True)
        finally:
            session.is_active = False
            logger.info(
                f"🏁 [BotArena Finished] Chat [{session.chat_title} ({session.chat_id})] "
                f"completed {session.current_round} rounds."
            )
'''

if "class BotArenaSession:" not in sbn:
    sbn = sbn.replace("class SiblingBotNetworkService:", arena_engine_code + "\n\nclass SiblingBotNetworkService:", 1)
    print("✅ sibling_bot_network: added BotArenaSession class")

if "def start_bot_arena(" not in sbn:
    sbn = sbn.replace("# Global Sibling Network Singleton", arena_methods_code + "\n\n# Global Sibling Network Singleton", 1)
    print("✅ sibling_bot_network: added Bot Arena Engine methods to SiblingBotNetworkService")

write("bot_factory/sibling_bot_network.py", sbn)


# ============================================================================
# 2. aether_human_core/cognitive_engine/orchestrator.py — Arena Turn Handling
# ============================================================================
orch = read("aether_human_core/cognitive_engine/orchestrator.py")

old_orch_king = """        # 2.3 Check Sovereign King Intent & Claim Override
        if is_admin_or_king or sender_id in settings.super_admin_ids_list:"""

new_orch_king = """        is_arena_turn = "[ساحة الحوار الحي في الجروب (Bot Arena)" in message_text

        # 2.3 Check Sovereign King Intent & Claim Override
        if not is_arena_turn and (is_admin_or_king or sender_id in settings.super_admin_ids_list):"""

if "is_arena_turn =" not in orch:
    assert old_orch_king in orch, "orchestrator king intent anchor not found"
    orch = orch.replace(old_orch_king, new_orch_king, 1)
    orch = orch.replace(
        "        # 3.5 Check for Persona Shift Commands (King Sovereignty / Admin / User Command)\n        shift_res = persona_shifter.evaluate_natural_language_shift(",
        "        # 3.5 Check for Persona Shift Commands (King Sovereignty / Admin / User Command)\n        shift_res = None if is_arena_turn else persona_shifter.evaluate_natural_language_shift(",
        1,
    )
    orch = orch.replace(
        '        is_multimodal_msg = (media_type in ("sticker", "photo", "document", "gif")) or ("<ATTACHED_FILE" in message_text)',
        '        is_multimodal_msg = (media_type in ("sticker", "photo", "document", "gif")) or ("<ATTACHED_FILE" in message_text) or is_arena_turn',
        1,
    )
    write("aether_human_core/cognitive_engine/orchestrator.py", orch)
    print("✅ orchestrator: added is_arena_turn guard for Bot Arena turns")


# ============================================================================
# 3. aether_human_core/telegram_client/telegram_menu.py — Interactive Bot Arena Panel
# ============================================================================
tmenu = read("aether_human_core/telegram_client/telegram_menu.py")

old_menu_factory_row = """        if is_owner or role in ("SUPER_ADMIN", "ADMIN"):
            buttons.append([
                {"text": "🏭 مصنع البوتات واليوزربوت 🤖", "callback_data": "menu:bot_factory", "style": "success"},
                {"text": "👑 إدارة الأدمنز والرتب 🛡️", "callback_data": "menu:admins", "style": "primary"},
            ])"""

new_menu_factory_row = """        if is_owner or role in ("SUPER_ADMIN", "ADMIN"):
            buttons.append([
                {"text": "🔥 حوار البوتات الحي (Bot Arena) 🗣️", "callback_data": "menu:bot_arena", "style": "success"},
            ])
            buttons.append([
                {"text": "🏭 مصنع البوتات واليوزربوت 🤖", "callback_data": "menu:bot_factory", "style": "success"},
                {"text": "👑 إدارة الأدمنز والرتب 🛡️", "callback_data": "menu:admins", "style": "primary"},
            ])"""

if '"callback_data": "menu:bot_arena"' not in tmenu:
    assert old_menu_factory_row in tmenu, "telegram_menu factory row anchor not found"
    tmenu = tmenu.replace(old_menu_factory_row, new_menu_factory_row, 1)
    print("✅ telegram_menu: added Bot Arena button to main dashboard")

arena_panel_methods = '''
    @classmethod
    async def render_bot_arena_panel(
        cls,
        user_id: int,
        chat_id: Optional[int] = None,
        status_banner: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Task 4.1: Renders the Interactive Group Control Panel for Bot-to-Bot Group Conversations (Bot Arena).
        Includes the exact mandatory callback buttons:
        - 🔥 تشغيل حوار البوتات (مفتوح حتى الإيقاف) (bot_arena:start:infinite:{chat_id})
        - 🎯 حوار 5 جولات (bot_arena:start:5:{chat_id})
        - 🎯 حوار 10 جولات (bot_arena:start:10:{chat_id})
        - 🎲 اختيار موضوع نقاش عشوائي (bot_arena:topic:{chat_id})
        - 🛑 إيقاف حوار البوتات فوراً (bot_arena:stop:{chat_id})
        """
        from core_config.sovereignty_rules import sovereignty_guard
        is_owner = sovereignty_guard.is_the_king(user_id) or (user_id in settings.super_admin_ids_list)
        if not is_owner:
            return (
                "🚫 <b>ساحة حوار البوتات الحي (Bot Arena) مخصصة لمالك النظام (ECENN) فقط 👑</b>",
                {"inline_keyboard": [[{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}]]},
            )

        known_groups = await sibling_network.get_known_groups_async()
        target_chat_id = chat_id if (chat_id is not None and chat_id < 0) else None
        if target_chat_id is None:
            # Pick currently active arena group, or most recent known group, or fallback
            for g in known_groups:
                if g.get("is_active"):
                    target_chat_id = int(g["chat_id"])
                    break
            if target_chat_id is None and known_groups:
                target_chat_id = int(known_groups[0]["chat_id"])
            if target_chat_id is None:
                target_chat_id = int(chat_id or user_id)

        present_bots = await sibling_network.discover_present_bots(target_chat_id)
        sess = sibling_network.get_arena_session(target_chat_id)
        is_running = bool(sess and sess.is_active)
        topic = sibling_network.get_arena_topic(target_chat_id)
        chat_title = (
            sess.chat_title
            if sess
            else sibling_network._known_group_titles.get(target_chat_id, f"الجروب ({target_chat_id})")
        )

        bot_badges = []
        for b in present_bots:
            g_icon = "👧" if getattr(b, "gender", "male") == "female" else "👦"
            ub_tag = " (Userbot)" if getattr(b, "is_userbot", False) else ""
            bot_badges.append(f"<b>{html.escape(getattr(b, 'name', 'بوت'))}</b> {g_icon}{ub_tag}")
        bots_display = " ، ".join(bot_badges) if bot_badges else "<i>جاري اكتشاف البوتات...</i>"

        if is_running and sess:
            max_r_txt = "مفتوح حتى الإيقاف ♾️" if sess.max_rounds >= 999999 else f"{sess.max_rounds} جولات"
            state_line = f"🟢 <b>نشط الآن (الجولة {sess.current_round} من {max_r_txt})</b>"
            last_sp = sess.last_speaker_name or "يستعد للبدء..."
        else:
            state_line = "⚪ <b>متوقف حالياً (جاهز للانطلاق)</b>"
            last_sp = "—"

        banner_block = f"<blockquote>{status_banner}</blockquote>\n" if status_banner else ""

        text = (
            f"🔥 <b>لوحة تحكم حوار البوتات الحي في الجروبات (Bot Arena)</b> 🗣️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{banner_block}"
            f"👥 <b>الجروب المستهدف:</b> <b>{html.escape(str(chat_title))}</b> (<code>{target_chat_id}</code>)\n"
            f"📡 <b>حالة الحوار:</b> {state_line}\n"
            f"🤖 <b>البوتات المتواجدة في الجروب ({len(present_bots)}):</b>\n"
            f"   └ {bots_display}\n"
            f"🎲 <b>موضوع النقاش المختار:</b>\n"
            f"   └ <i>«{html.escape(topic)}»</i>\n"
            f"🗣️ <b>آخر متحدث:</b> <code>{html.escape(str(last_sp))}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>أثناء الحوار يمكنك التدخل والكتابة في الجروب في أي لحظة، وسيرد عليك البوت التالي فوراً ويدمج كلامك في نقاشهم!</i>"
        )

        buttons: List[List[Dict[str, Any]]] = [
            [
                {
                    "text": "🔥 تشغيل حوار البوتات (مفتوح حتى الإيقاف)",
                    "callback_data": f"bot_arena:start:infinite:{target_chat_id}",
                    "style": "success",
                }
            ],
            [
                {
                    "text": "🎯 حوار 5 جولات",
                    "callback_data": f"bot_arena:start:5:{target_chat_id}",
                    "style": "primary",
                },
                {
                    "text": "🎯 حوار 10 جولات",
                    "callback_data": f"bot_arena:start:10:{target_chat_id}",
                    "style": "primary",
                },
            ],
            [
                {
                    "text": "🎲 اختيار موضوع نقاش عشوائي",
                    "callback_data": f"bot_arena:topic:{target_chat_id}",
                    "style": "primary",
                }
            ],
            [
                {
                    "text": "🛑 إيقاف حوار البوتات فوراً",
                    "callback_data": f"bot_arena:stop:{target_chat_id}",
                    "style": "danger",
                }
            ],
        ]

        # If opened in private DM and multiple groups exist, display group switcher pills
        if (chat_id is None or chat_id > 0) and len(known_groups) > 1:
            group_row: List[Dict[str, Any]] = []
            for g in known_groups[:4]:
                gid = int(g["chat_id"])
                gtitle = str(g["title"])[:16]
                prefix = "✅ " if gid == target_chat_id else "👥 "
                group_row.append(
                    {
                        "text": f"{prefix}{gtitle}",
                        "callback_data": f"bot_arena:select_group:{gid}",
                        "style": "success" if gid == target_chat_id else "primary",
                    }
                )
                if len(group_row) == 2:
                    buttons.append(group_row)
                    group_row = []
            if group_row:
                buttons.append(group_row)

        buttons.append(
            [
                {"text": "🔄 تحديث الحالة ⚡", "callback_data": f"bot_arena:refresh:{target_chat_id}", "style": "primary"},
                {"text": "🔙 الرئيسية 🏠", "callback_data": "menu:main", "style": "danger"},
            ]
        )
        return text, {"inline_keyboard": buttons}
'''

if "def render_bot_arena_panel(" not in tmenu:
    tmenu = tmenu.replace("    @classmethod\n    async def handle_callback(", arena_panel_methods + "\n    @classmethod\n    async def handle_callback(", 1)
    print("✅ telegram_menu: added render_bot_arena_panel method")

old_handle_cb_sig = """    @classmethod
    async def handle_callback(
        cls, callback_data: str, user_id: int, user_name: str = "مستخدم", bot_instance: Optional[Any] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str], Optional[str]]:"""

new_handle_cb_sig = """    @classmethod
    async def handle_callback(
        cls,
        callback_data: str,
        user_id: int,
        user_name: str = "مستخدم",
        bot_instance: Optional[Any] = None,
        chat_id: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str], Optional[str]]:"""

if "chat_id: Optional[int] = None," not in tmenu:
    assert old_handle_cb_sig in tmenu, "telegram_menu handle_callback signature anchor not found"
    tmenu = tmenu.replace(old_handle_cb_sig, new_handle_cb_sig, 1)

arena_cb_branch = '''
        elif callback_data == "menu:bot_arena" or callback_data.startswith("bot_arena:"):
            from core_config.sovereignty_rules import sovereignty_guard
            is_owner = sovereignty_guard.is_the_king(user_id) or (user_id in settings.super_admin_ids_list)
            if not is_owner:
                return None, None, "🚫 هذا التحكم مخصص لمالك النظام (ECENN) فقط 👑", None

            if callback_data == "menu:bot_arena":
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=chat_id)
                return text, markup, None, None

            parts = callback_data.split(":")
            action = parts[1] if len(parts) > 1 else ""

            if action == "select_group" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=target_cid)
                return text, markup, "✅ تم تحديد الجروب المستهدف!", None

            if action == "refresh" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=target_cid)
                return text, markup, "🔄 تم تحديث حالة ساحة الحوار!", None

            if action == "topic" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id or user_id
                new_topic = sibling_network.pick_random_arena_topic(target_cid)
                banner = f"🎲 <b>تم اختيار موضوع نقاش عشوائي جديد:</b>\n«{html.escape(new_topic)}»"
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                return text, markup, f"🎲 الموضوع: {new_topic[:45]}...", None

            if action == "start" and len(parts) >= 4:
                rounds_str = parts[2].lower()
                try:
                    target_cid = int(parts[3])
                except ValueError:
                    target_cid = chat_id or user_id
                max_rounds = 999999 if rounds_str == "infinite" else max(1, int(rounds_str))
                sess = await sibling_network.start_bot_arena(
                    chat_id=target_cid,
                    max_rounds=max_rounds,
                    started_by=user_id,
                )
                rounds_ar = "مفتوح حتى الإيقاف ♾️" if max_rounds >= 999999 else f"{max_rounds} جولات"
                banner = (
                    f"🔥 <b>انطلق حوار البوتات الحي الآن ({rounds_ar})!</b>\n"
                    f"الموضوع: «{html.escape(sess.topic)}»"
                )
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                return text, markup, f"🔥 بدأ حوار البوتات ({rounds_ar})!", None

            if action == "stop" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id or user_id
                was_stopped = await sibling_network.stop_bot_arena(
                    chat_id=target_cid, reason="إيقاف فوري من زر لوحة التحكم"
                )
                banner = (
                    "🛑 <b>تم إيقاف حوار البوتات في الجروب فوراً!</b>"
                    if was_stopped
                    else "ℹ️ <b>حوار البوتات متوقف بالفعل في هذا الجروب.</b>"
                )
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                toast = "🛑 تم إيقاف حوار البوتات فوراً!" if was_stopped else "ℹ️ الحوار متوقف بالفعل."
                return text, markup, toast, None
'''

if 'callback_data.startswith("bot_arena:")' not in tmenu:
    target_anchor = '        elif callback_data == "menu:bot_factory":'
    assert target_anchor in tmenu, "telegram_menu bot_factory callback anchor not found"
    tmenu = tmenu.replace(target_anchor, arena_cb_branch + "\n" + target_anchor, 1)
    print("✅ telegram_menu: added bot_arena callback handling")

write("aether_human_core/telegram_client/telegram_menu.py", tmenu)


# ============================================================================
# 4. aether_human_core/telegram_client/mtproto_manager.py — Commands & Callbacks
# ============================================================================
mtp = read("aether_human_core/telegram_client/mtproto_manager.py")

# Pass chat_id to telegram_menu.handle_callback in _process_callback_query
old_mtp_cb = "text, markup, alert, trigger = await telegram_menu.handle_callback(data, user_id, user_name)"
new_mtp_cb = "text, markup, alert, trigger = await telegram_menu.handle_callback(data, user_id, user_name, chat_id=chat_id)"
if old_mtp_cb in mtp:
    mtp = mtp.replace(old_mtp_cb, new_mtp_cb, 1)
    print("✅ mtproto_manager: passed chat_id to telegram_menu.handle_callback")

# Add /bots_chat, /حوار, /stop_chat, /ايقاف_الحوار in _handle_command
arena_cmds_mtp = '''
        elif cmd in ("/bots_chat", "/حوار", "/bot_arena", "/ساحة_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام (ECENN) فقط 👑", {}, reply_to_msg_id)
                return True
            if not sibling_network.try_claim_arena_command(chat_id, reply_to_msg_id):
                return True
            custom_topic = message_text[len(parts[0]):].strip()
            if custom_topic:
                sibling_network.set_arena_topic(chat_id, custom_topic)
            text, markup = await telegram_menu.render_bot_arena_panel(user_id=sender_id, chat_id=chat_id)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/stop_chat", "/ايقاف_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                return True
            if not sibling_network.try_claim_arena_command(chat_id, reply_to_msg_id):
                return True
            stopped = await sibling_network.stop_bot_arena(chat_id, reason="أمر /stop_chat من المطور")
            if not stopped and chat_id > 0:
                # If sent in DM, stop all active arena sessions across groups
                for active_cid in list(sibling_network._arena_sessions.keys()):
                    if await sibling_network.stop_bot_arena(active_cid, reason="أمر /stop_chat من الخاص"):
                        stopped = True
            msg_txt = (
                "🛑 <b>تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑</b>"
                if stopped
                else "ℹ️ <b>لا يوجد حوار بوتات نشط حالياً لإيقافه.</b>"
            )
            await self.send_message_with_keyboard(chat_id, msg_txt, {}, reply_to_msg_id)
            return True
'''

if '"/bots_chat"' not in mtp:
    cmd_anchor = '        # Multi-Persona Debate Engine (/debate)'
    assert cmd_anchor in mtp, "mtproto_manager /debate anchor not found"
    mtp = mtp.replace(cmd_anchor, arena_cmds_mtp + "\n" + cmd_anchor, 1)
    print("✅ mtproto_manager: added /bots_chat, /حوار, /stop_chat command handlers")

# In Telethon Userbot on_new_message: handle active BotArenaSession in groups immediately before long unseen_delay
old_ub_group_delay = """            # 1. Task 2.1 Phase 1 — Variable Unseen Delay before marking ✓✓ Seen
            if event.is_private:"""

new_ub_group_delay = """            # 0.9 Task 4.2: If Bot Arena is active in this group, handle sibling/owner messages immediately
            if event.is_group:
                from bot_factory.sibling_bot_network import sibling_network as _ub_sbn
                from bot_factory.group_arbiter import group_arbiter as _ub_ga
                _ub_ga.record_presence(event.chat_id, f"userbot_{userbot_id or 8656468004}")
                if _ub_sbn.is_arena_active(event.chat_id):
                    if _ub_sbn.is_server_sibling(sender_id):
                        # Another sibling bot spoke in the Arena; mark seen briefly and don't trigger normal handler
                        return
                    is_king_ub = (sender_id == settings.the_king_user_id) or (sender_id in settings.super_admin_ids_list)
                    if is_king_ub and _ub_sbn.is_arena_stop_phrase(msg_text):
                        if _ub_sbn.try_claim_arena_command(event.chat_id, event.id):
                            await _ub_sbn.stop_bot_arena(event.chat_id, reason="أمر إيقاف نصي من المطور")
                            await self.send_message(event.chat_id, "🛑 تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑", reply_to_msg_id=event.id)
                        return
                    _ub_sbn.record_arena_human_interjection(
                        chat_id=event.chat_id,
                        message_id=event.id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        message_text=msg_text,
                        is_owner=is_king_ub,
                    )
                    return

            # 1. Task 2.1 Phase 1 — Variable Unseen Delay before marking ✓✓ Seen
            if event.is_private:"""

if "_ub_sbn.is_arena_active(event.chat_id)" not in mtp:
    assert old_ub_group_delay in mtp, "mtproto_manager userbot unseen delay anchor not found"
    mtp = mtp.replace(old_ub_group_delay, new_ub_group_delay, 1)
    print("✅ mtproto_manager: added fast BotArena interjection capture in Userbot on_new_message")

write("aether_human_core/telegram_client/mtproto_manager.py", mtp)


# ============================================================================
# 5. aether_human_core/telegram_client/handlers/group_handler.py
# ============================================================================
gh = read("aether_human_core/telegram_client/handlers/group_handler.py")

old_gh_arbiter = """        # 1.5 The King / Creator sovereignty check
        is_the_king_user = sovereignty_guard.is_the_king(sender_id) or sender_id in settings.super_admin_ids_list

        # 2. Central Multi-Bot Group Arbiter (Collision-Free Turn Election)"""

new_gh_arbiter = """        # 1.5 The King / Creator sovereignty check
        is_the_king_user = sovereignty_guard.is_the_king(sender_id) or sender_id in settings.super_admin_ids_list

        # 1.8 Task 4.2: Bot Arena Live Interjection & Stop Trigger Handling
        if is_the_king_user and sibling_network.is_arena_stop_phrase(message_text):
            if sibling_network.is_arena_active(chat_id):
                if sibling_network.try_claim_arena_command(chat_id, message_id):
                    await sibling_network.stop_bot_arena(chat_id, reason="أمر إيقاف مباشر من المطور في الجروب")
                    await mtproto_manager.send_message(
                        chat_id=chat_id,
                        text="🛑 تم إيقاف حوار البوتات في الجروب فوراً بأمرك يا كبير! 👑",
                        reply_to_msg_id=message_id,
                    )
                return

        if sibling_network.is_arena_active(chat_id):
            if not sibling_network.is_server_sibling(sender_id):
                sibling_network.record_arena_human_interjection(
                    chat_id=chat_id,
                    message_id=message_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text,
                    is_owner=is_the_king_user,
                )
            return

        # 2. Central Multi-Bot Group Arbiter (Collision-Free Turn Election)"""

if "1.8 Task 4.2: Bot Arena Live Interjection" not in gh:
    assert old_gh_arbiter in gh, "group_handler arbiter anchor not found"
    gh = gh.replace(old_gh_arbiter, new_gh_arbiter, 1)
    write("aether_human_core/telegram_client/handlers/group_handler.py", gh)
    print("✅ group_handler: added Bot Arena stop phrase & live interjection handling")


# ============================================================================
# 6. bot_factory/multi_bot_dispatcher.py — Sub-Bots Arena Support
# ============================================================================
mbd = read("bot_factory/multi_bot_dispatcher.py")

old_mbd_cb = """            text, markup, alert, action = await telegram_menu.handle_callback(
                data, cb_user_id, cb_user_name, bot_instance=bot
            )"""

new_mbd_cb = """            text, markup, alert, action = await telegram_menu.handle_callback(
                data, cb_user_id, cb_user_name, bot_instance=bot, chat_id=cb_chat_id
            )"""

if old_mbd_cb in mbd:
    mbd = mbd.replace(old_mbd_cb, new_mbd_cb, 1)
    print("✅ multi_bot_dispatcher: passed chat_id to telegram_menu.handle_callback")

old_mbd_group = """        # In groups/supergroups: Coordinate turn election via Central Multi-Bot Group Arbiter
        if is_group:
            from bot_factory.group_arbiter import group_arbiter
            group_arbiter.record_presence(chat_id, bot.instance_id)"""

new_mbd_group = """        # Task 4.1 & 4.2: Handle /bots_chat, /حوار, /stop_chat on sub-bots (deduplicated across group bots)
        cmd_token = text.strip().split()[0].lower().split("@")[0] if text.strip() else ""
        if cmd_token in ("/bots_chat", "/حوار", "/bot_arena", "/ساحة_الحوار", "/stop_chat", "/ايقاف_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network as _mb_sbn
            from aether_human_core.config.settings import settings as _mb_settings
            is_king_mb = (sender_id == _mb_settings.the_king_user_id) or (sender_id in _mb_settings.super_admin_ids_list)
            if is_king_mb and _mb_sbn.try_claim_arena_command(chat_id, message_id):
                if cmd_token in ("/stop_chat", "/ايقاف_الحوار"):
                    stopped = await _mb_sbn.stop_bot_arena(chat_id, reason=f"أمر {cmd_token} عبر {bot.name}")
                    stop_txt = "🛑 <b>تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑</b>" if stopped else "ℹ️ <b>حوار البوتات متوقف بالفعل.</b>"
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": stop_txt, "parse_mode": "HTML", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
                else:
                    from aether_human_core.telegram_client.telegram_menu import telegram_menu
                    parts_cmd = text.strip().split()
                    custom_t = text.strip()[len(parts_cmd[0]):].strip() if parts_cmd else ""
                    if custom_t:
                        _mb_sbn.set_arena_topic(chat_id, custom_t)
                    panel_txt, panel_mk = await telegram_menu.render_bot_arena_panel(user_id=sender_id, chat_id=chat_id)
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": panel_txt, "reply_markup": panel_mk, "parse_mode": "HTML", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
            return

        # In groups/supergroups: Coordinate turn election via Central Multi-Bot Group Arbiter
        if is_group:
            from bot_factory.group_arbiter import group_arbiter
            from bot_factory.sibling_bot_network import sibling_network as _mb_sbn
            from aether_human_core.config.settings import settings as _mb_settings
            group_arbiter.record_presence(chat_id, bot.instance_id)
            if chat.get("title"):
                _mb_sbn._known_group_titles[chat_id] = chat.get("title")

            is_king_mb = (sender_id == _mb_settings.the_king_user_id) or (sender_id in _mb_settings.super_admin_ids_list)
            if is_king_mb and _mb_sbn.is_arena_stop_phrase(text) and _mb_sbn.is_arena_active(chat_id):
                if _mb_sbn.try_claim_arena_command(chat_id, message_id):
                    await _mb_sbn.stop_bot_arena(chat_id, reason="أمر إيقاف نصي من المطور")
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": "🛑 تم إيقاف حوار البوتات في الجروب فوراً بأمرك يا كبير! 👑", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
                return

            if _mb_sbn.is_arena_active(chat_id):
                if not _mb_sbn.is_server_sibling(sender_id):
                    _mb_sbn.record_arena_human_interjection(
                        chat_id=chat_id,
                        message_id=message_id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        message_text=text,
                        is_owner=is_king_mb,
                    )
                return"""

if "_mb_sbn.is_arena_active(chat_id)" not in mbd:
    assert old_mbd_group in mbd, "multi_bot_dispatcher group anchor not found"
    mbd = mbd.replace(old_mbd_group, new_mbd_group, 1)
    write("bot_factory/multi_bot_dispatcher.py", mbd)
    print("✅ multi_bot_dispatcher: added Bot Arena command, stop phrase & live interjection support")


# ============================================================================
# 7. bot_factory/group_arbiter.py — Suppress normal election during BotArena
# ============================================================================
ga = read("bot_factory/group_arbiter.py")

old_ga_elect = """        # In 1-on-1 private DMs, the receiving bot always handles the conversation
        if not is_group:
            return ElectionDecision(should_reply=True, winner_bot_id=requesting_bot_id, stagger_delay_sec=0.0, reason="PRIVATE_DM")"""

new_ga_elect = """        # In 1-on-1 private DMs, the receiving bot always handles the conversation
        if not is_group:
            return ElectionDecision(should_reply=True, winner_bot_id=requesting_bot_id, stagger_delay_sec=0.0, reason="PRIVATE_DM")

        # Task 4.2: While BotArenaSession is actively driving turn-taking in chat_id, suppress normal turn election
        from bot_factory.sibling_bot_network import sibling_network
        if sibling_network.is_arena_active(chat_id):
            return ElectionDecision(should_reply=False, winner_bot_id=None, stagger_delay_sec=0.0, reason="BOT_ARENA_ACTIVE")"""

if 'reason="BOT_ARENA_ACTIVE"' not in ga:
    assert old_ga_elect in ga, "group_arbiter elect_reply_turn anchor not found"
    ga = ga.replace(old_ga_elect, new_ga_elect, 1)
    write("bot_factory/group_arbiter.py", ga)
    print("✅ group_arbiter: added BOT_ARENA_ACTIVE guard in elect_reply_turn")


# ============================================================================
# 8. mini_app_webapp/webapp_server.py — Bot Arena Mini-App REST API Endpoints
# ============================================================================
wsrv = read("mini_app_webapp/webapp_server.py")

arena_api_code = '''

# ==============================================================================
# Task 4.1 & 4.2: Bot Arena (حوار البوتات الحي في الجروبات) Mini-App API
# ==============================================================================

class BotArenaStartRequest(BaseModel):
    user_id: int = 8287744705
    chat_id: int
    rounds: str = "infinite"  # "5", "10", "20", or "infinite"
    topic: Optional[str] = ""


class BotArenaStopRequest(BaseModel):
    user_id: int = 8287744705
    chat_id: int


class BotArenaTopicRequest(BaseModel):
    user_id: int = 8287744705
    chat_id: Optional[int] = None


@webapp_router.get("/api/webapp/arena/status")
async def get_bot_arena_status(user_id: int = 8287744705) -> Dict[str, Any]:
    rbac_guard.verify_king_access(user_id)
    from bot_factory.sibling_bot_network import sibling_network
    groups = await sibling_network.get_known_groups_async()
    sessions = sibling_network.get_all_arena_sessions()
    return {
        "success": True,
        "groups": groups,
        "sessions": sessions,
        "topics": sibling_network.ARENA_RANDOM_TOPICS,
    }


@webapp_router.post("/api/webapp/arena/start")
async def start_bot_arena_api(req: BotArenaStartRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    rounds_str = str(req.rounds or "infinite").strip().lower()
    if rounds_str in ("infinite", "open", "0", "∞"):
        max_rounds = 999999
    else:
        try:
            max_rounds = max(1, int(rounds_str))
        except ValueError:
            max_rounds = 999999

    session = await sibling_network.start_bot_arena(
        chat_id=req.chat_id,
        max_rounds=max_rounds,
        topic=(req.topic or "").strip() or None,
        started_by=req.user_id,
    )
    rounds_ar = "مفتوح حتى الإيقاف" if max_rounds >= 999999 else f"{max_rounds} جولات"
    return {
        "success": True,
        "message": f"🔥 تم تشغيل حوار البوتات الحي في {session.chat_title} ({rounds_ar})!",
        "session": session.to_dict(),
    }


@webapp_router.post("/api/webapp/arena/stop")
async def stop_bot_arena_api(req: BotArenaStopRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    stopped = await sibling_network.stop_bot_arena(
        chat_id=req.chat_id,
        reason="إيقاف مباشر من لوحة التطبيق المصغر (Mini-App)",
    )
    sess = sibling_network.get_arena_session(req.chat_id)
    return {
        "success": True,
        "stopped": stopped,
        "message": "🛑 تم إيقاف حوار البوتات فوراً!" if stopped else "ℹ️ الحوار متوقف بالفعل في هذا الجروب.",
        "session": sess.to_dict() if sess else None,
    }


@webapp_router.post("/api/webapp/arena/topic")
async def pick_bot_arena_random_topic_api(req: BotArenaTopicRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    new_topic = sibling_network.pick_random_arena_topic(req.chat_id)
    return {
        "success": True,
        "topic": new_topic,
        "message": f"🎲 تم اختيار موضوع جديد: {new_topic}",
    }
'''

if "/api/webapp/arena/status" not in wsrv:
    anchor_ws = "# ==============================================================================\n# HTML Mini App Single-Page Application"
    assert anchor_ws in wsrv, "webapp_server HTML section anchor not found"
    wsrv = wsrv.replace(anchor_ws, arena_api_code + "\n\n" + anchor_ws, 1)
    write("mini_app_webapp/webapp_server.py", wsrv)
    print("✅ webapp_server: added /api/webapp/arena/* endpoints")


# ============================================================================
# 9. mini_app_webapp/template.html — "حوار البوتات الحي في الجروبات (Bot Arena)" Card
# ============================================================================
tmpl = read("mini_app_webapp/template.html")

arena_card_html = '''
            <!-- Task 4.1: حوار البوتات الحي في الجروبات (Bot Arena) Control Card -->
            <div class="card glass" id="bot-arena-control-card" style="border: 1.5px solid rgba(0, 245, 155, 0.35); box-shadow: 0 0 24px rgba(0, 245, 155, 0.12);">
                <div class="card-title">
                    <span>🔥 حوار البوتات الحي في الجروبات (Bot Arena)</span>
                    <span id="arena-live-badge" style="font-size: 11px; padding: 3px 9px; border-radius: 12px; background: rgba(255,255,255,0.08); color: var(--text-muted);">⚪ متوقف</span>
                </div>
                <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
                    اجعل البوتات المتواجدة في الجروب يتحاورون ويتناقشون ويهزرون مع بعضهم تلقائياً، مع إمكانية تدخلك الحي معهم في أي لحظة!
                </p>

                <label style="font-size: 11px; color: var(--neon-blue);">👥 اختر الجروب النشط (أو اكتب Chat ID الجروب):</label>
                <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                    <select id="arena-group-select" class="input-glass" style="flex: 2; margin-bottom: 0;" onchange="onArenaGroupChange()">
                        <option value="">-- اختر الجروب --</option>
                    </select>
                    <input type="text" id="arena-custom-chat-id" class="input-glass" style="flex: 1; margin-bottom: 0;" placeholder="-100123456789">
                    <button class="pill-btn" style="padding: 6px 10px;" onclick="loadBotArenaStatus()" title="تحديث الجروبات">🔄</button>
                </div>

                <div id="arena-present-bots-box" style="font-size: 11.5px; color: var(--text-main); background: rgba(255,255,255,0.03); border: 1px solid var(--border-card); border-radius: 10px; padding: 8px 10px; margin-bottom: 10px;">
                    🤖 <b>البوتات المتواجدة:</b> <span id="arena-present-bots-list" style="color: var(--neon-green);">اختر جروباً لعرض البوتات...</span>
                </div>

                <label style="font-size: 11px; color: var(--neon-yellow);">🎲 موضوع النقاش (اختياري — اتركه فارغاً لحوار عفوي أو اختر عشوائياً):</label>
                <div style="display: flex; gap: 8px; margin-bottom: 10px;">
                    <input type="text" id="arena-topic-input" class="input-glass" style="margin-bottom: 0; flex: 1;" placeholder="اكتب موضوعاً للنقاش أو اضغط 🎲 عشوائي...">
                    <button class="btn-action" style="padding: 8px 12px; white-space: nowrap; background: linear-gradient(135deg, #9d4edd, #ff2a85);" onclick="pickRandomArenaTopic()">🎲 عشوائي</button>
                </div>

                <label style="font-size: 11px; color: var(--text-muted);">🎯 عدد جولات الحوار:</label>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 12px;">
                    <button type="button" class="pill-btn arena-round-btn" data-rounds="5" onclick="selectArenaRounds('5', this)">5 جولات</button>
                    <button type="button" class="pill-btn arena-round-btn" data-rounds="10" onclick="selectArenaRounds('10', this)">10 جولات</button>
                    <button type="button" class="pill-btn arena-round-btn" data-rounds="20" onclick="selectArenaRounds('20', this)">20 جولة</button>
                    <button type="button" class="pill-btn arena-round-btn active" data-rounds="infinite" onclick="selectArenaRounds('infinite', this)">♾️ مفتوح</button>
                </div>

                <div style="display: flex; gap: 8px;">
                    <button class="btn-action btn-success" style="flex: 1.4; font-size: 13.5px; font-weight: 800;" onclick="startBotArenaFromWebApp()">🔥 تشغيل حوار البوتات</button>
                    <button class="btn-action btn-danger" style="flex: 1; font-size: 13px; font-weight: 800;" onclick="stopBotArenaFromWebApp()">🛑 إيقاف فوراً</button>
                </div>

                <div id="arena-status-feedback" style="margin-top: 10px; font-size: 12px; line-height: 1.5;"></div>
            </div>
'''

arena_js_code = '''
        // ==========================================
        // Task 4.1 & 4.2: Bot Arena (حوار البوتات الحي في الجروبات) Mini-App Controller
        // ==========================================
        let _arenaSelectedRounds = "infinite";
        let _arenaGroupsCache = [];

        function selectArenaRounds(roundsVal, btnEl) {
            _arenaSelectedRounds = roundsVal;
            document.querySelectorAll('.arena-round-btn').forEach(b => b.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');
        }

        function getTargetArenaChatId() {
            const manual = (document.getElementById('arena-custom-chat-id')?.value || '').trim();
            if (manual && !isNaN(parseInt(manual))) {
                return parseInt(manual);
            }
            const sel = document.getElementById('arena-group-select')?.value || '';
            if (sel && !isNaN(parseInt(sel))) {
                return parseInt(sel);
            }
            return null;
        }

        function onArenaGroupChange() {
            const selVal = document.getElementById('arena-group-select')?.value || '';
            const customInput = document.getElementById('arena-custom-chat-id');
            if (selVal && customInput) {
                customInput.value = selVal;
            }
            updateArenaGroupDetailsUI();
        }

        function updateArenaGroupDetailsUI() {
            const cid = getTargetArenaChatId();
            const botsListEl = document.getElementById('arena-present-bots-list');
            const badgeEl = document.getElementById('arena-live-badge');
            const feedbackEl = document.getElementById('arena-status-feedback');
            const topicInput = document.getElementById('arena-topic-input');

            if (!cid) {
                if (botsListEl) botsListEl.innerText = 'اختر جروباً أو اكتب Chat ID...';
                return;
            }

            const g = _arenaGroupsCache.find(item => Number(item.chat_id) === Number(cid));
            if (g) {
                const bots = g.present_bots || [];
                if (botsListEl) {
                    botsListEl.innerHTML = bots.length
                        ? bots.map(b => `<span style="display:inline-block; background:rgba(0,210,255,0.12); border:1px solid rgba(0,210,255,0.3); padding:2px 8px; border-radius:10px; margin:2px;">${b.name} ${b.gender === 'female' ? '👧' : '👦'}</span>`).join(' ')
                        : 'كل بوتات الأسطول المتواجدة في الجروب';
                }
                if (topicInput && !topicInput.value && g.topic) {
                    topicInput.value = g.topic;
                }
                if (g.is_active && g.session) {
                    const maxR = g.session.max_rounds === 'infinite' ? '♾️' : g.session.max_rounds;
                    if (badgeEl) {
                        badgeEl.style.background = 'rgba(0, 245, 155, 0.2)';
                        badgeEl.style.color = 'var(--neon-green)';
                        badgeEl.innerText = `🟢 نشط (جولة ${g.session.current_round}/${maxR})`;
                    }
                    if (feedbackEl) {
                        feedbackEl.innerHTML = `<span style="color:var(--neon-green);">🗣️ الحوار شغال الآن في <b>${g.title}</b> | آخر متحدث: <b>${g.session.last_speaker_name || 'يبدأ الآن...'}</b></span>`;
                    }
                } else {
                    if (badgeEl) {
                        badgeEl.style.background = 'rgba(255,255,255,0.08)';
                        badgeEl.style.color = 'var(--text-muted)';
                        badgeEl.innerText = '⚪ متوقف';
                    }
                }
            }
        }

        async function loadBotArenaStatus() {
            if (!isKingUser) return;
            try {
                const res = await fetch(`/api/webapp/arena/status?user_id=${tgUser.id}`);
                const data = await res.json();
                if (!data.success) return;

                _arenaGroupsCache = data.groups || [];
                const sel = document.getElementById('arena-group-select');
                const currentVal = sel ? sel.value : '';
                if (sel) {
                    sel.innerHTML = '<option value="">-- اختر الجروب المستهدف --</option>';
                    _arenaGroupsCache.forEach(g => {
                        const opt = document.createElement('option');
                        opt.value = g.chat_id;
                        const statusIcon = g.is_active ? '🟢 ' : '👥 ';
                        opt.innerText = `${statusIcon}${g.title} (${g.chat_id})`;
                        sel.appendChild(opt);
                    });
                    if (currentVal && _arenaGroupsCache.some(g => String(g.chat_id) === String(currentVal))) {
                        sel.value = currentVal;
                    } else if (_arenaGroupsCache.length > 0) {
                        const activeG = _arenaGroupsCache.find(g => g.is_active) || _arenaGroupsCache[0];
                        sel.value = activeG.chat_id;
                        const customInput = document.getElementById('arena-custom-chat-id');
                        if (customInput && !customInput.value) customInput.value = activeG.chat_id;
                    }
                }
                updateArenaGroupDetailsUI();
            } catch (e) {
                console.error("BotArena status error:", e);
            }
        }

        async function pickRandomArenaTopic() {
            const cid = getTargetArenaChatId();
            const feedbackEl = document.getElementById('arena-status-feedback');
            try {
                const res = await fetch('/api/webapp/arena/topic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: tgUser.id, chat_id: cid })
                });
                const data = await res.json();
                if (data.success && data.topic) {
                    const topicInput = document.getElementById('arena-topic-input');
                    if (topicInput) topicInput.value = data.topic;
                    if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-yellow);">🎲 تم اختيار الموضوع: «${data.topic}»</span>`;
                }
            } catch (e) {
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">تعذر جلب موضوع عشوائي</span>`;
            }
        }

        async function startBotArenaFromWebApp() {
            const cid = getTargetArenaChatId();
            const feedbackEl = document.getElementById('arena-status-feedback');
            if (!cid) {
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">⚠️ يرجى اختيار جروب أو كتابة Chat ID الجروب أولاً (أو أرسل /bots_chat داخل الجروب).</span>`;
                return;
            }
            const topic = (document.getElementById('arena-topic-input')?.value || '').trim();
            if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-blue);">⏳ جاري إطلاق ساحة حوار البوتات الحي في الجروب...</span>`;
            try {
                const res = await fetch('/api/webapp/arena/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: tgUser.id,
                        chat_id: cid,
                        rounds: _arenaSelectedRounds,
                        topic: topic
                    })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-green);">✅ ${data.message}</span>`;
                    await loadBotArenaStatus();
                } else {
                    if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">❌ ${formatError(data)}</span>`;
                }
            } catch (e) {
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">❌ فشل الاتصال بالسيرفر</span>`;
            }
        }

        async function stopBotArenaFromWebApp() {
            const cid = getTargetArenaChatId();
            const feedbackEl = document.getElementById('arena-status-feedback');
            if (!cid) {
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">⚠️ اختر الجروب المراد إيقاف الحوار فيه أولاً.</span>`;
                return;
            }
            try {
                const res = await fetch('/api/webapp/arena/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: tgUser.id, chat_id: cid })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-yellow);">${data.message}</span>`;
                    await loadBotArenaStatus();
                } else {
                    if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">❌ ${formatError(data)}</span>`;
                }
            } catch (e) {
                if (feedbackEl) feedbackEl.innerHTML = `<span style="color:var(--neon-red);">❌ فشل الاتصال بالسيرفر</span>`;
            }
        }
'''

if 'id="bot-arena-control-card"' not in tmpl:
    factory_section_anchor = '        <!-- 7. Bot Factory (King Only) - Dedicated Bot & Userbot Creator -->\n        <section id="view-factory" class="view-section">'
    assert factory_section_anchor in tmpl, "template.html view-factory anchor not found"
    tmpl = tmpl.replace(factory_section_anchor, factory_section_anchor + "\n" + arena_card_html, 1)
    print("✅ template.html: added Bot Arena control card to view-factory")

if "function startBotArenaFromWebApp()" not in tmpl:
    tmpl = tmpl.replace(
        "if (viewId === 'view-factory') loadFactoryBots();",
        "if (viewId === 'view-factory') { loadFactoryBots(); loadBotArenaStatus(); }",
        1,
    )
    js_anchor = "        // ==========================================\n        // Bot Factory (Official Bot vs Userbot)\n        // =========================================="
    assert js_anchor in tmpl, "template.html JS factory anchor not found"
    tmpl = tmpl.replace(js_anchor, arena_js_code + "\n" + js_anchor, 1)
    print("✅ template.html: added Bot Arena JS controller functions")

write("mini_app_webapp/template.html", tmpl)
print("Done PART 4 patches.")

