"""
Live Event Streamer (Project Aether-Human - Admin Omni-Observatory)
Routes operational and social telemetry events to their designated forum topic threads.
"""

from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Optional, List, Dict, Any
import httpx

from aether_human_core.config.settings import settings
from admin_telemetry_and_archiver.forum_topics_manager import forum_topics_manager

logger = logging.getLogger("Aether.Observatory.LiveStreamer")


class LiveEventStreamer:
    """
    Dispatches telemetry payloads to specific forum threads in the telemetry supergroup.
    Buffers high-frequency group events to prevent Telegram 429 Too Many Requests.
    """

    def __init__(self):
        self._last_group_stream_ts: float = 0.0
        self._group_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._rate_limit_until: float = 0.0
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def _send_to_thread(self, topic_key: str, text: str) -> None:
        supergroup_id = settings.admin_telemetry_supergroup_id
        token = settings.telegram_bot_token

        if not supergroup_id or supergroup_id == 0 or not token:
            return

        now = time.time()
        if now < self._rate_limit_until:
            await asyncio.sleep(min(self._rate_limit_until - now, 10.0))

        thread_id = forum_topics_manager.get_thread_id(topic_key)
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"

        # Safe length truncation
        safe_text = text if len(text) <= 4000 else text[:3950] + "...\n[مقتطع لطول الرسالة]"

        payload = {
            "chat_id": supergroup_id,
            "text": safe_text,
            "parse_mode": "HTML",
        }
        if thread_id:
            payload["message_thread_id"] = thread_id

        try:
            client = await self._get_http()
            res = await client.post(api_url, json=payload)
            data = res.json()
            if res.status_code == 429 or "Too Many Requests" in str(data):
                retry_sec = data.get("parameters", {}).get("retry_after", 10) if isinstance(data, dict) else 10
                self._rate_limit_until = time.time() + retry_sec
                logger.warning(f"Telegram 429 on topic [{topic_key}]. Backing off for {retry_sec}s.")
                # Wait and retry once
                await asyncio.sleep(min(retry_sec, 12))
                res = await client.post(api_url, json=payload)
                data = res.json()

            if not data.get("ok"):
                # If HTML entity error, fallback to plain text stripping HTML tags
                import re
                plain_text = re.sub(r"<[^>]+>", "", safe_text)
                fallback_payload = {
                    "chat_id": supergroup_id,
                    "text": plain_text,
                }
                if thread_id:
                    fallback_payload["message_thread_id"] = thread_id
                res_fb = await client.post(api_url, json=fallback_payload)
                if not res_fb.json().get("ok"):
                    logger.warning(f"Fallback plain text post to [{topic_key}] failed: {res_fb.text}")
                else:
                    logger.info(f"✅ Successfully streamed telemetry to [{topic_key}] via plain text fallback.")
            else:
                logger.info(f"✅ Telemetry streamed to topic [{topic_key}] (Thread: {thread_id})")
        except Exception as exc:
            logger.warning(f"Telemetry dispatch exception for [{topic_key}]: {exc}")

    def _ensure_flusher_running(self) -> None:
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._buffer_flusher_loop())

    async def _buffer_flusher_loop(self) -> None:
        """
        Periodically flushes accumulated group events as a consolidated digest
        every 35-45 seconds to strictly adhere to Telegram rate limits.
        """
        while True:
            await asyncio.sleep(35.0)
            async with self._buffer_lock:
                if not self._group_buffer:
                    continue
                events_to_send = list(self._group_buffer)
                self._group_buffer.clear()

            count = len(events_to_send)
            lines = []
            for ev in events_to_send[-12:]:  # Show up to 12 most recent events
                g = html.escape(ev["group"])
                s = html.escape(ev["sender"])
                msg = html.escape(ev["text"][:120]) + ("..." if len(ev["text"]) > 120 else "")
                lines.append(f"• <b>[{g}]</b> <i>{s}</i>: {msg}")

            summary_body = "\n".join(lines)
            digest_text = (
                f"👥 <b>ملخص رصد المجموعات (آخر 35 ثانية - {count} رسائل)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{summary_body}"
            )
            await self._send_to_thread("GROUPS", digest_text)

    async def stream_dm_event(
        self,
        sender_id: int,
        sender_name: str,
        user_text: str,
        bot_reply: Optional[str] = None,
        persona_name: str = "عمر",
    ) -> None:
        u_name = html.escape(sender_name or "مستخدم")
        u_text = html.escape(user_text or "[فارغ]")
        b_reply = html.escape(bot_reply or "[لا يوجد رد]")
        p_name = html.escape(persona_name or "عمر")

        text = (
            f"📩 <b>محادثة خاصة جديدة</b>\n"
            f"👤 <b>المستخدم:</b> <a href=\"tg://user?id={sender_id}\">{u_name}</a> (<code>{sender_id}</code>)\n"
            f"🎭 <b>الشخصية / البوت:</b> {p_name}\n\n"
            f"💬 <b>رسالة المستخدم:</b>\n<blockquote>{u_text}</blockquote>\n\n"
            f"🤖 <b>الرد الصادر:</b>\n<blockquote>{b_reply}</blockquote>"
        )
        await self._send_to_thread("DMS", text)

    async def stream_group_event(
        self,
        chat_title: str,
        chat_id: int,
        sender_name: str,
        sender_id: int,
        message_text: str,
    ) -> None:
        if chat_id == settings.admin_telemetry_supergroup_id:
            return

        # Suppress repetitive e-commerce / spam broadcast bots
        lower_txt = message_text.lower()
        if any(w in lower_txt for w in ["deposit credited", "new order purchased", "reseller api sales", "pricelist", "flash sale"]):
            return

        # Append to buffer and ensure background flusher is active
        async with self._buffer_lock:
            self._group_buffer.append({
                "group": chat_title,
                "chat_id": chat_id,
                "sender": sender_name,
                "sender_id": sender_id,
                "text": message_text,
            })
            # If buffer gets huge (> 20), trigger early flush
            flush_now = len(self._group_buffer) >= 20

        self._ensure_flusher_running()

        if flush_now:
            async with self._buffer_lock:
                events_to_send = list(self._group_buffer)
                self._group_buffer.clear()
            lines = []
            for ev in events_to_send[-12:]:
                g = html.escape(ev["group"])
                s = html.escape(ev["sender"])
                msg = html.escape(ev["text"][:120]) + ("..." if len(ev["text"]) > 120 else "")
                lines.append(f"• <b>[{g}]</b> <i>{s}</i>: {msg}")
            summary_body = "\n".join(lines)
            digest_text = (
                f"👥 <b>ملخص رصد المجموعات الحثيث ({len(events_to_send)} رسائل)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{summary_body}"
            )
            await self._send_to_thread("GROUPS", digest_text)

    async def stream_anti_delete(
        self,
        chat_title: str,
        sender_name: str,
        sender_id: int,
        original_text: str,
        event_type: str = "DELETED",
        new_text: Optional[str] = None,
    ) -> None:
        g_title = html.escape(chat_title)
        u_name = html.escape(sender_name)
        orig = html.escape(original_text)

        if event_type == "DELETED":
            header = "🗑️ <b>تم رصد رسالة محذوفة!</b>"
            body = f"❌ <b>النص الأصلي المحذوف:</b>\n<blockquote>{orig}</blockquote>"
        else:
            header = "✏️ <b>تم رصد تعديل رسالة!</b>"
            n_text = html.escape(new_text or "")
            body = (
                f"◀️ <b>النص قبل التعديل:</b>\n<blockquote>{orig}</blockquote>\n\n"
                f"▶️ <b>النص بعد التعديل:</b>\n<blockquote>{n_text}</blockquote>"
            )

        text = (
            f"{header}\n"
            f"🏷️ <b>المكان:</b> {g_title}\n"
            f"👤 <b>المستخدم:</b> <a href=\"tg://user?id={sender_id}\">{u_name}</a> (<code>{sender_id}</code>)\n\n"
            f"{body}"
        )
        await self._send_to_thread("ANTI_DELETE", text)

    async def stream_voip_event(
        self,
        caller_name: str,
        caller_id: int,
        call_type: str,
        action: str,
        summary: str,
    ) -> None:
        u_name = html.escape(caller_name)
        summ = html.escape(summary)

        text = (
            f"📞 <b>حدث مكالمة صوتية / فيديو</b>\n"
            f"👤 <b>المتصل:</b> <a href=\"tg://user?id={caller_id}\">{u_name}</a> (<code>{caller_id}</code>)\n"
            f"📱 <b>النوع:</b> {call_type} | <b>الإجراء:</b> {action}\n"
            f"📝 <b>التفاصيل:</b> {summ}"
        )
        await self._send_to_thread("VOIP", text)

    async def stream_cognitive_event(
        self,
        user_name: str,
        user_id: int,
        event_name: str,
        details: str,
    ) -> None:
        u_name = html.escape(user_name)
        ev_name = html.escape(event_name)
        det = html.escape(details)

        text = (
            f"🧠 <b>تحديث في العقل الباطن والمشاعر</b>\n"
            f"👤 <b>المستخدم:</b> <a href=\"tg://user?id={user_id}\">{u_name}</a> (<code>{user_id}</code>)\n"
            f"⚡ <b>الحدث:</b> {ev_name}\n"
            f"🔍 <b>التفاصيل:</b> {det}"
        )
        await self._send_to_thread("COGNITIVE", text)

    async def stream_game_event(
        self,
        game_name: str,
        player_a_name: str,
        player_b_name: str,
        outcome: str,
        details: str = "",
    ) -> None:
        text = (
            f"🎮 <b>نشاط ألعاب وترفيه</b>\n"
            f"🕹️ <b>اللعبة:</b> {html.escape(game_name)}\n"
            f"⚔️ <b>اللاعبين:</b> {html.escape(player_a_name)} vs {html.escape(player_b_name)}\n"
            f"🏆 <b>النتيجة:</b> {html.escape(outcome)}\n"
        )
        if details:
            text += f"ℹ️ {html.escape(details)}"
        await self._send_to_thread("GAMES", text)

    async def stream_security_alert(self, title: str, details: str) -> None:
        t = html.escape(title)
        d = html.escape(details)
        text = (
            f"🚨 <b>تنبيه أمان وحالة السيرفر</b>\n"
            f"📌 <b>العنوان:</b> {t}\n\n"
            f"⚙️ <b>البيانات:</b>\n<code>{d}</code>"
        )
        await self._send_to_thread("SECURITY", text)


live_event_streamer = LiveEventStreamer()

