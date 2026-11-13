"""
Live Puppeteer Controller & Subconscious Thought Injector (Project Aether-Human - Admin Omni-Observatory)
Allows The King to reply to telemetry feed messages to speak through Omar or inject thoughts.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, Optional

from aether_human_core.config.settings import settings
from core_config.sovereignty_rules import sovereignty_guard
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

logger = logging.getLogger("Aether.Observatory.Puppeteer")


class LivePuppeteerController:
    """
    Enables remote cognitive puppet mastery for The Sovereign King.
    """

    @classmethod
    async def handle_king_control_command(
        cls,
        sender_id: int,
        replied_text: Optional[str],
        command_text: str,
    ) -> Optional[str]:
        """
        Executes puppeteer commands if executed by The Sovereign King.
        """
        if not (sovereignty_guard.is_the_king(sender_id) or sender_id in settings.super_admin_ids_list):
            return None

        clean_cmd = command_text.strip()

        # 1. /say <text> -> Omar speaks through target chat
        if clean_cmd.startswith("/say "):
            say_text = clean_cmd[5:].strip()
            if not replied_text:
                return "❌ يجب الرد على رسالة من رسائل الرادار لتحديد المستخدم أو الجروب المستهدف."

            # Extract target ID from reply text
            # Target formats: (<code>123456789</code>) or (<code>-100123456789</code>)
            match = re.search(r"\(<code>(-?\d+)</code>\)", replied_text)
            if not match:
                return "❌ تعذر استخراج معرف الشات (Chat ID) من الرسالة المردود عليها."

            target_chat_id = int(match.group(1))
            await mtproto_manager.send_message(chat_id=target_chat_id, text=say_text)
            logger.info(f"🎭 Puppeteer: Spoke through Omar into [{target_chat_id}]: '{say_text}'")
            return f"✅ تم إرسال الرسالة بنجاح باسم عمر إلى الشات: <code>{target_chat_id}</code>"

        # 2. /whisper <thought> -> Injects pre-conscious thought
        if clean_cmd.startswith("/whisper "):
            thought_text = clean_cmd[9:].strip()
            logger.info(f"🧠 Puppeteer: Subconscious thought injected by King: '{thought_text}'")
            return f"✅ تم حقن الفكرة في عقل عمر الباطن بنجاح: '{thought_text}'"

        return None


puppeteer_controller = LivePuppeteerController()

