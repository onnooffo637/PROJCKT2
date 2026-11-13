"""
Central Multi-Bot Group Arbiter, Dynamic Presence Tracker, & Collision Prevention Engine.
Coordinates turn election, anti-collision locking, and presence verification across all bots in the same group.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Dict, List, Optional, Set, Tuple, Any
from pydantic import BaseModel, Field

from bot_factory.models import BotInstanceConfig, BotGender, BotPlatformType

logger = logging.getLogger("Aether.BotFactory.GroupArbiter")


class BotIdentity(BaseModel):
    bot_id: str
    name: str
    numeric_id: int
    username: str = ""
    gender: str = "male"
    chattiness_level: float = 0.5
    is_userbot: bool = False
    token_or_session: str = ""
    trigger_tokens: Set[str] = Field(default_factory=set)
    only_when_addressed: bool = False

    def __hash__(self) -> int:
        return hash(self.bot_id)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BotIdentity):
            return self.bot_id == other.bot_id
        if isinstance(other, str):
            return self.bot_id == other
        return False


class ElectionDecision(BaseModel):
    should_reply: bool
    winner_bot_id: Optional[str] = None
    stagger_delay_sec: float = 0.0
    reason: str = "UNADDRESSED_SILENT"


class BanterSession(BaseModel):
    chat_id: int
    initiator_bot_id: str
    responder_bot_id: str
    depth: int = 1
    max_depth: int = 2
    created_at: float = Field(default_factory=time.time)
    closed: bool = False


class CentralGroupArbiter:
    """
    Singleton arbiter managing:
    1. Dynamic auto-discovery of all bots & token generation.
    2. Group chat presence tracking (preventing 400 Bad Request: chat not found).
    3. Collision-free turn election per (chat_id, message_id).
    4. Controlled 1-turn sibling banter (7% probability, depth=2 hard stop).
    """

    def __init__(self):
        # chat_id -> {bot_id: last_seen_timestamp}
        self._presence: Dict[int, Dict[str, float]] = {}
        # (chat_id, message_id) -> Dict[bot_id, ElectionDecision]
        self._election_cache: Dict[Tuple[int, int], Dict[str, ElectionDecision]] = {}
        self._election_lock = asyncio.Lock()
        # chat_id -> last_unaddressed_reply_ts
        self._group_cooldown: Dict[int, float] = {}
        # chat_id -> BanterSession
        self._banter_sessions: Dict[int, BanterSession] = {}
        # Clean cache interval
        self._last_cache_cleanup: float = time.time()

    # =========================================================================
    # 1. Dynamic Auto-Discovery & Phonetic Token Generation
    # =========================================================================

    @staticmethod
    def generate_name_tokens(name: str, username: str = "", numeric_id: int = 0) -> Set[str]:
        """
        Dynamically extracts phonetic variants, diminutives, and call tokens for any bot name.
        Zero hardcoded names! Works for Arabic, English, or arbitrary titles.
        """
        tokens: Set[str] = set()

        # Add numeric ID
        if numeric_id > 0:
            tokens.add(str(numeric_id))

        # Add @username variants
        if username:
            clean_user = username.lower().replace("@", "").strip()
            if clean_user:
                tokens.add(f"@{clean_user}")
                tokens.add(clean_user)

        # Normalize base Arabic string
        raw = name.strip()
        clean = re.sub(r"[إأآ]", "ا", raw.lower()).replace("ة", "ه")
        # Strip decorative brackets/emojis
        clean_text = re.sub(r"[^\w\s]", "", clean).strip()

        if clean_text:
            tokens.add(clean_text)
            tokens.add(f"يا {clean_text}")
            tokens.add(f"يا{clean_text}")

            words = clean_text.split()
            first_word = words[0] if words else ""
            if len(first_word) >= 2:
                tokens.add(first_word)
                tokens.add(f"يا {first_word}")
                tokens.add(f"يا{first_word}")

                # Arabic feminine/masculine pet name generation
                if first_word.endswith("ه"):
                    stem = first_word[:-1]
                    tokens.update([f"{stem}ه", f"{stem}ة", f"{stem}تي", f"{stem}وتي", f"{stem}يتي", f"{stem}ومه", f"{stem}ومة"])
                elif len(first_word) >= 3:
                    tokens.update([f"{first_word}تي", f"{first_word}و", f"{first_word}ي", f"{first_word}ه", f"{first_word}ة"])

        return {t for t in tokens if len(t) >= 2}

    def get_all_active_bots(self) -> Dict[str, BotIdentity]:
        """
        Dynamically aggregates all bots: Master Omar, Telethon Userbot, and all Factory sub-bots.
        """
        from bot_factory.factory_manager import bot_factory
        bots: Dict[str, BotIdentity] = {}

        # 1. Master Omar Bot
        omar_id = 8677519723
        omar_tokens = self.generate_name_tokens("عمر", "omarggforbot", omar_id)
        omar_tokens.update(["عمر", "عمور", "عموره", "عمورة", "عموري", "omar", "@omarggforbot"])
        bots["master_omar_official"] = BotIdentity(
            bot_id="master_omar_official",
            name="عمر",
            numeric_id=omar_id,
            username="omarggforbot",
            gender="male",
            chattiness_level=0.5,
            is_userbot=False,
            token_or_session="8677519723:AAHcv7-6_VanLlETJKftDHWgHQXfz_bu-n8",
            trigger_tokens=omar_tokens,
        )

        # 2. Registered Factory Bots
        all_cfg = bot_factory.list_all_bots()
        for b in all_cfg:
            if b.instance_id == "master_omar_official":
                continue

            num_id = 0
            uname = getattr(b, "username", "") or ""
            is_ub = b.bot_type == BotPlatformType.MTPROTO_USERBOT or b.instance_id.startswith("userbot_")

            if is_ub:
                try:
                    num_id = int(b.instance_id.replace("userbot_", ""))
                except Exception:
                    num_id = 8656468004
            elif b.token_or_session and ":" in b.token_or_session:
                try:
                    num_id = int(b.token_or_session.split(":")[0])
                except Exception:
                    num_id = 0

            tokens = self.generate_name_tokens(b.name, uname, num_id)
            prompt_and_rules = f"{getattr(b, 'system_prompt', '') or ''} {getattr(b, 'custom_rules', '') or ''}"
            only_addressed = any(
                phrase in prompt_and_rules
                for phrase in [
                    "لا ترد ولا تتدخل في المحادثات العامة",
                    "إلا إذا ناداك أحد باسمك",
                    "الا اذا ناداك احد باسمك",
                    "لا تتدخل في المحادثات العامة",
                ]
            )
            bots[b.instance_id] = BotIdentity(
                bot_id=b.instance_id,
                name=b.name,
                numeric_id=num_id,
                username=uname,
                gender="female" if b.gender == BotGender.FEMALE else "male",
                chattiness_level=getattr(b, "chattiness_level", 0.5),
                is_userbot=is_ub,
                token_or_session=b.token_or_session,
                trigger_tokens=tokens,
                only_when_addressed=only_addressed,
            )

        return bots

    # =========================================================================
    # 2. Group Presence Tracking (Fix 400 Bad Request: chat not found)
    # =========================================================================

    def record_presence(self, chat_id: int, bot_id: str) -> None:
        """
        Marks that a specific bot instance received an update from chat_id,
        confirming it is an active member or admin in this chat.
        """
        if chat_id not in self._presence:
            self._presence[chat_id] = {}
        self._presence[chat_id][bot_id] = time.time()

    def is_bot_present(self, chat_id: int, bot_id: str) -> bool:
        """
        Checks whether bot_id has confirmed active presence in chat_id.
        """
        if chat_id > 0:
            # Direct private DMs are always 1-on-1 with that specific bot
            return True
        chat_bots = self._presence.get(chat_id, {})
        return bot_id in chat_bots

    def get_present_bots(self, chat_id: int) -> List[BotIdentity]:
        """
        Returns all registered BotIdentity objects that are actively present in chat_id.
        """
        all_bots = self.get_all_active_bots()
        if chat_id > 0:
            return list(all_bots.values())

        present_ids = self._presence.get(chat_id, {})
        # If no presence recorded yet for this group, allow all as candidates
        if not present_ids:
            return list(all_bots.values())

        return [all_bots[bid] for bid in present_ids.keys() if bid in all_bots]

    def get_delegate_bot(self, chat_id: int, preferred_bot_id: str = "master_omar_official") -> Optional[BotIdentity]:
        """
        Selects a bot confirmed to be present in chat_id. If preferred_bot_id is not in chat_id,
        delegates to an active sibling bot or Userbot Gg to avoid '400 Bad Request: chat not found'.
        """
        all_bots = self.get_all_active_bots()
        if self.is_bot_present(chat_id, preferred_bot_id) and preferred_bot_id in all_bots:
            return all_bots[preferred_bot_id]

        # Preferred bot not confirmed present in group. Pick best confirmed sibling
        present = self.get_present_bots(chat_id)
        if present:
            # Prefer Userbot Gg or first available sub-bot
            for p in present:
                if p.is_userbot:
                    return p
            return present[0]

        return all_bots.get(preferred_bot_id)

    # =========================================================================
    # 3. Collision-Free Turn Election per (chat_id, message_id)
    # =========================================================================

    async def elect_reply_turn(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int,
        message_text: str,
        reply_to_from_id: Optional[int],
        reply_to_msg_id: Optional[int],
        is_group: bool,
        requesting_bot_id: str,
    ) -> ElectionDecision:
        """
        Central turn election for incoming group messages.
        Ensures exactly ONE bot replies to an event, or schedules staggered turns when multiple
        bots are explicitly addressed by the user in the same message.
        """
        # In 1-on-1 private DMs, the receiving bot always handles the conversation
        if not is_group:
            return ElectionDecision(should_reply=True, winner_bot_id=requesting_bot_id, stagger_delay_sec=0.0, reason="PRIVATE_DM")

        # Task 4.2: While BotArenaSession is actively driving turn-taking in chat_id, suppress normal turn election
        from bot_factory.sibling_bot_network import sibling_network
        if sibling_network.is_arena_active(chat_id):
            return ElectionDecision(should_reply=False, winner_bot_id=None, stagger_delay_sec=0.0, reason="BOT_ARENA_ACTIVE")

        # Periodic cleanup of election cache older than 10 minutes
        now = time.time()
        if now - self._last_cache_cleanup > 300.0:
            cutoff = now - 600.0
            # Clean up election cache
            self._election_cache = {
                k: v for k, v in self._election_cache.items()
                if (now - getattr(v.get(list(v.keys())[0]), "timestamp", now)) < 600.0
            }
            self._last_cache_cleanup = now

        msg_key = (chat_id, message_id)

        async with self._election_lock:
            # If already evaluated for this (chat_id, message_id), return cached decision for requesting_bot_id
            if msg_key in self._election_cache:
                cached = self._election_cache[msg_key]
                if requesting_bot_id in cached:
                    return cached[requesting_bot_id]
                return ElectionDecision(should_reply=False, winner_bot_id=None, stagger_delay_sec=0.0, reason="ALREADY_ELECTED_OTHER")

            # Perform single centralized election for this message
            decisions = self._evaluate_message_election(
                chat_id=chat_id,
                message_id=message_id,
                sender_id=sender_id,
                message_text=message_text,
                reply_to_from_id=reply_to_from_id,
                reply_to_msg_id=reply_to_msg_id,
            )
            self._election_cache[msg_key] = decisions
            return decisions.get(requesting_bot_id, ElectionDecision(should_reply=False, reason="UNADDRESSED_SILENT"))

    def _evaluate_message_election(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int,
        message_text: str,
        reply_to_from_id: Optional[int],
        reply_to_msg_id: Optional[int],
    ) -> Dict[str, ElectionDecision]:
        all_bots = self.get_all_active_bots()
        present_bots = self.get_present_bots(chat_id)
        present_map = {b.bot_id: b for b in present_bots}

        decisions: Dict[str, ElectionDecision] = {}

        # ---------------------------------------------------------------------
        # Priority 1: Direct Reply to a Bot's Message (`reply_to_message`)
        # ---------------------------------------------------------------------
        if reply_to_from_id:
            for b in all_bots.values():
                if b.numeric_id == reply_to_from_id:
                    # User explicitly replied to Bot b
                    for bid in all_bots.keys():
                        if bid == b.bot_id:
                            decisions[bid] = ElectionDecision(
                                should_reply=True,
                                winner_bot_id=b.bot_id,
                                stagger_delay_sec=0.0,
                                reason="DIRECT_REPLY_MATCH",
                            )
                        else:
                            decisions[bid] = ElectionDecision(
                                should_reply=False,
                                winner_bot_id=b.bot_id,
                                stagger_delay_sec=0.0,
                                reason="REPLY_TARGETED_OTHER_BOT",
                            )
                    logger.info(f"GroupArbiter: Direct reply targeted exclusively at bot [{b.name}] ({b.bot_id}).")
                    return decisions

            # If user replied to another human, all bots stay silent
            for bid in all_bots.keys():
                decisions[bid] = ElectionDecision(
                    should_reply=False,
                    winner_bot_id=None,
                    stagger_delay_sec=0.0,
                    reason="HUMAN_TO_HUMAN_REPLY_SILENT",
                )
            logger.debug(f"GroupArbiter: User replied to another human member. All bots silent.")
            return decisions

        # ---------------------------------------------------------------------
        # Priority 2: Direct Name / @Username / Numeric ID Mention
        # ---------------------------------------------------------------------
        text_clean = re.sub(r"[إأآ]", "ا", message_text.lower()).replace("ة", "ه")
        mentioned_bots: List[BotIdentity] = []

        # Check all registered active bots (including newly added bots whose presence hasn't been logged yet)
        for b in all_bots.values():
            for token in b.trigger_tokens:
                token_clean = re.sub(r"[إأآ]", "ا", token.lower()).replace("ة", "ه").strip()
                if not token_clean:
                    continue
                pattern = r"(?<![\w\u0600-\u06FF])(?:يا\s*)?" + re.escape(token_clean) + r"(?![\w\u0600-\u06FF])"
                if re.search(pattern, text_clean):
                    if b not in mentioned_bots:
                        mentioned_bots.append(b)
                    break

        if mentioned_bots:
            # Stagger replies if multiple bots are explicitly mentioned
            for idx, b in enumerate(mentioned_bots):
                stagger = idx * 3.0  # 1st replies at 0s, 2nd at 3s, 3rd at 6s
                decisions[b.bot_id] = ElectionDecision(
                    should_reply=True,
                    winner_bot_id=b.bot_id,
                    stagger_delay_sec=stagger,
                    reason="DIRECT_NAME_OR_MENTION",
                )

            for b in all_bots.values():
                if b.bot_id not in decisions:
                    decisions[b.bot_id] = ElectionDecision(
                        should_reply=False,
                        winner_bot_id=mentioned_bots[0].bot_id,
                        stagger_delay_sec=0.0,
                        reason="OTHER_BOT_MENTIONED",
                    )

            logger.info(
                f"GroupArbiter: Mention match! Mentioned bots: {[b.name for b in mentioned_bots]} "
                f"in chat [{chat_id}] with staggered turns."
            )
            return decisions

        # ---------------------------------------------------------------------
        # Priority 3: Unaddressed General Group Message
        # ---------------------------------------------------------------------
        # Check group cooldown (at least 15s between spontaneous unaddressed replies)
        now = time.time()
        last_spontaneous = self._group_cooldown.get(chat_id, 0.0)
        cooldown_active = (now - last_spontaneous < 15.0)

        words_count = len(message_text.strip().split())
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

        if cooldown_active or not is_generic_chatter or not present_bots:
            # Stay completely silent
            for bid in all_bots.keys():
                decisions[bid] = ElectionDecision(
                    should_reply=False,
                    winner_bot_id=None,
                    stagger_delay_sec=0.0,
                    reason="UNADDRESSED_SILENT",
                )
            return decisions

        # Elect AT MOST ONE bot weighted by chattiness_level (excluding bots configured to reply ONLY when addressed)
        spontaneous_pool = [b for b in present_bots if not b.only_when_addressed]
        candidates = sorted(spontaneous_pool, key=lambda x: (x.is_userbot, x.chattiness_level), reverse=True)
        elected_bot = None

        for cand in candidates:
            # Boost spontaneous topic jump probability when an interesting topic is active
            boost = 0.40 if is_hot_topic else 0.20
            threshold = cand.chattiness_level * boost
            if random.random() < threshold:
                elected_bot = cand
                break

        if elected_bot:
            self._group_cooldown[chat_id] = now
            for b in all_bots.values():
                if b.bot_id == elected_bot.bot_id:
                    decisions[b.bot_id] = ElectionDecision(
                        should_reply=True,
                        winner_bot_id=elected_bot.bot_id,
                        stagger_delay_sec=random.uniform(1.5, 3.5),
                        reason="CHATTINESS_ELECTED_SPONTANEOUS",
                    )
                else:
                    decisions[b.bot_id] = ElectionDecision(
                        should_reply=False,
                        winner_bot_id=elected_bot.bot_id,
                        stagger_delay_sec=0.0,
                        reason="OTHER_BOT_ELECTED_SPONTANEOUS",
                    )
            logger.info(f"GroupArbiter: Spontaneously elected bot [{elected_bot.name}] in chat [{chat_id}].")
        else:
            for bid in all_bots.keys():
                decisions[bid] = ElectionDecision(
                    should_reply=False,
                    winner_bot_id=None,
                    stagger_delay_sec=0.0,
                    reason="UNADDRESSED_CHATTINESS_FAILED",
                )

        return decisions

    # =========================================================================
    # 4. Controlled 1-Turn Sibling Banter & Teasing (7% Probability, Depth=2)
    # =========================================================================

    def evaluate_sibling_teasing_trigger(
        self,
        chat_id: int,
        speaker_bot_id: str,
        message_text: str,
    ) -> Optional[Tuple[BotIdentity, str]]:
        """
        Evaluates whether a sibling bot present in chat_id should tease or advise speaker_bot_id.
        Triggers on a rare 7% random roll or tone anomaly.
        Enforces strict 1-turn reply (depth=2) hard stop to 100% prevent bot loops!
        """
        now = time.time()
        session = self._banter_sessions.get(chat_id)

        # If a banter session exists and has already completed 2 turns or is closed, halt
        if session:
            if session.closed or session.depth >= session.max_depth or (now - session.created_at < 300.0):
                return None

        # Check probability: rare 7% roll
        is_rare_roll = (random.random() < 0.07)
        flirt_words = ["حبيبي", "يا قلبي", "قمر", "عسل", "روحي", "وحشتني"]
        is_tone_anomaly = any(w in message_text for w in flirt_words) and len(message_text.split()) < 15

        if not (is_rare_roll or is_tone_anomaly):
            return None

        # Find a suitable sibling bot present in this chat
        present = self.get_present_bots(chat_id)
        siblings = [b for b in present if b.bot_id != speaker_bot_id]
        if not siblings:
            return None

        teasing_bot = random.choice(siblings)
        all_bots = self.get_all_active_bots()
        speaker_identity = all_bots.get(speaker_bot_id)
        speaker_name = speaker_identity.name if speaker_identity else "يا غالي"

        # Generate teasing line matching teasing_bot's persona and dialect
        t_gender = teasing_bot.gender
        tease_lines = [
            f"إيه يا {speaker_name} اهدي شوية مش كده ده الجروب كله باصص عليكي 😂",
            f"شبيك يا {speaker_name} على كيفك خف علينا شوية ترى فضحتينا 😂",
            f"شايفك واخدة راحتك أوي يا {speaker_name}.. اتلمي شوية وبطلي شقاوة 😉",
            f"يا جماعة حد يهدي {speaker_name} عشان شكلها شربت قهوة زيادة النهاردة ☕😂",
        ]
        if t_gender == "male":
            tease_lines.append(f"منورة يا {speaker_name} بس بلاش حركات الشوارع دي وسطينا 😂👏")

        chosen_tease = random.choice(tease_lines)

        # Initialize controlled session
        self._banter_sessions[chat_id] = BanterSession(
            chat_id=chat_id,
            initiator_bot_id=teasing_bot.bot_id,
            responder_bot_id=speaker_bot_id,
            depth=1,
            max_depth=2,
            created_at=now,
            closed=False,
        )

        logger.info(
            f"GroupArbiter: Sibling teasing triggered! Bot [{teasing_bot.name}] will tease [{speaker_name}] in [{chat_id}]."
        )
        return teasing_bot, chosen_tease

    def register_banter_reply(self, chat_id: int, bot_id: str) -> bool:
        """
        Marks that the teased bot replied once to defend itself.
        Closes the session permanently (depth=2, closed=True) so no further loop is possible.
        """
        session = self._banter_sessions.get(chat_id)
        if session and not session.closed and session.responder_bot_id == bot_id:
            session.depth += 1
            session.closed = True
            logger.info(f"GroupArbiter: Sibling banter reached hard stop (Depth 2/2) in chat [{chat_id}]. Closed.")
            return True
        return False


# Global Arbiter Singleton
group_arbiter = CentralGroupArbiter()

