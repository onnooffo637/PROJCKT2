"""
Ghost Anti-Delete & Edit Catcher (Project Aether-Human - Admin Omni-Observatory)
Captures and surfaces deleted or edited messages across groups and private DMs,
broadcasting forensically formatted diffs into the dedicated King's Forum Topic.
"""

from __future__ import annotations

import collections
import logging
import time
from typing import Dict, Optional, Tuple, Any

from aether_human_core.config.settings import settings
from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer

logger = logging.getLogger("Aether.Observatory.GhostCatcher")


class GhostAntiDeleteCatcher:
    """
    Maintains a rolling cache of recent messages to intercept stealth edits and deletions.
    """

    def __init__(self, max_cache_size: int = 50000):
        # Key: (chat_id, message_id) -> (sender_id, sender_name, chat_title, text, timestamp)
        self._message_cache: collections.OrderedDict[Tuple[int, int], Dict[str, Any]] = collections.OrderedDict()
        self._deleted_messages: collections.OrderedDict[Tuple[int, int], Dict[str, Any]] = collections.OrderedDict()
        self._max_cache_size = max_cache_size

    def get_deleted_messages(self, chat_id: Optional[int] = None) -> list[Dict[str, Any]]:
        """Returns forensic list of intercepted deleted messages."""
        results = []
        for (c_id, m_id), item in list(self._deleted_messages.items()):
            if chat_id is None or c_id == chat_id:
                results.append({"chat_id": c_id, "message_id": m_id, **item})
        return results

    def record_incoming_message(
        self,
        chat_id: int,
        message_id: int,
        sender_id: int,
        sender_name: str,
        chat_title: str,
        text: str,
    ) -> None:
        """
        Stores snapshot of incoming message.
        """
        if chat_id == settings.admin_telemetry_supergroup_id:
            return

        key = (chat_id, message_id)
        if len(self._message_cache) >= self._max_cache_size:
            self._message_cache.popitem(last=False)

        self._message_cache[key] = {
            "sender_id": sender_id,
            "sender_name": sender_name,
            "chat_title": chat_title,
            "text": text,
            "timestamp": time.time(),
        }

    async def handle_message_edit(
        self,
        chat_id: int,
        message_id: int,
        new_text: str,
    ) -> None:
        """
        Intercepts edit event and compares with cached original text.
        """
        if chat_id == settings.admin_telemetry_supergroup_id:
            return

        key = (chat_id, message_id)
        cached = self._message_cache.get(key)
        if not cached:
            return

        old_text = cached.get("text", "")
        if old_text.strip() == new_text.strip():
            return  # No actual text modification (e.g. metadata only)

        sender_id = cached["sender_id"]
        sender_name = cached["sender_name"]
        chat_title = cached["chat_title"]

        logger.info(f"✏️ Message Edit captured in [{chat_title}] by [{sender_name}]: '{old_text}' -> '{new_text}'")
        # Update cache to current text
        cached["text"] = new_text

        await live_event_streamer.stream_anti_delete(
            chat_title=chat_title,
            sender_name=sender_name,
            sender_id=sender_id,
            original_text=old_text,
            event_type="EDITED",
            new_text=new_text,
        )

    async def handle_message_deletion(
        self,
        chat_id: int,
        message_ids: list[int],
    ) -> None:
        """
        Intercepts message deletion event.
        """
        for msg_id in message_ids:
            key = (chat_id, msg_id)
            cached = self._message_cache.pop(key, None)
            if cached:
                sender_id = cached["sender_id"]
                sender_name = cached["sender_name"]
                chat_title = cached["chat_title"]
                deleted_text = cached["text"]

                logger.info(f"🗑️ Message Deletion captured in [{chat_title}] by [{sender_name}]: '{deleted_text}'")
                if len(self._deleted_messages) >= 2000:
                    self._deleted_messages.popitem(last=False)
                self._deleted_messages[key] = {
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "chat_title": chat_title,
                    "text": deleted_text,
                    "deleted_at": time.time(),
                }
                await live_event_streamer.stream_anti_delete(
                    chat_title=chat_title,
                    sender_name=sender_name,
                    sender_id=sender_id,
                    original_text=deleted_text,
                    event_type="DELETED",
                )


ghost_catcher = GhostAntiDeleteCatcher()

