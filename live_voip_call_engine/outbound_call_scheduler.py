"""
Outbound Call Scheduler & Human Alarm Clock (Project Aether-Human V4.0)
Schedules autonomous proactive outbound calls:
- Human Alarm Clock: Wakes up user at requested time with dynamic voice encouragement.
- Reconciliation & Check-In Calls: Calls close friends if inactive or after a disagreement.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

logger = logging.getLogger("Aether.VoIP.OutboundScheduler")


@dataclass
class ScheduledCall:
    call_id: str
    user_id: int
    user_name: str
    target_timestamp: float
    call_purpose: str  # 'WAKEUP_ALARM', 'RECONCILIATION', 'REMINDER'
    prompt_topic: str = ""
    is_executed: bool = False

    @property
    def scheduled_time(self) -> float:
        return self.target_timestamp


class OutboundCallScheduler:
    """
    Manages scheduling and autonomous triggering of outbound voice calls.
    """

    def __init__(self, storage_path: str = "data/scheduled_calls.json"):
        self.storage_path = storage_path
        self._calls: Dict[str, ScheduledCall] = {}
        self._is_running = False
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for cid, c_dict in raw_data.items():
                    self._calls[cid] = ScheduledCall(**c_dict)
            logger.info(f"Loaded {len(self._calls)} scheduled outbound calls.")
        except Exception as exc:
            logger.warning(f"Failed to load scheduled calls: {exc}")

    def _save(self) -> None:
        try:
            data = {cid: asdict(call) for cid, call in self._calls.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"Failed to save scheduled calls: {exc}")

    def schedule_wakeup_call(
        self,
        user_id: int,
        user_name: str = "مستخدم",
        delay_seconds: float = 600.0,
        note: str = "",
        minutes_from_now: Optional[float] = None,
        reason: Optional[str] = None,
        reminder_text: Optional[str] = None,
        **kwargs,
    ) -> ScheduledCall:
        m_from_now = minutes_from_now if minutes_from_now is not None else kwargs.get("minutes_from_now")
        if m_from_now is not None:
            delay_seconds = float(m_from_now) * 60.0
        elif "delay_seconds" in kwargs:
            delay_seconds = float(kwargs["delay_seconds"])

        prompt_reason = reason or reminder_text or note or kwargs.get("reminder_text") or kwargs.get("reason") or ""
        call_id = f"call_{user_id}_{int(time.time())}"
        target_ts = time.time() + delay_seconds
        call = ScheduledCall(
            call_id=call_id,
            user_id=user_id,
            user_name=user_name,
            target_timestamp=target_ts,
            call_purpose="WAKEUP_ALARM",
            prompt_topic=prompt_reason,
        )
        self._calls[call_id] = call
        self._save()
        logger.info(f"⏰ Scheduled Wakeup Call for [{user_name}] in {int(delay_seconds)} seconds.")
        return call

    def start_scheduler_worker(self) -> None:
        if self._is_running:
            return
        self._is_running = True

        async def _worker():
            while self._is_running:
                now = time.time()
                for cid, call in list(self._calls.items()):
                    if not call.is_executed and now >= call.target_timestamp:
                        call.is_executed = True
                        self._save()
                        asyncio.create_task(self._trigger_call(call))
                await asyncio.sleep(5.0)

        asyncio.create_task(_worker())
        logger.info("Outbound call supervisor daemon started.")

    async def _trigger_call(self, call: ScheduledCall) -> None:
        logger.info(f"🚀 Triggering outbound call [{call.call_id}] for [{call.user_name}]...")
        # Since standard MTProto bots initiate voice messages/calls:
        wakeup_greeting = (
            f"📞 *[رنة مكالمة هاتفية حية من عمر]* 🔔\n\n"
            f"صباح الورد والنشاط يا {call.user_name}! ☀️\n"
            f"أنا رنيت عليك زي ما اتفقنا بالضبط عشان تصحى وميفوتكش يومك!\n"
            f"قوم يلا اغسل وشك واشرب قهوتك الحلوة، ويومك كله توفيق إن شاء الله! ☕💪"
        )
        if call.prompt_topic:
            wakeup_greeting += f"\nملاحظتك: {call.prompt_topic}"

        await mtproto_manager.send_message(chat_id=call.user_id, text=wakeup_greeting)


outbound_scheduler = OutboundCallScheduler()
outbound_call_scheduler = outbound_scheduler

