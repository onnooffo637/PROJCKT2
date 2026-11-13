"""
Anti-Spam Silent Drop Middleware for Project Aether-Human (V6.0).
Provides cross-bot deduplication, message-id tracking, and per-bot rate isolation.
Guarantees that sibling bots (Omar, Maryam, Masa, Gg) polling the same message
never trigger false-positive spam mutes against real users.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

from aether_human_core.config.settings import settings
from core_config.sovereignty_rules import sovereignty_guard

logger = logging.getLogger("Aether.Security.AntiSpamGuard")


class AntiSpamGuard:
    """
    Intelligent cross-bot rate limiter & deduplicator:
    - Tracks seen messages across all sibling bots: if the same (chat_id, user_id, message_id)
      is seen within 5.0s, it is recognized as the SAME Telegram message and never counted again.
    - Keys rate limits by (bot_id, chat_id, user_id).
    - Threshold: Drops only if >= 5 distinct message_ids arrive in < 2.5 seconds on the same bot.
    - 100% Silent Drop: returns True (meaning drop), never raises or outputs fallback text.
    - King and Super Admins are strictly exempt.
    """

    def __init__(self):
        # Global deduplicator: (chat_id, user_id, message_id) -> first_seen_timestamp
        self._seen_messages: Dict[Tuple[int, int, int], float] = {}
        # Keyed rate limiter: (bot_id, chat_id, user_id) -> List of (timestamp, message_id)
        self._user_events: Dict[Tuple[str, int, int], List[Tuple[float, int]]] = {}
        # Mute window: (bot_id, user_id) -> unmuted_timestamp
        self._muted_until: Dict[Tuple[str, int], float] = {}

    def is_spam(
        self,
        user_id: int,
        bot_id: Optional[str] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
    ) -> bool:
        """
        Evaluates whether an incoming event should be silently dropped.
        Returns True to drop silently (meaning it is spam/muted), False to permit processing.
        """
        if not user_id:
            return False

        # 1. Bypass for King (Zero) and Super Admins
        if sovereignty_guard.is_king(user_id) or user_id in settings.super_admin_ids_list:
            return False

        now = time.time()
        b_id = str(bot_id or "default")
        c_id = int(chat_id or 0)
        m_id = int(message_id or 0)

        # 2. Check active mute window for this bot + user
        mute_key = (b_id, user_id)
        muted_expire = self._muted_until.get(mute_key, 0.0)
        if now < muted_expire:
            remaining = muted_expire - now
            logger.debug(
                f"AntiSpam: User [{user_id}] on bot [{b_id}] is muted for {remaining:.1f}s. Silently dropping."
            )
            return True

        # 3. Cross-Bot Message ID Deduplication:
        # If multiple bots receive the EXACT same Telegram message, only the first bot's evaluation
        # logs the event; subsequent sibling bots recognize it as the SAME message and do NOT treat it as spam.
        if m_id > 0 and c_id != 0:
            msg_key = (c_id, user_id, m_id)
            if msg_key in self._seen_messages:
                last_seen = self._seen_messages[msg_key]
                if (now - last_seen) < 5.0:
                    # Same message polled concurrently by another sibling bot! Safe pass.
                    return False
            self._seen_messages[msg_key] = now

            # Periodic cleanup of seen messages cache (> 15 seconds old)
            if len(self._seen_messages) > 1000:
                self._seen_messages = {
                    k: t for k, t in self._seen_messages.items() if (now - t) < 15.0
                }

        # 4. Clean expired events (> 3.0s old) for this specific (bot_id, chat_id, user_id)
        rate_key = (b_id, c_id, user_id)
        events = self._user_events.get(rate_key, [])
        cutoff = now - 3.0
        events = [(t, mid) for t, mid in events if t > cutoff]

        # 5. Check burst rate in the last 2.5s for DISTINCT message_ids
        recent_2_5s = [(t, mid) for t, mid in events if t > (now - 2.5)]
        distinct_msg_ids = {mid for _, mid in recent_2_5s if mid > 0}

        burst_count = len(distinct_msg_ids) if distinct_msg_ids else len(recent_2_5s)

        if burst_count >= 5:
            # Trigger 10-second silent mute on this bot
            self._muted_until[mute_key] = now + 10.0
            self._user_events[rate_key] = []
            logger.warning(
                f"🚫 [Anti-Spam] Genuine burst spam detected from user [{user_id}] on bot [{b_id}] "
                f"({burst_count} distinct messages in < 2.5s). Applying 10s silent mute."
            )
            return True

        # 6. Record current event
        events.append((now, m_id))
        self._user_events[rate_key] = events
        return False

    def reset_user(self, user_id: int) -> None:
        """Manually un-mute a user across all bots."""
        keys_to_unmute = [k for k in self._muted_until if k[1] == user_id]
        for k in keys_to_unmute:
            self._muted_until.pop(k, None)
        events_to_clear = [k for k in self._user_events if k[2] == user_id]
        for k in events_to_clear:
            self._user_events.pop(k, None)


# Global singleton instance
anti_spam_guard = AntiSpamGuard()
