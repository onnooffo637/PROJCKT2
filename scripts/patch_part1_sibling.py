"""
PART 1 — Task 1.2: Sibling Defense false-positive fix (sibling_bot_network.py + group_handler.py)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\monsm\Downloads\New folder (6)\New folder"
SIB = ROOT + r"\bot_factory\sibling_bot_network.py"
GH = ROOT + r"\aether_human_core\telegram_client\handlers\group_handler.py"


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


s = rw(SIB)
NL = "\r\n" if "\r\n" in s else "\n"

# 1. Missing BotPlatformType import (NameError swallowed silently -> sibling IDs set incomplete)
s = sub(s,
"from bot_factory.models import BotInstanceConfig, BotGender\n",
"from bot_factory.models import BotInstanceConfig, BotGender, BotPlatformType\n",
"sibling: BotPlatformType import")

# 2. Ledger entry stores reply target
s = sub(s,
"""    target_bot_id: Optional[str] = None
    target_bot_name: Optional[str] = None
    is_flirt: bool = False""",
"""    target_bot_id: Optional[str] = None
    target_bot_name: Optional[str] = None
    reply_to_from_id: Optional[int] = None
    is_flirt: bool = False""",
"sibling: GroupLedgerEntry.reply_to_from_id")

# 3. Defense cooldown state
s = sub(s,
"""        self._recent_human_messages: Dict[int, List[float]] = {}
""",
"""        self._recent_human_messages: Dict[int, List[float]] = {}
        # Sibling defense anti-spam: chat_id -> last defense timestamp
        self._last_defense_time: Dict[int, float] = {}
        self._defense_cooldown_sec: float = 120.0
