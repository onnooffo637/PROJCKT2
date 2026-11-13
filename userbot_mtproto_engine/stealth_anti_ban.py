"""
Stealth Anti-Ban & Behavioral Obfuscation Shield for MTProto Living Userbot (V2.0).
Provides multi-layered defense against Telegram behavioral heuristics:
1. Stochastic Human Jitter (Gaussian & Poisson distributions) for typing, reading, and inter-action latencies.
2. Hard Action Caps: Rate-limits profile changes (max 2 photo/bio updates per 24h) to avoid spam flags.
3. PeerFlood Guard: Strictly prohibits initiating unsolicited DMs to strangers.
4. Automatic FloodWait Backoff: Pauses gracefully with a 1.5x safety multiplier.
5. Persistent Hardware Emulation (Samsung Galaxy S24 Ultra / OneUI 6.1).
"""

from __future__ import annotations

import asyncio
from collections import deque
import logging
import math
import random
import time
from typing import Dict, Optional, Tuple, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("Aether.Userbot.StealthShield")


class DeviceFingerprint(BaseModel):
    """
    Simulates a genuine physical smartphone footprint to prevent session suspicion.
    """
    device_model: str = "Samsung SM-S928B"       # Galaxy S24 Ultra Flagship
    system_version: str = "SDK 34 (Android 14)"   # OneUI 6.1
    app_version: str = "10.14.5 (49852)"          # Official Telegram Android Build
    lang_code: str = "ar"
    system_lang_code: str = "ar-EG"


class StealthAntiBanShield:
    """
    Comprehensive guard protecting the living MTProto userbot account from bans,
    quarantine, or FloodWait restrictions.
    """
    def __init__(self):
        self.device = DeviceFingerprint()

        # Action history timestamps for 24-hour sliding window caps
        self._photo_updates: deque[float] = deque()
        self._bio_updates: deque[float] = deque()
        self._name_updates: deque[float] = deque()

        # Contacts with whom direct messaging is pre-approved (received msg first or high trust)
        self._whitelisted_dm_peers: Set[int] = set()

        # Active FloodWait freeze timestamp
        self._flood_freeze_until: float = 0.0
        self._lock = asyncio.Lock()

    # --------------------------------------------------------------------------
    # 1. Stochastic Human Jitter & Behavioral Latency
    # --------------------------------------------------------------------------
    @staticmethod
    def get_reading_delay(char_count: int) -> float:
        """
        Calculates human reading delay based on a Gaussian distribution N(mu, sigma^2).
        Average reading speed: ~250 words per minute (~15-20 chars/sec).
        """
        if char_count <= 0:
            return 0.5
        words = max(1, char_count // 5)
        # Mean reading time: ~0.24 seconds per word + cognitive perception offset
        mu = 0.8 + (words * 0.22)
        sigma = max(0.2, mu * 0.25)
        delay = random.gauss(mu, sigma)
        # Clamp between 0.6s and 8.0s
        return max(0.6, min(delay, 8.0))

    @staticmethod
    def get_typing_jitter(base_seconds: float) -> float:
        """
        Introduces human muscle memory variance (Poisson-distributed micro-hesitations).
        """
        variance = random.uniform(-0.15, 0.25) * base_seconds
        return max(0.4, base_seconds + variance)

    @staticmethod
    def get_inter_bubble_pause() -> float:
        """
        Micro-pause between sequential chat bubbles (0.3s to 0.75s).
        """
        return random.uniform(0.3, 0.75)

    # --------------------------------------------------------------------------
    # 2. Strict Daily Action Limits (Profile Photos, Bio, Name)
    # --------------------------------------------------------------------------
    def _clean_window(self, dq: deque[float], now: float) -> None:
        DAY_SEC = 86400.0
        while dq and dq[0] < now - DAY_SEC:
            dq.popleft()

    def can_update_profile_photo(self) -> Tuple[bool, str]:
        now = time.time()
        self._clean_window(self._photo_updates, now)
        MAX_PHOTOS_PER_DAY = 2
        if len(self._photo_updates) >= MAX_PHOTOS_PER_DAY:
            remaining = int((self._photo_updates[0] + 86400.0) - now)
            return False, f"Reached daily profile photo limit (Max {MAX_PHOTOS_PER_DAY}/24h). Wait {remaining//3600}h."
        return True, "Allowed"

    def record_profile_photo_update(self) -> None:
        self._photo_updates.append(time.time())
        logger.info(f"Recorded profile photo update. Used today: {len(self._photo_updates)}/2.")

    def can_update_bio(self) -> Tuple[bool, str]:
        now = time.time()
        self._clean_window(self._bio_updates, now)
        MAX_BIO_PER_DAY = 3
        if len(self._bio_updates) >= MAX_BIO_PER_DAY:
            return False, f"Reached daily bio update limit (Max {MAX_BIO_PER_DAY}/24h)."
        return True, "Allowed"

    def record_bio_update(self) -> None:
        self._bio_updates.append(time.time())
        logger.info(f"Recorded bio update. Used today: {len(self._bio_updates)}/3.")

    def can_update_name(self) -> Tuple[bool, str]:
        now = time.time()
        self._clean_window(self._name_updates, now)
        MAX_NAME_PER_DAY = 2
        if len(self._name_updates) >= MAX_NAME_PER_DAY:
            return False, f"Reached daily name change limit (Max {MAX_NAME_PER_DAY}/24h)."
        return True, "Allowed"

    def record_name_update(self) -> None:
        self._name_updates.append(time.time())
        logger.info(f"Recorded name update. Used today: {len(self._name_updates)}/2.")

    # --------------------------------------------------------------------------
    # 3. PeerFlood Guard: Zero Unsolicited DM Outbound
    # --------------------------------------------------------------------------
    def register_inbound_dm_permission(self, peer_id: int) -> None:
        """
        Records that this peer initiated contact first or is a confirmed contact.
        Permits safe conversational responses without triggering PeerFlood.
        """
        self._whitelisted_dm_peers.add(peer_id)

    def is_safe_to_dm(self, peer_id: int, is_reply: bool = True) -> bool:
        """
        Strict check: Living userbot NEVER messages raw unknown strangers out of the blue.
        """
        if is_reply or peer_id in self._whitelisted_dm_peers:
            return True
        logger.warning(
            f"Blocked proactive DM to unknown stranger [{peer_id}]. "
            "Anti-Ban protocol forbids initiating unprovoked private chats."
        )
        return False

    # --------------------------------------------------------------------------
    # 4. Automated FloodWait Backoff Protocol
    # --------------------------------------------------------------------------
    def is_frozen_by_flood(self) -> Tuple[bool, float]:
        now = time.time()
        if now < self._flood_freeze_until:
            wait_remaining = self._flood_freeze_until - now
            return True, wait_remaining
        return False, 0.0

    async def handle_flood_wait(self, flood_seconds: float) -> None:
        """
        Applies a 1.5x safety margin backoff to completely heal Telegram rate limit blocks.
        """
        safety_backoff = flood_seconds * 1.5
        self._flood_freeze_until = time.time() + safety_backoff
        logger.critical(
            f"🚨 Telegram FloodWait triggered ({flood_seconds}s). "
            f"Stealth Shield freezing all outgoing actions for {safety_backoff:.1f}s."
        )
        await asyncio.sleep(safety_backoff)
        logger.info("✅ FloodWait safety cooldown expired. Resuming normal living userbot operations.")


# Global Singleton Instance
stealth_anti_ban = StealthAntiBanShield()

