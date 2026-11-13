"""
Proactive Autonomous Initiator and Subconscious Event Daemon.
Spontaneously initiates conversations with high-affinity friends, checks on life events (exams, interviews),
and monitors interpersonal absences without external triggers.
"""

from __future__ import annotations

import logging
import asyncio
import random
from datetime import datetime, timedelta
import time
from typing import List, Dict, Optional, Any

from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.database.vector_store.qdrant_client import vector_memory
from aether_human_core.telegram_client.human_typer import human_typer
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
from aether_human_core.psychology_engine.affinity_matrix import RelationshipTier
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine

logger = logging.getLogger("Aether.Daemon.ProactiveInitiator")


class ProactiveInitiatorDaemon:
    """
    Subconscious background loop driving human proactivity and emotional initiative.
    """
    ABSENCE_CHECK_PHRASES = [
        "إيه يا عم الغيبة دي كلها؟ قلقتني عليك والله.. طمني إيه أخبارك؟",
        "وحشتني يا غالي.. بقالك كام يوم مختفي ومطمنيش، خير في إيه؟",
        "مساء الفل.. افتكرتك فجأة قولت لازم أسأل عليك وأشوف يومك ماشي إزاي.",
        "طمني عليك، شغلتك الدنيا أوي كدا ولا إيه؟",
    ]

    PARTNER_MISSING_PHRASES = [
        "وحشتيني أوي.. مختفية بقالك حبة وقلبي مش متطمن، طمنيني عليكي يا روحي ❤️",
        "إيه الغيبة دي؟ اليوم ملوش طعم من غير ما نرغي.. مستنيكي تطمنيني أول ما تشوفي الرسالة ❤️",
    ]

    EVENT_FOLLOW_UP_TEMPLATES = [
        "طمني يا بطل عملت إيه في موضوع {event_name}؟ يا رب تكون الدنيا مشيت تمام!",
        "كنت مستني أطمن عليك.. إيه الأخبار في {event_name}؟ طحنتهم ولا إيه؟",
    ]

    # Task 2.3 (2): Interesting topics for autonomous group browsing & topic jumping
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
        self._last_group_jump_ts: Dict[int, float] = {}

    def start(self) -> None:
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._daemon_loop())
            logger.info("Proactive Initiator Daemon started.")

    def stop(self) -> None:
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Proactive Initiator Daemon stopped.")

    async def _daemon_loop(self) -> None:
        while self._is_running:
            try:
                await self.evaluate_proactive_initiatives()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in Proactive Initiator loop: {exc}")

            # Task 2.3 (2): Periodically browse every 20-40 minutes
            next_sleep = random.uniform(1200.0, 2400.0)
            await asyncio.sleep(next_sleep)

    async def evaluate_proactive_initiatives(self) -> None:
        """
        Scans for users with high affinity who have been silent, or scheduled human life events.
        """
        circadian = circadian_engine.evaluate_circadian_state()
        if circadian["is_sleeping"]:
            logger.debug("Omar is sleeping. Skipping proactive messaging initiative.")
            return

        # Task 2.3 (2): Autonomous Group Browsing & Topic Jumping
        try:
            await self.browse_and_jump_into_groups()
        except Exception as grp_exc:
            logger.debug(f"Autonomous group browsing notice: {grp_exc}")

        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            top_users = await user_repo.get_top_affinity_users(limit=10)

        now = datetime.utcnow()
        for user in top_users:
            # Ignore test dummy users with short synthetic IDs
            if user.telegram_id < 100000:
                continue

            if user.affinity_score < 40.0:
                continue

            last_seen = user.last_interaction_at or user.created_at
            silence_duration = now - last_seen

            # If user has been silent for more than 24 hours (or 14 hours for romantic partner)
            threshold_hours = 14 if user.relationship_tier == "EXCLUSIVE_PARTNER" else 28
            if silence_duration > timedelta(hours=threshold_hours):
                if random.random() < 0.45:  # Organic probability
                    if user.relationship_tier == "EXCLUSIVE_PARTNER":
                        phrase = random.choice(self.PARTNER_MISSING_PHRASES)
                    else:
                        phrase = random.choice(self.ABSENCE_CHECK_PHRASES)

                    logger.info(
                        f"Proactive impulse: Messaging [{user.first_name} ({user.telegram_id})] "
                        f"after {silence_duration.total_seconds() / 3600:.1f}h of silence."
                    )

                    bursts = human_typer.prepare_message_bursts(phrase)
                    await mtproto_manager.dispatch_burst_messages(
                        chat_id=user.telegram_id, bursts=bursts
                    )

                    # Update last interaction timestamp so we don't spam
                    async with db_manager.session() as session:
                        u_repo = UserRepository(session)
                        db_user = await u_repo.get_by_telegram_id(user.telegram_id)
                        if db_user:
                            db_user.last_interaction_at = datetime.utcnow()
                            await session.flush()
                    break  # One proactive action per cycle to stay natural


    async def browse_and_jump_into_groups(self) -> None:
        """
        Task 2.3 (2) — Autonomous Group Browsing & Topic Jumping:
        Periodically (every 20–40 mins) inspects the last 5–10 messages of active groups.
        If members are discussing an interesting topic (hacking, Linux, Python, servers, drama,
        gaming, or a cool question), Userbot Gg autonomously jumps into the conversation with a
        natural, sharp human comment on the topic—even if nobody mentioned him/her!
        """
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

            transcript_block = "\n".join(msg_lines[-8:])
            gender_hint = "بنت شابة ذكية وفاهمة" if chosen_bot.gender == "female" else "شاب ذكي وفاهم"
            prompt = (
                f"آخر رسائل دارت في الجروب الآن بين الأعضاء:\n{transcript_block}\n\n"
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


proactive_daemon = ProactiveInitiatorDaemon()
