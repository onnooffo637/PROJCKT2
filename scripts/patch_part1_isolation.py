"""
PART 1 — Strict thread isolation in the message ledger.
- message_repo.get_recent_chat_history gains `thread_scope` filter.
- Adds MessageRepository.build_thread_scope(bot_id, sender_id) -> 26-char tag stored in `sentiment`.
- orchestrator: replaces the invalid `sender_id=` kwarg with thread_scope, tags incoming + outgoing logs.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
REPO = ROOT + r"\aether_human_core\database\postgres\repositories\message_repo.py"
ORCH = ROOT + r"\aether_human_core\cognitive_engine\orchestrator.py"


def rw(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def ww(path, s):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sub(src, old, new, label):
    # Normalise to the file's newline convention
    nl = "\r\n" if "\r\n" in src else "\n"
    old_n = old.replace("\r\n", "\n").replace("\n", nl)
    new_n = new.replace("\r\n", "\n").replace("\n", nl)
    if old_n in src:
        print(f"✅ {label}")
        return src.replace(old_n, new_n, 1)
    print(f"⚠️  {label} — anchor NOT found")
    return src


# ───────────────────────── message_repo.py ─────────────────────────
s = rw(REPO)
s = sub(s,
"""    async def get_recent_chat_history(
        self,
        chat_id: int,
        limit: int = 15,
    ) -> List[Tuple[MessageRecordModel, Optional[str]]]:
        \"\"\"
        Returns recent messages along with sender's actual registered first_name.
        Guarantees zero name confusion or cross-talk between group members.
        \"\"\"
        stmt = (
            select(MessageRecordModel, UserModel.first_name)
            .outerjoin(UserModel, MessageRecordModel.sender_id == UserModel.telegram_id)
            .where(MessageRecordModel.chat_id == chat_id)
            .order_by(desc(MessageRecordModel.created_at))
            .limit(limit)
        )""",
"""    @staticmethod
    def build_thread_scope(bot_id: str, sender_id: int) -> str:
        \"\"\"
        Deterministic 26-char conversation-thread tag for strict
        (bot_id, chat_id, sender_user_id) isolation. Stored in the `sentiment` column.
        In DMs every bot shares chat_id == user_id, so without this tag the history of
        one bot's DM bleeds into another bot's DM with the same user.
        \"\"\"
        import hashlib
        digest = hashlib.md5(f"{bot_id}|{sender_id}".encode("utf-8")).hexdigest()[:24]
        return f"T:{digest}"

    async def get_recent_chat_history(
        self,
        chat_id: int,
        limit: int = 15,
        thread_scope: Optional[str] = None,
    ) -> List[Tuple[MessageRecordModel, Optional[str]]]:
        \"\"\"
        Returns recent messages along with sender's actual registered first_name.
        Guarantees zero name confusion or cross-talk between group members.
        When `thread_scope` is given, ONLY messages of that exact (bot, user) thread are returned.
        \"\"\"
        conditions = [MessageRecordModel.chat_id == chat_id]
        if thread_scope:
            conditions.append(MessageRecordModel.sentiment == thread_scope)
        stmt = (
            select(MessageRecordModel, UserModel.first_name)
            .outerjoin(UserModel, MessageRecordModel.sender_id == UserModel.telegram_id)
            .where(*conditions)
            .order_by(desc(MessageRecordModel.created_at))
            .limit(limit)
        )""",
"message_repo: thread_scope filter + build_thread_scope()")
ww(REPO, s)

# ───────────────────────── orchestrator.py ─────────────────────────
o = rw(ORCH)

# 1. Compute thread scope + tag incoming log
o = sub(o,
"""            # 2. Log incoming message into historical ledger
            await msg_repo.log_message(
                telegram_message_id=telegram_message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                text=message_text,
                media_type=media_type,
                is_from_bot=False,
            )""",
"""            # 2. Log incoming message into historical ledger (tagged with strict thread scope)
            thread_scope = MessageRepository.build_thread_scope(target_bot_id or "master_omar_official", sender_id)
            await msg_repo.log_message(
                telegram_message_id=telegram_message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                text=message_text,
                media_type=media_type,
                sentiment=thread_scope,
                is_from_bot=False,
            )""",
"orchestrator: incoming log tagged with thread_scope")

# 2. Replace invalid sender_id kwarg
o = sub(o,
"""            recent_history = await msg_repo.get_recent_chat_history(
                chat_id=chat_id,
                limit=10,
                sender_id=sender_id,  # prevents cross-user context bleed
            )""",
"""            recent_history = await msg_repo.get_recent_chat_history(
                chat_id=chat_id,
                limit=10,
                thread_scope=thread_scope,  # (bot_id, chat_id, sender_id) — zero cross-user / cross-bot bleed
            )""",
"orchestrator: history fetch uses thread_scope")

# 3. Tag outgoing bot reply with same scope + reply link
o = sub(o,
"""                text=raw_reply,
                perceived_emotion=f"BOT:{active_persona_name}",
                is_from_bot=True,
            )""",
"""                text=raw_reply,
                sentiment=thread_scope,
                perceived_emotion=f"BOT:{active_persona_name}",
                is_from_bot=True,
                reply_to_msg_id=telegram_message_id,
            )""",
"orchestrator: outgoing log tagged with thread_scope")

# 4. Pass bot_id to context_linker
o = sub(o,
"""            current_chat_id=chat_id,
            is_dm=is_dm,
        )
        social_affinity_guidance""",
"""            current_chat_id=chat_id,
            is_dm=is_dm,
            bot_id=target_bot_id or "master_omar_official",
        )
        social_affinity_guidance""",
"orchestrator: context_linker receives bot_id")

# 5. Vector memory recall/store: label by persona to avoid cross-bot memory bleed
o = sub(o,
"""        memories_str = "\\n".join(f"- {m['text']}" for m in recalled_memories) if recalled_memories else \"\"""",
"""        # Per-bot memory isolation: only keep memories authored by THIS persona (or legacy unlabeled ones for Omar)
        _scope_persona = target_bot_name or "عمر"
        _iso_mem = []
        for m in (recalled_memories or []):
            _t = m.get('text', '') if isinstance(m, dict) else str(m)
            if f"-> {_scope_persona}:" in _t or (_scope_persona == "عمر" and "-> " in _t and "-> عمر:" in _t):
                _iso_mem.append(_t)
        memories_str = "\\n".join(f"- {t}" for t in _iso_mem)""",
"orchestrator: vector memories isolated per persona")

ww(ORCH, o)
print("\\nDone.")

