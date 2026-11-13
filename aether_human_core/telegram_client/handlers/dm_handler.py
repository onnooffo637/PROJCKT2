"""
Private Direct Message (DM) Event Handler for Project Aether-Human.
Executes individual relationship progression, multi-tenant isolated persona virtualization,
custom private commands, OSINT tracking, and telemetry streaming.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional, Any

from aether_human_core.config.settings import settings
from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
from aether_human_core.telegram_client.human_typer import human_typer
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
from multi_tenant_sandbox.custom_command_compiler import custom_commands
from multi_tenant_sandbox.zero_leakage_firewall import zero_leakage_firewall
from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
from admin_telemetry_and_archiver.passive_omni_archiver import omni_archiver
from admin_telemetry_and_archiver.ghost_anti_delete_catcher import ghost_catcher
from admin_telemetry_and_archiver.osint_search_and_filter_engine import osint_engine

logger = logging.getLogger("Aether.Telegram.DMHandler")


class PrivateDMHandler:
    """
    Manages private 1-on-1 chats with multi-tenant isolated sandboxes.
    """

    @classmethod
    async def handle_dm_message(
        cls,
        message_id: int,
        sender_id: int,
        sender_name: str,
        sender_gender: str,
        message_text: str,
        sender_username: Optional[str] = None,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
        target_bot_name: str = "عمر",
        target_bot_id: str = "master_omar_official",
        media_type: str = "text",
    ) -> None:
        """
        Processes private 1-on-1 chat event.
        Guarantees strict client-bound reply transport and per-bot persona isolation.
        """
        channel_type = "Userbot MTProto" if is_userbot else "Official Bot API"
        logger.info(f"Private DM via [{channel_type} - {target_bot_name}] from [{sender_id} ({sender_name})]: '{message_text[:40]}...'")

        # 1. OSINT & Telemetry Tracking
        osint_engine.track_user_identity(user_id=sender_id, first_name=sender_name, username=sender_username)
        ghost_catcher.record_incoming_message(
            chat_id=sender_id,
            message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_title=f"خاص مع {sender_name}",
            text=message_text,
        )
        omni_archiver.archive_message(
            message_id=message_id,
            chat_id=sender_id,
            chat_title=f"خاص مع {sender_name}",
            chat_type="private",
            sender_id=sender_id,
            sender_name=sender_name,
            sender_username=sender_username,
            message_text=message_text,
        )

        # 2. Check Custom Commands (Multi-Tenant Isolated Sandbox)
        cmd_result = custom_commands.match_and_execute(sender_id, message_text)
        if cmd_result:
            custom_reply = cmd_result.get("output", "")
            bursts = human_typer.prepare_message_bursts(custom_reply)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=sender_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )
            await live_event_streamer.stream_dm_event(
                sender_id=sender_id,
                sender_name=sender_name,
                user_text=message_text,
                bot_reply=f"[أمر خاص: {cmd_result.get('command')}] {custom_reply}",
                persona_name="Custom Command",
            )
            return

        # 3. Retrieve Tenant Isolated Persona
        tenant_persona = persona_virtualizer.get_persona(sender_id)
        persona_instruction = tenant_persona.to_system_instruction()

        # 4. Delayed Read Receipt (Seen simulation)
        # Note: For Userbot, Phase 1 (variable unseen delay + send_read_acknowledge) already ran in on_new_message.
        if not is_userbot:
            seen_delay = random.uniform(1.0, 3.5)
            await mtproto_manager.mark_seen(chat_id=sender_id, max_id=message_id, delay_sec=seen_delay)

        think_phase_started_at = time.time() if is_userbot else 0.0

        # 5. Run cognitive engine with user's private persona
        resp = await cognitive_orchestrator.process_incoming_event(
            telegram_message_id=message_id,
            chat_id=sender_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
            media_type=media_type,
            sender_gender=sender_gender,
            chat_type="private",
            chat_title=f"خاص مع {sender_name}",
            extra_system_instruction=persona_instruction,
            tenant_persona=tenant_persona,
            is_userbot=is_userbot,
            target_bot_name=target_bot_name,
            target_bot_id=target_bot_id,
        )

        # 6. Selective Reply vs Reply Handling
        active_persona_display = target_bot_name if is_userbot else (tenant_persona.persona_name if tenant_persona else "عمر")
        if resp.decision_type in ("GHOST_SEEN", "IGNORE"):
            from aether_human_core.config.settings import settings
            is_creator = (sender_id == settings.the_king_user_id) or (sender_id in settings.super_admin_ids_list)
            if is_userbot and not is_creator:
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
            await asyncio.sleep(remaining_think)

        # 7. Handle Reaction Emoji
        if resp.reaction_emoji:
            await mtproto_manager.send_reaction(
                chat_id=sender_id,
                message_id=message_id,
                emoji=resp.reaction_emoji,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )

        # 8. Handle Text Reply via multi-bubble bursts strictly through original client
        dispatched_text = ""
        if resp.raw_response_text and resp.decision_type not in ("GHOST_SEEN", "IGNORE", "REACT_ONLY"):
            safe_text = zero_leakage_firewall.sanitize_response_text(resp.raw_response_text, "private")
            dispatched_text = safe_text
            bursts = human_typer.prepare_message_bursts(safe_text, is_shy=resp.is_shy)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=sender_id,
                bursts=bursts,
                reply_to_msg_id=message_id,
                is_userbot=is_userbot,
                userbot_client=userbot_client,
            )

        # 9. Stream to King's Forum Supergroup in Real-Time
        p_name = f"{target_bot_name} (Userbot)" if is_userbot else active_persona_display
        asyncio.create_task(
            live_event_streamer.stream_dm_event(
                sender_id=sender_id,
                sender_name=sender_name,
                user_text=message_text,
                bot_reply=dispatched_text or resp.raw_response_text,
                persona_name=p_name,
            )
        )

        # 10. Status Notification for Affinity Updates
        if resp.affinity_notification:
            await mtproto_manager.send_ephemeral_message(
                chat_id=sender_id,
                text=resp.affinity_notification,
                duration_sec=4.5,
            )

        # 11. Execute Loyalty Reporting
        if resp.loyalty_partner_id and resp.loyalty_report_message:
            logger.info(
                f"Dispatching Loyalty Report to Partner [{resp.loyalty_partner_id}]: '{resp.loyalty_report_message}'"
            )
            report_bursts = human_typer.prepare_message_bursts(resp.loyalty_report_message)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=resp.loyalty_partner_id, bursts=report_bursts
            )


dm_handler = PrivateDMHandler()