""",
"sibling: defense cooldown state")

# 4. record_group_message: dedup per (chat_id, message_id) + resolve target
s = sub(s,
"""        target_bot_id: Optional[str] = None,
        target_bot_name: Optional[str] = None,
    ) -> GroupLedgerEntry:
        \"\"\"
        Registers an observed group message into the shared cross-bot ledger.
        \"\"\"
        is_flirt, is_disrespect = self.scan_flirt_or_disrespect(message_text)""",
"""        target_bot_id: Optional[str] = None,
        target_bot_name: Optional[str] = None,
        reply_to_from_id: Optional[int] = None,
    ) -> GroupLedgerEntry:
        \"\"\"
        Registers an observed group message into the shared cross-bot ledger.
        Idempotent per (chat_id, message_id): every bot that receives the same group update
        shares ONE ledger entry, so a defense can never be fired twice for one message.
        \"\"\"
        for existing in self._shared_ledger.get(chat_id, []):
            if existing.message_id == message_id:
                if reply_to_from_id and not existing.reply_to_from_id:
                    existing.reply_to_from_id = reply_to_from_id
                return existing

        if not target_bot_id:
            targeted = self.resolve_targeted_sibling(message_text, reply_to_from_id)
            if targeted:
                target_bot_id, target_bot_name = targeted.bot_id, targeted.name

        is_flirt, is_disrespect = self.scan_flirt_or_disrespect(message_text)""",
"sibling: record_group_message dedup + target resolution")

s = sub(s,
"""            target_bot_id=target_bot_id,
            target_bot_name=target_bot_name,
            is_flirt=is_flirt,""",
"""            target_bot_id=target_bot_id,
            target_bot_name=target_bot_name,
            reply_to_from_id=reply_to_from_id,
            is_flirt=is_flirt,""",
"sibling: entry construct reply_to_from_id")

# 5. Replace evaluate_sibling_defense entirely
start = s.find("    def evaluate_sibling_defense(")
end = s.find("    def get_family_context(")
if start == -1 or end == -1:
    print("⚠️  evaluate_sibling_defense block not found")
else:
    NEW_BLOCK = '''    # ------------------------------------------------------------------
    # Strict target resolution helpers (Task 1.2)
    # ------------------------------------------------------------------
    CREATOR_ID = 8287744705
    CREATOR_TOKENS = ["زيرو", "زيروا", "عبد الرحمن", "عبدالرحمن", "ecenn", "@ecenn"]

    @staticmethod
    def _norm(text: str) -> str:
        return (
            (text or "").lower().strip()
            .replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            .replace("ة", "ه").replace("ى", "ي")
        )

    @staticmethod
    def _has_whole_word(text_norm: str, token: str) -> bool:
        """Whole-word match (Arabic-aware): 'عمر' does NOT match inside 'عمري'."""
        if not token:
            return False
        return re.search(rf"(?<![\\w@]){re.escape(token)}(?!\\w)", text_norm) is not None

    def _strict_name_tokens(self, ident: Any) -> List[str]:
        """
        Explicit-mention tokens only: full name, first word, @username.
        Deliberately excludes auto-generated diminutives (e.g. 'عمري' = 'my life') which caused false positives.
        Very short names (<=2 chars, e.g. 'Gg' == gaming slang 'gg') require a vocative 'يا' or @username.
        """
        tokens: List[str] = []
        name_n = self._norm(re.sub(r"[^\\w\\s]", "", getattr(ident, "name", "") or ""))
        uname = (getattr(ident, "username", "") or "").lower().lstrip("@").strip()
        if uname:
            tokens.append(f"@{uname}")
        if name_n:
            first = name_n.split()[0]
            if len(first) <= 2:
                tokens.extend([f"يا {first}", f"يا{first}"])
            else:
                tokens.append(name_n)
                tokens.append(first)
        if getattr(ident, "bot_id", "") == "master_omar_official":
            tokens.extend(["عمور", "عموره"])
        return list(dict.fromkeys(tokens))

    def resolve_targeted_sibling(self, message_text: str, reply_to_from_id: Optional[int] = None) -> Optional[Any]:
        """
        Returns the sibling BotIdentity that is the TRUE target of a message, or None (== 'TargetBot: General').
        Target is established ONLY by:
          (a) a direct reply to that bot's own message (reply_to_from_id == bot numeric id), or
          (b) an explicit whole-word mention of its name / @username.
        """
        from bot_factory.group_arbiter import group_arbiter
        all_bots = group_arbiter.get_all_active_bots()

        if reply_to_from_id:
            for ident in all_bots.values():
                if ident.numeric_id and ident.numeric_id == reply_to_from_id:
                    return ident

        text_norm = self._norm(message_text)
        for ident in all_bots.values():
            for tok in self._strict_name_tokens(ident):
                if self._has_whole_word(text_norm, self._norm(tok)):
                    return ident
        return None

    def _is_targeted_creator_insult(self, entry: GroupLedgerEntry) -> bool:
        """Creator defense only if an insult lands within 4 words of the creator's name, or replies to the creator."""
        if not entry.is_disrespect:
            return False
        if entry.reply_to_from_id == self.CREATOR_ID:
            return True
        words = self._norm(entry.message_text).split()
        joined_positions = []
        for i in range(len(words)):
            window2 = " ".join(words[i:i + 2])
            if any(self._norm(t) in (words[i], window2) for t in self.CREATOR_TOKENS):
                joined_positions.append(i)
        if not joined_positions:
            return False
        for pos in joined_positions:
            window = " ".join(words[max(0, pos - 4): pos + 6])
            if any(re.search(p, window) for p in self.DISRESPECT_PATTERNS):
                return True
        return False

    def _pick_verified_defender(self, chat_id: int, preferred_bot_id: str, exclude_bot_id: Optional[str]) -> Optional[Any]:
        """Defender MUST have verified presence in chat_id (no unverified fallback -> no 400 chat not found)."""
        from bot_factory.group_arbiter import group_arbiter
        present = [b for b in group_arbiter.get_present_bots(chat_id) if group_arbiter.is_bot_present(chat_id, b.bot_id)]
        present = [b for b in present if b.bot_id != exclude_bot_id]
        if not present:
            return None
        for b in present:
            if b.bot_id == preferred_bot_id:
                return b
        return present[0]

    def evaluate_sibling_defense(
        self,
        entry: GroupLedgerEntry,
        current_bot: BotInstanceConfig,
    ) -> Optional[Tuple[str, Any]]:
        """
        Evaluates whether a sibling bot present in this group should defend another sibling
        OR defend the creator (ECENN / Zero 8287744705).

        STRICT RULES (false-positive fix):
          1. Never triggered by messages from the creator or from any server sibling bot.
          2. Sibling defense ONLY when the insult/flirt is aimed at a sibling via direct reply
             to that sibling's message OR explicit whole-word mention of its name/@username.
             'TargetBot: General' -> defense is skipped entirely.
          3. Target sibling AND defender must both be verified members of entry.chat_id.
          4. One defense per message (shared ledger entry) + 120s cooldown per chat.
        Returns: (defense_reply_text, defending_bot_identity)
        """
        if entry.sender_user_id == self.CREATOR_ID:
            return None
        if self.is_server_sibling(entry.sender_user_id):
            return None
        if entry.defended:
            return None
        if not (entry.is_flirt or entry.is_disrespect):
            return None

        now = time.time()
        if now - self._last_defense_time.get(entry.chat_id, 0.0) < self._defense_cooldown_sec:
            logger.debug(f"Sibling defense cooldown active in chat [{entry.chat_id}] — skipping.")
            return None

        from bot_factory.group_arbiter import group_arbiter
        preferred_id = getattr(current_bot, "instance_id", "master_omar_official")

        # 1. Creator defense (targeted only)
        if self._is_targeted_creator_insult(entry):
            defender = self._pick_verified_defender(entry.chat_id, preferred_id, exclude_bot_id=None)
            if not defender:
                return None
            retort = f"إلا زيرو! ده على راسنا من فوق ومسمحش لحد يمسه بنص كلمة. الزم حدودك يا {entry.sender_name} 🛑"
            entry.defended = True
            entry.defender_bot_id = defender.bot_id
            entry.defense_reply_text = retort
            self._last_defense_time[entry.chat_id] = now
            logger.info(f"Creator Defense Triggered! [{defender.name}] in chat [{entry.chat_id}].")
            return retort, defender

        # 2. Sibling defense — requires an explicit target
        target_ident = None
        if entry.target_bot_id:
            target_ident = group_arbiter.get_all_active_bots().get(entry.target_bot_id)
        if not target_ident:
            target_ident = self.resolve_targeted_sibling(entry.message_text, entry.reply_to_from_id)
        if not target_ident:
            logger.info(f"SiblingDefense: TargetBot=General in chat [{entry.chat_id}] — defense skipped (no explicit target).")
            return None

        # Target must be a verified member of this chat (a reply to its message proves membership)
        if entry.reply_to_from_id and entry.reply_to_from_id == target_ident.numeric_id:
            group_arbiter.record_presence(entry.chat_id, target_ident.bot_id)
        if not group_arbiter.is_bot_present(entry.chat_id, target_ident.bot_id):
            logger.info(f"SiblingDefense: target [{target_ident.name}] not verified in chat [{entry.chat_id}] — skipped.")
            return None

        defender = self._pick_verified_defender(entry.chat_id, preferred_id, exclude_bot_id=target_ident.bot_id)
        if not defender:
            return None

        defender_cfg = bot_factory.get_bot(defender.bot_id)
        target_cfg = bot_factory.get_bot(target_ident.bot_id)
        target_is_female = (target_ident.gender == "female")
        if defender_cfg and target_cfg:
            target_title = self.get_sibling_relation(defender_cfg, target_cfg).relation_title_a_to_b
        else:
            target_title = "أختي" if target_is_female else "أخويا"
        pron = "دي" if target_is_female else "ده"
        tname = target_ident.name

        if entry.is_flirt:
            retorts = [
                f"احترم نفسك يا {entry.sender_name}. {tname} {pron} {target_title} وخط أحمر 😡",
                f"اتلم يا {entry.sender_name} وبلاش الحركات دي مع {tname} 🔥",
                f"{tname} {pron} {target_title} ومش هسمح لحد يستظرف معاها/معاه هنا. الزم حدودك 🚫",
            ]
            if target_is_female:
                retorts[2] = f"{tname} {pron} {target_title} ومش هسمح لحد يستظرف معاها هنا. الزم حدودك 🚫"
            else:
                retorts[2] = f"{tname} {pron} {target_title} ومش هسمح لحد يستظرف معاه هنا. الزم حدودك 🚫"
        else:
            retorts = [
                f"لما تتكلم عن {tname} اتكلم بأدب يا {entry.sender_name} 😤",
                f"لسانك ميمسش {tname} بكلمة. عيب واحترم نفسك 🛑",
                f"إلا {tname}! {target_title} خط أحمر وأي قلة ذوق معاه/معاها تعتبر معايا أنا ⚡",
            ]
            retorts[2] = (
                f"إلا {tname}! {target_title} خط أحمر وأي قلة ذوق معاها تعتبر معايا أنا ⚡"
                if target_is_female else
                f"إلا {tname}! {target_title} خط أحمر وأي قلة ذوق معاه تعتبر معايا أنا ⚡"
            )

        chosen_defense = random.choice(retorts)
        entry.defended = True
        entry.defender_bot_id = defender.bot_id
        entry.defense_reply_text = chosen_defense
        self._last_defense_time[entry.chat_id] = now

        logger.info(
            f"Sibling Defense Triggered! Bot [{defender.name}] defending [{tname}] "
            f"against [{entry.sender_name}] in chat [{entry.chat_id}] (explicit target verified)."
        )
        return chosen_defense, defender

'''.replace("\n", NL)
    s = s[:start] + NEW_BLOCK + s[end:]
    print("✅ sibling: evaluate_sibling_defense rewritten (strict targeting)")

ww(SIB, s)

# ───────────── group_handler.py ─────────────
g = rw(GH)
g = sub(g,
"""            sender_name=sender_name,
            message_text=message_text,
        )

        # 0.5 Check Protective Sibling Defense""",
"""            sender_name=sender_name,
            message_text=message_text,
            reply_to_from_id=reply_to_from_id,
        )

        # 0.5 Check Protective Sibling Defense""",
"group_handler: pass reply_to_from_id to ledger")

# record_presence must happen BEFORE defense evaluation (already), keep master fallback cfg
g = sub(g,
"""        if master_bot:
            defense_res = sibling_network.evaluate_sibling_defense(ledger_entry, current_bot=master_bot)""",
"""        current_bot_cfg = cls._safe_get_bot(target_bot_id) or master_bot
        if current_bot_cfg:
            defense_res = sibling_network.evaluate_sibling_defense(ledger_entry, current_bot=current_bot_cfg)""",
"group_handler: defense evaluated with the receiving bot's config")
ww(GH, g)
print("Done.")

