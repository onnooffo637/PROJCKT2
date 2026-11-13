"""
Group Chat Event Handler and Social Dynamics Observer for Project Aether-Human.
Strictly regulates Omar's public group engagements:
- Only intervenes if explicitly tagged (@mention), replied to, or named.
- Selectively chimes in if group opinion/advice is genuinely sought on an engaging topic.
- Deliberately keeps responses ultra-concise to prevent cluttering busy group chats.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Optional, Dict, Any, List

from aether_human_core.config.settings import settings
from aether_human_core.config.llm_router import llm_pool
from core_config.sovereignty_rules import sovereignty_guard
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.database.neo4j_graph.social_graph import social_graph
from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
from aether_human_core.telegram_client.human_typer import human_typer
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
from aether_human_core.psychology_engine.affinity_matrix import UserAffinityVector, RelationshipTier
from aether_human_core.psychology_engine.micro_traits import micro_traits_engine
from bot_factory.factory_manager import bot_factory
from bot_factory.sibling_bot_network import sibling_network

from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
from admin_telemetry_and_archiver.passive_omni_archiver import omni_archiver
from admin_telemetry_and_archiver.ghost_anti_delete_catcher import ghost_catcher
from admin_telemetry_and_archiver.osint_search_and_filter_engine import osint_engine
from admin_telemetry_and_archiver.group_privilege_escalator import privilege_escalator
from multi_tenant_sandbox.zero_leakage_firewall import zero_leakage_firewall

logger = logging.getLogger("Aether.Telegram.GroupHandler")


class GroupEventHandler:
    """
    Monitors group dynamics with disciplined, realistic human participation.
    """
    @classmethod
    def _safe_get_bot(cls, bot_id: str):
        try:
            from bot_factory.factory_manager import bot_factory as _bf
            return _bf.get_bot(bot_id)
        except Exception as e:
            logger.debug(f"Error fetching bot [{bot_id}]: {e}")
            return None

    NAME_PATTERNS = [
        "عمر", "عمور", "عمورة", "عموره", "يا عمر", "ياعمر", "يعمر", "omar", "@omarggforbot"
    ]

    OPINION_TRIGGERS = [
        "إيه رأيكم", "ايه رايكم", "شايفين إيه", "شايفين ايه",
        "حد عنده رأي", "حد عنده راي", "تنصحوني بإيه", "تنصحوني بايه",
        "حد جرب", "حد يفيدنا", "أعمل إيه", "اعمل ايه", "إيه العمل",
        "ايه العمل", "إيه الحل", "ايه الحل", "مين يعرف", "رأيكم", "رايكم"
    ]

    ENGAGING_TOPICS = [
        "برمجة", "كود", "بايثون", "python", "ذكاء اصطناعي", "ai", "لابتوب",
        "هاك", "هكر", "هاكينج", "hacking", "لينكس", "linux", "كالي", "kali",
        "سيرفر", "سيرفرات", "server", "ثغرة", "سيكيورتي", "security",
        "جيم", "جيمنج", "ببجي", "فالورنت", "فيفا", "دراما", "خناقة", "حوار",
        "شغل", "شركة", "ماتش", "كورة", "أهلي", "زمالك", "كافيه",
        "قهوة", "خروجة", "سفر", "تمرين", "سعر", "موبايل"
    ]

    _last_group_reply_ts: Dict[int, float] = {}

    @classmethod
    async def handle_group_message(
        cls,
        message_id: int,
        chat_id: int,
        sender_id: int,
        sender_name: str,
        sender_gender: str,
        message_text: str,
        chat_title: str,
        is_reply_to_bot: bool = False,
        is_reply_to_other: bool = False,
        is_bot_mentioned: bool = False,
        sender_username: Optional[str] = None,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
        target_bot_name: str = "عمر",
        target_bot_id: str = "master_omar_official",
        reply_to_from_id: Optional[int] = None,
        reply_to_msg_id: Optional[int] = None,
        media_type: str = "text",
    ) -> None:
        """
        Processes group communication event with strict selectivity and full telemetry.
        """
        text_lower = message_text.lower().strip()

        # CRITICAL: Suppress all group processing, telemetry mirroring, and auto-replies
        # if the message originated inside the King's Telemetry Supergroup itself.
        if chat_id == settings.admin_telemetry_supergroup_id:
            logger.debug(f"Ignoring message inside admin telemetry supergroup ({chat_id}) to prevent feedback loops.")
            return

        logger.info(
            f"Group Event in [{chat_title} ({chat_id})]: Sender [{sender_id} ({sender_name})]: '{message_text[:35]}...'"
        )

        # 0. Forensics, OSINT Tracking & Archival
        osint_engine.track_user_identity(user_id=sender_id, first_name=sender_name, username=sender_username)
        ghost_catcher.record_incoming_message(
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_title=chat_title,
            text=message_text,
        )

        # Anti-Spam Silent Drop (with Cross-Bot Deduplication)
        from aether_human_core.telegram_client.anti_spam_guard import anti_spam_guard
        if anti_spam_guard.is_spam(sender_id, bot_id=target_bot_id, chat_id=chat_id, message_id=message_id):
            logger.info(f"🚫 [Anti-Spam] Silently dropped spam from user [{sender_id}] in group [{chat_id}].")
            return
        omni_archiver.archive_message(
            message_id=message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            chat_type="supergroup",
            sender_id=sender_id,
            sender_name=sender_name,
            sender_username=sender_username,
            message_text=message_text,
        )

        # Stream group feed to King's Forum Supergroup
        asyncio.create_task(
            live_event_streamer.stream_group_event(
                chat_title=chat_title,
                chat_id=chat_id,
                sender_name=sender_name,
                sender_id=sender_id,
                message_text=message_text,
            )
        )

        # Check King administrative escalation ONLY when explicitly requested by The King
        is_the_king_user = sovereignty_guard.is_the_king(sender_id) or sender_id in settings.super_admin_ids_list
        if is_the_king_user:
            lowered = message_text.lower().strip()
            escalation_triggers = [
                "ارفعني مشرف", "ارفعني ادمن", "ترقية", "هات الرابط", "هات رابط الجروب",
                "رابط الجروب", "اعملني مشرف", "اعملني ادمن", "/promote_king", "/escalate"
            ]
            if any(trig in lowered for trig in escalation_triggers):
                logger.info(f"King [{sender_id}] explicitly requested escalation in [{chat_title}]. Executing PrivilegeEscalator...")
                asyncio.create_task(privilege_escalator.evaluate_and_escalate_king(chat_id, chat_title))

        # 0. Sibling Bot Network: Register message in cross-bot shared ledger
        master_bot = cls._safe_get_bot("master_omar_official")
        ledger_entry = sibling_network.record_group_message(
            message_id=message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            sender_user_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
            reply_to_from_id=reply_to_from_id,
        )

        # 0.5 Check Protective Sibling Defense (Presence-Guaranteed to fix 400 Bad Request: chat not found)
        from bot_factory.group_arbiter import group_arbiter
        group_arbiter.record_presence(chat_id, target_bot_id)

        current_bot_cfg = cls._safe_get_bot(target_bot_id) or master_bot
        if current_bot_cfg:
            defense_res = sibling_network.evaluate_sibling_defense(ledger_entry, current_bot=current_bot_cfg)
            if defense_res:
                defense_reply, defender_identity = defense_res
                bursts = human_typer.prepare_message_bursts(defense_reply)
                if defender_identity.is_userbot or userbot_client is not None:
                    await mtproto_manager.dispatch_burst_messages(
                        chat_id=chat_id,
                        bursts=bursts,
                        reply_to_msg_id=message_id,
                        is_userbot=True,
                        userbot_client=userbot_client,
                    )
                elif defender_identity.bot_id == "master_omar_official":
                    await mtproto_manager.dispatch_burst_messages(
                        chat_id=chat_id,
                        bursts=bursts,
                        reply_to_msg_id=message_id,
                        is_userbot=False,
                    )
                else:
                    # Dispatch through defending sub-bot token
                    token = defender_identity.token_or_session
                    if token and ":" in token:
                        http = await mtproto_manager._get_http()
                        await http.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": defense_reply,
                                "reply_to_message_id": message_id,
                            },
                            timeout=10.0,
                        )
                return

        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            user_record = await user_repo.get_or_create(
                telegram_id=sender_id,
                first_name=sender_name,
                gender=sender_gender,
            )

        # 1. Check Group Jealousy Trigger: Is this a high-attachment partner flirting publicly?
        partner_vector = UserAffinityVector(
            user_id=sender_id,
            affinity_score=user_record.affinity_score,
            trust_score=user_record.trust_score,
            romantic_attachment=user_record.romantic_attachment,
            respect_dominance=user_record.respect_dominance,
            tier=RelationshipTier(user_record.relationship_tier),
        )

        jealousy_reproach = micro_traits_engine.evaluate_group_jealousy(
            partner_vector=partner_vector,
            partner_name=sender_name,
            message_in_group=message_text,
            target_person_name="الأعضاء في الجروب",
        )

        if jealousy_reproach:
            logger.warning(
                f"Partner [{sender_name}] triggered jealousy! Scheduling private reproach DM: '{jealousy_reproach}'"
            )
            bursts = human_typer.prepare_message_bursts(jealousy_reproach)
            await mtproto_manager.dispatch_burst_messages(chat_id=sender_id, bursts=bursts)

        # 1.5 The King / Creator sovereignty check
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

        # 2. Central Multi-Bot Group Arbiter (Collision-Free Turn Election)
        decision = await group_arbiter.elect_reply_turn(
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            message_text=message_text,
            reply_to_from_id=reply_to_from_id,
            reply_to_msg_id=reply_to_msg_id,
            is_group=True,
            requesting_bot_id=target_bot_id,
        )

        if not decision.should_reply:
            if (
                decision.winner_bot_id
                and decision.winner_bot_id != target_bot_id
                and decision.reason in ("DIRECT_NAME_OR_MENTION", "DIRECT_REPLY_MATCH")
            ):
                try:
                    from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
                    asyncio.create_task(
                        multi_bot_dispatcher.relay_group_message_to_sub_bot(
                            winner_bot_id=decision.winner_bot_id,
                            chat_id=chat_id,
                            chat_title=chat_title,
                            message_id=message_id,
                            sender_id=sender_id,
                            sender_name=sender_name,
                            sender_username=None,
                            text=message_text,
                            reply_to_msg_id=reply_to_msg_id,
                            reply_to_from_id=reply_to_from_id,
                        )
                    )
                except Exception:
                    pass
            logger.info(
                f"GroupArbiter: [{target_bot_name}] remaining silent in [{chat_title}]. Reason: {decision.reason}"
            )
            return

        if decision.stagger_delay_sec > 0:
            logger.info(f"GroupArbiter: Staggering [{target_bot_name}] reply by {decision.stagger_delay_sec:.1f}s...")
            await asyncio.sleep(decision.stagger_delay_sec)

        logger.info(f"GroupArbiter: Bot [{target_bot_name}] granted turn in [{chat_title}] due to [{decision.reason}].")

        # 2.5 Check if the message granted to this bot is a Selfie/Photo or Voice Note request
        try:
            from aether_human_core.telegram_client.handlers.media_handler import media_handler
            bot_gender_str = "female" if (
                is_userbot or (current_bot_cfg and getattr(current_bot_cfg, "gender", None) and current_bot_cfg.gender.value == "FEMALE")
            ) else "male"
            handled_group_photo = await media_handler.handle_photo_request(
                message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                message_text=message_text,
                is_reply_to_me=True,
                reply_to_other=False,
                is_userbot=is_userbot,
                persona_name=target_bot_name,
                gender=bot_gender_str,
                userbot_client=userbot_client,
                target_bot_id=target_bot_id,
            )
            if handled_group_photo:
                return

            handled_group_voice = await media_handler.handle_voice_request(
                message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                message_text=message_text,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
                target_bot_name=target_bot_name,
                target_bot_id=target_bot_id,
                is_reply_to_me=True,
                reply_to_other=False,
            )
            if handled_group_voice:
                return
        except Exception as gm_err:
            logger.debug(f"Group multimodal check notice for [{target_bot_name}]: {gm_err}")

        # 3. Cognitive orchestration
        resp = await cognitive_orchestrator.process_incoming_event(
            telegram_message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
            media_type=media_type,
            sender_gender=sender_gender,
            chat_type="supergroup",
            chat_title=chat_title,
            is_userbot=is_userbot,
            target_bot_name=target_bot_name,
            target_bot_id=target_bot_id,
        )

        # 4. Group reply delivery:
        # Delivers complete multi-bubble thoughts without leaking private tenant data
        if resp.decision_type == "REPLY" and resp.raw_response_text:
            safe_text = zero_leakage_firewall.sanitize_response_text(resp.raw_response_text, "supergroup")
            if len(safe_text) > 150:
                safe_text = safe_text[:150].rsplit(" ", 1)[0] + "..."
            bursts = human_typer.prepare_message_bursts(safe_text, is_shy=resp.is_shy, is_group=True)

            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )

            # Register banter turn closure if answering teasing
            group_arbiter.register_banter_reply(chat_id, target_bot_id)

            # Rare 7% Sibling Correction / Teasing Trigger
            tease_res = group_arbiter.evaluate_sibling_teasing_trigger(chat_id, target_bot_id, safe_text)
            if tease_res:
                teasing_bot, tease_text = tease_res
                asyncio.create_task(cls._schedule_sibling_tease(chat_id, message_id, teasing_bot, tease_text))

        if resp.reaction_emoji:
            await mtproto_manager.send_reaction(
                chat_id=chat_id,
                message_id=message_id,
                emoji=resp.reaction_emoji,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )


    @classmethod
    async def _schedule_sibling_tease(
        cls,
        chat_id: int,
        reply_to_msg_id: int,
        teasing_bot: Any,
        tease_text: str,
    ) -> None:
        """
        Delivers realistic teasing / banter from Bot B to Bot A after a human-like delay (4-6s).
        """
        await asyncio.sleep(random.uniform(4.0, 6.0))
        bursts = human_typer.prepare_message_bursts(tease_text, is_group=True)
        if teasing_bot.is_userbot:
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=reply_to_msg_id,
                is_userbot=True,
            )
        elif teasing_bot.bot_id == "master_omar_official":
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=reply_to_msg_id,
                is_userbot=False,
            )
        else:
            token = teasing_bot.token_or_session
            if token and ":" in token:
                try:
                    http = await mtproto_manager._get_http()
                    await http.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": tease_text,
                            "reply_to_message_id": reply_to_msg_id,
                        },
                        timeout=10.0,
                    )
                except Exception as ex:
                    logger.debug(f"Failed to dispatch sibling tease: {ex}")


group_handler = GroupEventHandler()
