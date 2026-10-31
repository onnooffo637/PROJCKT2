"""
Telegram MTProto Client and Bot API Manager for Project Aether-Human.
Handles real-time message reception, read receipts, human typing presence,
reactions, voice notes, photos, and burst dispatching.
Supports both Telegram Bot API Polling (via BOT_TOKEN) and MTProto Userbot Client (Telethon).
"""

from __future__ import annotations

import logging
import asyncio
import os
import random
import time
from typing import Optional, List, Any, Dict
import httpx
from telethon import TelegramClient, events
from telethon.tl.types import (
    DocumentAttributeAudio,
    ReactionEmoji,
)

from aether_human_core.config.settings import settings
from aether_human_core.telegram_client.human_typer import BurstMessage, human_typer

logger = logging.getLogger("Aether.Telegram.MTProto")


class TelegramMTProtoManager:
    """
    Manages Telegram communication with authentic human UX timings.
    Supports official Bot API long-polling and Telethon MTProto userbot.
    """
    def __init__(self):
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        self.bot_token = settings.telegram_bot_token
        self.session_name = settings.telegram_session_name
        self.client: Optional[TelegramClient] = None
        self._is_running: bool = False
        self._mock_mode: bool = False
        self._bot_polling_task: Optional[asyncio.Task] = None
        self._last_update_id: int = 0
        self.bot_api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        self._http_client: Optional[httpx.AsyncClient] = None
        self._user_last_button_click: Dict[int, float] = {}
        self._user_media_cooldown: Dict[Tuple[int, str], float] = {}

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=40.0)
        return self._http_client

    async def initialize(self) -> None:
        """
        Initializes Telegram connectivity:
        1. If TELEGRAM_BOT_TOKEN is provided: launches real-time Telegram Bot API long-polling.
        2. If MTProto Userbot is configured & authorized: hooks Telethon event handlers.
        3. If neither: runs in Simulation / Sandbox mode.
        """
        if self.bot_token:
            # Active Telegram Bot mode via official Telegram Bot API
            try:
                http = await self._get_http()
                res = await http.get(f"{self.bot_api_url}/getMe")
                if res.status_code == 200 and res.json().get("ok"):
                    bot_info = res.json()["result"]
                    self.bot_id = bot_info.get("id")
                    self.bot_username = bot_info.get("username", "omarggforbot").lower()
                    logger.info(
                        f"🚀 Telegram Bot authenticated successfully! "
                        f"Username: @{self.bot_username} | Name: '{bot_info.get('first_name')}'"
                    )
                    self._is_running = True
                    self._mock_mode = False
                    # Start polling background daemon
                    self._bot_polling_task = asyncio.create_task(self._start_bot_polling())
                    return
                else:
                    logger.warning(f"Telegram Bot Token check returned {res.status_code}: {res.text}")
            except Exception as exc:
                logger.error(f"Failed to verify Telegram Bot Token: {exc}")

        # Fallback to Telethon MTProto Userbot
        if self.api_id and self.api_hash and self.api_id != 0:
            try:
                self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
                await self.client.connect()
                if await self.client.is_user_authorized():
                    logger.info("Telethon MTProto client connected and authorized as Userbot.")
                    self._is_running = True
                    self._mock_mode = False
                    self._register_telethon_handlers()
                    return
                elif self.bot_token:
                    await self.client.start(bot_token=self.bot_token)
                    logger.info("Telethon connected using Bot Token fallback.")
                    self._is_running = True
                    self._mock_mode = False
                    self._register_telethon_handlers()
                    return
                else:
                    logger.warning("Telegram Userbot not authorized. Authorization required via phone.")
            except Exception as exc:
                logger.error(f"Failed to start MTProto client: {exc}")

        logger.warning("Operating Telegram Manager in Simulation/Sandbox mode.")
        self._mock_mode = True
        self._is_running = True

    async def _start_bot_polling(self) -> None:
        """
        Long-polling loop receiving incoming Telegram messages and routing to cognitive handlers.
        """
        logger.info("Listening for real-time Telegram messages (Long-Polling Active)...")
        http = await self._get_http()

        # Advance past historical unhandled updates to start fresh or process recent
        try:
            init_res = await http.get(f"{self.bot_api_url}/getUpdates", params={"limit": 100})
            if init_res.status_code == 200:
                results = init_res.json().get("result", [])
                if results:
                    # Catch up with unread messages concurrently
                    logger.info(f"Processing {len(results)} pending incoming message(s) from Telegram...")
                    for u in results:
                        self._last_update_id = u["update_id"]
                        asyncio.create_task(self._process_telegram_update_safe(u))
        except Exception as exc:
            logger.warning(f"Error fetching initial update batch: {exc}")

        while self._is_running:
            try:
                params = {"timeout": 25, "offset": self._last_update_id + 1}
                res = await http.get(f"{self.bot_api_url}/getUpdates", params=params, timeout=35.0)
                if res.status_code == 200:
                    data = res.json()
                    for update in data.get("result", []):
                        self._last_update_id = update["update_id"]
                        # Process each update in an independent concurrent task!
                        # Guarantees buttons and messages never block or hang each other.
                        asyncio.create_task(self._process_telegram_update_safe(update))
                elif res.status_code == 409:
                    logger.warning("Telegram Bot conflict: another instance might be polling. Waiting 5s...")
                    await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"Polling network exception: {exc}")
                await asyncio.sleep(2.0)

    async def _process_telegram_update_safe(self, update: Dict[str, Any]) -> None:
        """
        Safely executes an update handler in a detached background task without crashing polling.
        """
        try:
            await self._process_telegram_update(update)
        except Exception as exc:
            logger.error(f"Error handling Telegram update: {exc}", exc_info=True)

    async def _process_telegram_update(self, update: Dict[str, Any]) -> None:
        """
        Parses incoming Telegram event and delegates to appropriate domain handler.
        """
        # Intercept Callback Queries (Inline Button Clicks)
        if "callback_query" in update:
            await self._process_callback_query(update["callback_query"])
            return

        msg = update.get("message")
        if not msg:
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "private")
        message_id = msg.get("message_id")
        sender = msg.get("from", {})
        sender_id = sender.get("id", chat_id)
        sender_name = sender.get("first_name", "صديق")
        message_text = msg.get("text", "") or msg.get("caption", "")

        # Command interception (/start, /menu, /panel, /stats, /mood, /admins, /rules, /dialects, /media, /add_admin, /del_admin, /add_rule, /del_rule, /ban_word, /unban_word)
        if message_text.startswith("/"):
            handled_cmd = await self._handle_command(
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                message_text=message_text,
                reply_to_msg_id=message_id,
            )
            if handled_cmd:
                return

        # Guess gender from first name heuristics or default unknown
        name_lower = sender_name.lower().strip()
        common_female = ("سارة", "نورا", "مريم", "آية", "فاطمة", "حبيبتي", "ياسمين", "سلمى", "هدى", "رنا", "دينا", "منى", "مي", "نور")
        common_male = ("محمد", "أحمد", "مصطفى", "يوسف", "علي", "محمود", "عمر", "كريم", "حسن", "حسين", "خالد", "طارق", "هيثم", "سيف", "إسلام", "إبراهيم", "عمرو", "زياد", "فارس", "معاذ", "عبد", "mustafa", "mohamed", "ahmed", "youssef", "marcel", "v7x", "joo")
        if any(f in name_lower for f in common_female):
            sender_gender = "female"
        elif any(m in name_lower for m in common_male):
            sender_gender = "male"
        else:
            sender_gender = "unknown"

        logger.info(f"📩 [Telegram Message] From [{sender_name} ({sender_id})]: '{message_text[:40]}...'")

        # Import handlers locally to prevent circular imports
        from aether_human_core.telegram_client.handlers.dm_handler import dm_handler
        from aether_human_core.telegram_client.handlers.group_handler import group_handler
        from aether_human_core.telegram_client.handlers.media_handler import media_handler

        # 1. Voice note detection
        if msg.get("voice") or msg.get("audio"):
            file_id = (msg.get("voice") or msg.get("audio"))["file_id"]
            http = await self._get_http()
            file_info = await http.get(f"{self.bot_api_url}/getFile", params={"file_id": file_id})
            if file_info.status_code == 200:
                file_path_tg = file_info.json()["result"]["file_path"]
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path_tg}"
                dl_res = await http.get(download_url)
                if dl_res.status_code == 200:
                    local_voice = os.path.join(os.getcwd(), "artifacts", "voice_notes", f"incoming_{file_id}.ogg")
                    with open(local_voice, "wb") as f:
                        f.write(dl_res.content)
                    await media_handler.handle_incoming_voice(
                        message_id=message_id,
                        chat_id=chat_id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        voice_file_path=local_voice,
                    )
                    return

        # 2. Photo request detection
        handled_photo = await media_handler.handle_photo_request(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
        )
        if handled_photo:
            return

        # 3. Voice note request detection
        handled_voice = await media_handler.handle_voice_request(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
        )
        if handled_voice:
            return

        # 3. Private DM handling
        if chat_type == "private":
            await dm_handler.handle_dm_message(
                message_id=message_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_gender=sender_gender,
                message_text=message_text,
            )

        # 4. Group handling
        elif chat_type in ("group", "supergroup"):
            chat_title = chat.get("title", "جروب عام")
            reply_to = msg.get("reply_to_message", {})
            reply_from = reply_to.get("from", {})
            is_reply = False
            if reply_from:
                is_reply = bool(reply_from.get("id") == getattr(self, "bot_id", 0) or reply_from.get("is_bot"))

            bot_tag = f"@{getattr(self, 'bot_username', 'omarggforbot')}".lower()
            is_tagged = bot_tag in message_text.lower()

            await group_handler.handle_group_message(
                message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_gender=sender_gender,
                message_text=message_text,
                chat_title=chat_title,
                is_reply_to_bot=is_reply,
                is_bot_mentioned=is_tagged,
            )

    def _register_telethon_handlers(self) -> None:
        """
        Registers event handlers on active Telethon client.
        """
        if not self.client:
            return

        @self.client.on(events.NewMessage(incoming=True))
        async def on_new_message(event):
            sender = await event.get_sender()
            sender_id = event.sender_id
            sender_name = getattr(sender, "first_name", "صديق") or "صديق"
            sender_gender = "female" if sender_name in ("سارة", "نورا", "حبيبتي") else "unknown"
            msg_text = event.raw_text

            from aether_human_core.telegram_client.handlers.dm_handler import dm_handler
            from aether_human_core.telegram_client.handlers.group_handler import group_handler
            from aether_human_core.telegram_client.handlers.media_handler import media_handler

            if event.is_private:
                # Check photo request
                is_photo_req = await media_handler.handle_photo_request(
                    message_id=event.id,
                    chat_id=sender_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=msg_text,
                )
                if is_photo_req:
                    return

                # Check voice note request
                is_voice_req = await media_handler.handle_voice_request(
                    message_id=event.id,
                    chat_id=sender_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=msg_text,
                )
                if is_voice_req:
                    return

                await dm_handler.handle_dm_message(
                    message_id=event.id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_gender=sender_gender,
                    message_text=msg_text,
                )
            elif event.is_group:
                chat = await event.get_chat()
                title = getattr(chat, "title", "جروب عام")
                await group_handler.handle_group_message(
                    message_id=event.id,
                    chat_id=event.chat_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_gender=sender_gender,
                    message_text=msg_text,
                    chat_title=title,
                    is_reply_to_bot=event.is_reply,
                    is_bot_mentioned="عمر" in msg_text,
                )

    async def send_typing_indicator(self, chat_id: int, duration_sec: float) -> None:
        """
        Broadcasts human typing indicator.
        """
        if self._mock_mode:
            logger.debug(f"[Simulation] Typing in chat {chat_id} for {duration_sec}s...")
            await asyncio.sleep(min(duration_sec, 2.0))
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                )
                await asyncio.sleep(min(duration_sec, 0.8))
            except Exception as exc:
                logger.debug(f"Typing action exception: {exc}")
        elif self.client:
            try:
                async with self.client.action(chat_id, "typing"):
                    await asyncio.sleep(min(duration_sec, 0.8))
            except Exception as exc:
                logger.debug(f"Telethon typing action exception: {exc}")

    async def mark_seen(self, chat_id: int, max_id: int, delay_sec: float = 2.0) -> None:
        """
        Simulates delayed read receipt (Seen).
        """
        await asyncio.sleep(delay_sec)
        logger.debug(f"Simulated read receipt in chat [{chat_id}] (Msg ID: {max_id}).")

    async def send_reaction(self, chat_id: int, message_id: int, emoji: str) -> None:
        """
        Attaches emoji reaction to a message.
        """
        if self._mock_mode:
            logger.info(f"[Simulation] Reacted with '{emoji}' to msg {message_id} in chat {chat_id}.")
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/setMessageReaction",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reaction": [{"type": "emoji", "emoji": emoji}],
                    },
                )
                logger.info(f"Attached reaction '{emoji}' to message [{message_id}] in chat [{chat_id}].")
            except Exception as exc:
                logger.debug(f"Bot reaction not supported or chat too restricted: {exc}")
        elif self.client:
            try:
                from telethon.tl.functions.messages import SendReactionRequest
                await self.client(
                    SendReactionRequest(
                        peer=chat_id,
                        msg_id=message_id,
                        reaction=[ReactionEmoji(emoticon=emoji)],
                    )
                )
            except Exception as exc:
                logger.debug(f"Telethon reaction exception: {exc}")

    async def _process_callback_query(self, cb: Dict[str, Any]) -> None:
        """
        Handles interactive inline button clicks from Telegram menus with instant sub-second response,
        anti-spam debounce, and media request rate-limiting.
        """
        query_id = cb.get("id")
        from_user = cb.get("from", {})
        user_id = from_user.get("id", 0)
        user_name = from_user.get("first_name", "صديق")
        data = cb.get("data", "")
        msg = cb.get("message", {})
        chat_id = msg.get("chat", {}).get("id", user_id)
        message_id = msg.get("message_id")

        now = time.time()
        http = await self._get_http() if self.bot_token else None

        # 1. Anti-Double-Click Debounce:
        # Prevents accidental double-taps (< 0.4s) from executing duplicate logic
        last_click = self._user_last_button_click.get(user_id, 0.0)
        if now - last_click < 0.4:
            if http:
                try:
                    await http.post(f"{self.bot_api_url}/answerCallbackQuery", json={"callback_query_id": query_id})
                except Exception:
                    pass
            return
        self._user_last_button_click[user_id] = now

        # 2. Strict Rate-Limit & Cooldown on Media Buttons (Photo & Voice):
        # Prevents users from spamming 5,000 photos or voice notes in rapid succession
        if data in ("act:send_photo", "act:send_voice"):
            last_media_time = self._user_media_cooldown.get((user_id, data), 0.0)
            MEDIA_COOLDOWN_SEC = 15.0  # 15s cooldown
            remaining = int(MEDIA_COOLDOWN_SEC - (now - last_media_time))
            if remaining > 0:
                if http:
                    try:
                        ans_payload = {
                            "callback_query_id": query_id,
                            "text": f"⏳ استنى {remaining} ثانية يا غالي قبل ما تطلب ميديا تانية علشان السيرفر يلاحق!",
                            "show_alert": True,
                        }
                        await http.post(f"{self.bot_api_url}/answerCallbackQuery", json=ans_payload)
                    except Exception:
                        pass
                return
            self._user_media_cooldown[(user_id, data)] = now

        from aether_human_core.telegram_client.telegram_menu import telegram_menu
        text, markup, alert, trigger = await telegram_menu.handle_callback(data, user_id, user_name)

        # 3. Answer callback query IMMEDIATELY so buttons never spin or hang
        if http:
            ans_payload: Dict[str, Any] = {"callback_query_id": query_id}
            if alert:
                ans_payload["text"] = alert
                ans_payload["show_alert"] = True if ("استنى" in alert or "كورتيزول" in alert or "قهوة" in alert or "جاري" in alert) else False
            try:
                await http.post(f"{self.bot_api_url}/answerCallbackQuery", json=ans_payload)
            except Exception as exc:
                logger.debug(f"answerCallbackQuery error: {exc}")

        # 4. Update message content immediately
        if text and message_id and http:
            try:
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": markup or {},
                }
                res = await http.post(f"{self.bot_api_url}/editMessageText", json=edit_payload)
                if res.status_code != 200:
                    edit_payload.pop("parse_mode", None)
                    await http.post(f"{self.bot_api_url}/editMessageText", json=edit_payload)
            except Exception as exc:
                logger.debug(f"editMessageText error: {exc}")

        # 5. Execute action triggers in a DECOUPLED background task
        # Generates photo/voice without blocking button responses or polling loop!
        if trigger == "send_voice":
            from aether_human_core.telegram_client.handlers.media_handler import media_handler
            asyncio.create_task(
                media_handler.handle_voice_request(
                    message_id=message_id,
                    chat_id=chat_id,
                    sender_id=user_id,
                    sender_name=user_name,
                    message_text="ابعتلي فويس ضروري يا عمر",
                )
            )
        elif trigger == "send_photo":
            from aether_human_core.telegram_client.handlers.media_handler import media_handler
            asyncio.create_task(
                media_handler.handle_photo_request(
                    message_id=message_id,
                    chat_id=chat_id,
                    sender_id=user_id,
                    sender_name=user_name,
                    message_text="ابعتلي صورتك سيلفي دلوقتي يا عمر",
                )
            )

    async def _handle_command(
        self,
        chat_id: int,
        sender_id: int,
        sender_name: str,
        message_text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> bool:
        """
        Dispatches slash commands (/menu, /stats, /mood, /admins, /rules, /add_admin, /ban_word, etc.)
        """
        from aether_human_core.telegram_client.telegram_menu import telegram_menu
        from aether_human_core.psychology_engine.admin_manager import admin_manager
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        parts = message_text.strip().split()
        if not parts:
            return False
        cmd = parts[0].lower().split("@")[0]

        if cmd in ("/start", "/menu", "/panel", "/control"):
            text, markup = await telegram_menu.render_main_dashboard(sender_id, user_name=sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/affinity", "/me", "/profile", "/xp", "/rank"):
            text, markup = await telegram_menu.render_user_affinity_profile(sender_id, user_name=sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/stats", "/server", "/system"):
            text, markup = await telegram_menu.render_server_stats()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/mood", "/radar", "/hormones"):
            text, markup = await telegram_menu.render_mood_radar()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/admins", "/roles"):
            text, markup = await telegram_menu.render_admins_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/rules", "/laws"):
            text, markup = await telegram_menu.render_rules_panel()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/dialects", "/languages", "/accents"):
            text, markup = await telegram_menu.render_dialects_info()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/media", "/test_media"):
            text, markup = await telegram_menu.render_media_center()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/villain", "/set_villain", "/شرير"):
            if not await admin_manager.is_admin(sender_id):
                refusal = "🚫 <b>عفواً:</b> صلاحية تعيين الشرير محصورة للأدمنز ومالك النظام فقط."
                await self.send_message_with_keyboard(chat_id, refusal, {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                help_msg = (
                    "🦹 <b>تعيين شخص كـ «شرير رسمي»:</b>\n"
                    "<code>/villain &lt;user_id&gt;</code>\n"
                    "<i>يقلب رصيد الشخص فوراً بالسالب (-75.0)، وعمر هيعامله كعدو ويسخر منه ويحرمه من الميديا!</i>"
                )
                await self.send_message_with_keyboard(chat_id, help_msg, {}, reply_to_msg_id)
                return True
            try:
                target_id = int(parts[1])
                ok, msg = await admin_manager.set_user_villain(operator_id=sender_id, target_id=target_id)
                resp = f"🦹 <b>إدارة الأشرار والخصوم:</b>\n<blockquote>{msg}</blockquote>"
                await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            except ValueError:
                await self.send_message_with_keyboard(chat_id, "⚠️ اكتب الأيدي بالأرقام يا غالي: <code>/villain 123456789</code>", {}, reply_to_msg_id)
            return True

        elif cmd in ("/add_admin", "/promote", "/set_role", "/رتبة"):
            if not await admin_manager.is_admin(sender_id):
                refusal = "🚫 <b>عفواً يا غالي:</b>\n<blockquote>هذا الأمر مخصص لأصحاب الرتب الإدارية العليا والسوبر أدمن فقط 🛡️</blockquote>"
                await self.send_message_with_keyboard(chat_id, refusal, {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                help_msg = (
                    "ℹ️ <b>طريقة تعيين وتغيير الرتب:</b>\n"
                    "<code>/promote &lt;user_id&gt; &lt;ROLE&gt;</code>\n\n"
                    "👑 <b>الرتب المتاحة:</b>\n"
                    "• <code>ADMIN</code>: مسؤول معتمد\n"
                    "• <code>MODERATOR</code>: مشرف الجروب\n"
                    "• <code>VIP</code>: عضو شرف مميز\n"
                    "• <code>FAVORITE</code>: المفضل وشريك الروح (+85)\n"
                    "• <code>WISE</code>: الحكيم وكبير القعدة\n"
                    "• <code>JESTER</code>: الفرفوش وصانع البهجة\n"
                    "• <code>MEMBER</code>: عضو عادي\n"
                    "• <code>COLD</code>: المتجاهل والبارد\n"
                    "• <code>VILLAIN</code>: الشرير والعدو اللدود (-75)"
                )
                await self.send_message_with_keyboard(chat_id, help_msg, {}, reply_to_msg_id)
                return True
            try:
                target_id = int(parts[1])
                target_role = parts[2].upper() if len(parts) > 2 else "ADMIN"
                ok, msg = await admin_manager.promote_user(operator_id=sender_id, target_id=target_id, role=target_role)
                status_icon = "👑" if ok else "⚠️"
                resp = f"{status_icon} <b>إدارة الصلاحيات والرتب:</b>\n<blockquote>{msg}</blockquote>"
                await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            except ValueError:
                await self.send_message_with_keyboard(chat_id, "⚠️ يجب كتابة الـ User ID كأرقام فقط.", {}, reply_to_msg_id)
            return True

        elif cmd == "/del_admin":
            if not await admin_manager.is_admin(sender_id):
                refusal = "🚫 <b>عفواً:</b> هذه الصلاحية للأدمن فقط."
                await self.send_message_with_keyboard(chat_id, refusal, {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/del_admin &lt;user_id&gt;</code>", {}, reply_to_msg_id)
                return True
            try:
                target_id = int(parts[1])
                ok, msg = await admin_manager.demote_user(target_id, assigned_by=sender_id)
                resp = f"🛡️ <b>تعديل الصلاحيات:</b>\n<blockquote>{msg}</blockquote>"
                await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            except ValueError:
                await self.send_message_with_keyboard(chat_id, "⚠️ يجب كتابة الـ User ID كأرقام فقط.", {}, reply_to_msg_id)
            return True

        elif cmd == "/add_rule":
            if not await admin_manager.is_admin(sender_id):
                await self.send_message_with_keyboard(chat_id, "🚫 عذراً، إضافة القواعد مقتصرة على الأدمنز.", {}, reply_to_msg_id)
                return True
            rule_text = message_text[len(parts[0]):].strip()
            if not rule_text:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/add_rule نص القاعدة الجديدة هنا</code>", {}, reply_to_msg_id)
                return True
            ok, msg = await admin_manager.add_dynamic_rule(operator_id=sender_id, instruction_text=rule_text, rule_type="RESTRICTION")
            resp = (
                f"📜 <b>تم اعتماد وتثبيت القاعدة الجديدة في عقل عمر:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<blockquote>{rule_text}</blockquote>\n"
                f"<i>محفوظة بصفة دائمة في قاعدة البيانات ولن تُمسح مع أي إعادة تشغيل.</i>"
            )
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        elif cmd == "/del_rule":
            if not await admin_manager.is_admin(sender_id):
                await self.send_message_with_keyboard(chat_id, "🚫 عذراً، حذف القواعد مقتصر على الأدمنز.", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/del_rule &lt;rule_id&gt;</code>", {}, reply_to_msg_id)
                return True
            try:
                target_rule_id = int(parts[1])
                ok, msg = await admin_manager.delete_dynamic_rule(operator_id=sender_id, rule_id=target_rule_id)
                await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            except ValueError:
                await self.send_message_with_keyboard(chat_id, "⚠️ يجب كتابة رقم القاعدة كأرقام (مثال: /del_rule 1).", {}, reply_to_msg_id)
            return True

        elif cmd in ("/ban_word", "/block_word"):
            if not await admin_manager.is_admin(sender_id):
                await self.send_message_with_keyboard(chat_id, "🚫 عذراً، حظر الكلمات مقتصر على الأدمنز.", {}, reply_to_msg_id)
                return True
            word_to_ban = message_text[len(parts[0]):].strip()
            if not word_to_ban:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/ban_word الكلمة</code>", {}, reply_to_msg_id)
                return True
            anti_toxicity.add_banned_word(word_to_ban)
            await admin_manager.add_dynamic_rule(
                operator_id=sender_id,
                instruction_text=f"ممنوع استخدام كلمة: {word_to_ban}",
                rule_type="PROHIBITION",
            )
            resp = f"🛡️ <b>تم حظر الكلمة فوراً:</b>\n<blockquote>تم إدراج «{word_to_ban}» في القائمة السوداء الفورية وممنوع التلفظ بها نهائياً.</blockquote>"
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        elif cmd in ("/unban_word"):
            if not await admin_manager.is_admin(sender_id):
                await self.send_message_with_keyboard(chat_id, "🚫 عذراً، مقتصر على الأدمنز.", {}, reply_to_msg_id)
                return True
            word = message_text[len(parts[0]):].strip()
            removed = anti_toxicity.remove_banned_word(word)
            msg = f"✅ تم رفع الحظر عن «{word}»." if removed else f"⚠️ الكلمة «{word}» لم تكن في قائمة الحظر الخاصة."
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        return False

    async def send_message_with_keyboard(
        self,
        chat_id: int,
        text: str,
        reply_markup: Dict[str, Any],
        reply_to_msg_id: Optional[int] = None,
    ) -> None:
        """
        Sends formatted message with inline keyboard markup and anti-ban throttling.
        """
        from aether_human_core.config.anti_ban_shield import anti_ban_shield
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        await anti_ban_shield.wait_for_telegram_slot(chat_id)
        text = anti_toxicity.sanitize_outgoing_speech(text)

        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Outgoing Menu] Chat {chat_id} -> '{text[:60]}...'")
            return

        if self.bot_token:
            http = await self._get_http()
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            }
            if reply_to_msg_id:
                payload["reply_to_message_id"] = reply_to_msg_id
            try:
                res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                if res.status_code != 200:
                    payload.pop("parse_mode", None)
                    await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
            except Exception as exc:
                logger.error(f"Error sending message with keyboard via Bot API: {exc}")
        elif self.client:
            try:
                await self.client.send_message(chat_id, text, reply_to=reply_to_msg_id)
            except Exception as exc:
                logger.error(f"Error sending message with keyboard via Telethon: {exc}")

    async def dispatch_burst_messages(
        self,
        chat_id: int,
        bursts: List[BurstMessage],
        reply_to_msg_id: Optional[int] = None,
    ) -> None:
        """
        Sends sequential message bubbles with realistic typing latencies and typo self-corrections.
        Protected by Anti-Ban Flood Token Bucket and Anti-Toxicity Outgoing Speech Sanitizer.
        """
        http = await self._get_http() if self.bot_token else None
        from aether_human_core.config.anti_ban_shield import anti_ban_shield
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        for i, burst in enumerate(bursts):
            # Enforce Telegram Anti-Ban Token-Bucket & per-chat rate limits
            await anti_ban_shield.wait_for_telegram_slot(chat_id)

            # Strictly sanitize outgoing text - ZERO PROFANITY GUARANTEE
            burst.text = anti_toxicity.sanitize_outgoing_speech(burst.text)
            if burst.correction_text:
                burst.correction_text = anti_toxicity.sanitize_outgoing_speech(burst.correction_text)

            # 1. Simulate human typing latency
            await self.send_typing_indicator(chat_id, burst.typing_delay_sec)

            # 2. Transmit message bubble
            reply_target = reply_to_msg_id if i == 0 else None

            if self._mock_mode or (not self.bot_token and not self.client):
                logger.info(f"[Simulation Outgoing] Chat {chat_id} -> '{burst.text}'")
            elif self.bot_token and http:
                try:
                    payload: Dict[str, Any] = {
                        "chat_id": chat_id,
                        "text": burst.text,
                        "parse_mode": "HTML",
                    }
                    if reply_target:
                        payload["reply_to_message_id"] = reply_target
                    res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                    if res.status_code == 200:
                        logger.info(f"📤 [Telegram Sent] Chat [{chat_id}]: '{burst.text}'")
                    else:
                        # Fallback without parse_mode if entity formatting error
                        payload.pop("parse_mode", None)
                        fallback_res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                        if fallback_res.status_code == 200:
                            logger.info(f"📤 [Telegram Sent Fallback] Chat [{chat_id}]: '{burst.text}'")
                        else:
                            logger.warning(f"Failed to send message: {fallback_res.text}")
                except Exception as exc:
                    logger.error(f"Error dispatching burst message via Bot API: {exc}")
            elif self.client:
                try:
                    await self.client.send_message(chat_id, burst.text, reply_to=reply_target)
                except Exception as exc:
                    logger.error(f"Failed to send burst message via Telethon: {exc}")

            # 3. Handle typo self-correction
            if burst.has_typo and burst.correction_text:
                await asyncio.sleep(random.uniform(0.4, 0.8))
                if self.bot_token and http:
                    try:
                        await http.post(
                            f"{self.bot_api_url}/sendMessage",
                            json={"chat_id": chat_id, "text": burst.correction_text},
                        )
                        logger.info(f"📤 [Typo Self-Correction] Chat [{chat_id}]: '{burst.correction_text}'")
                    except Exception:
                        pass
                elif self.client:
                    try:
                        await self.client.send_message(chat_id, burst.correction_text)
                    except Exception:
                        pass

            # Snappy micro-pause between bubbles
            if i < len(bursts) - 1:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def send_voice_note(
        self,
        chat_id: int,
        file_path: str,
        waveform: bytes,
        reply_to_msg_id: Optional[int] = None,
    ) -> None:
        """
        Sends audio note as native Telegram voice note.
        """
        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Outgoing Voice] Chat {chat_id} -> File: {file_path}")
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "record_voice"},
                )
                await asyncio.sleep(1.5)

                mime_type = "audio/ogg" if file_path.endswith(".ogg") else "audio/mpeg"
                with open(file_path, "rb") as f:
                    files = {"voice": (os.path.basename(file_path), f, mime_type)}
                    data: Dict[str, Any] = {"chat_id": str(chat_id)}
                    if reply_to_msg_id:
                        data["reply_to_message_id"] = str(reply_to_msg_id)
                    res = await http.post(f"{self.bot_api_url}/sendVoice", data=data, files=files)
                    if res.status_code == 200:
                        logger.info(f"🎙️ [Voice Sent] Dispatched native Egyptian voice note to chat [{chat_id}].")
                    else:
                        logger.warning(f"Failed to send voice note: {res.text}")
            except Exception as exc:
                logger.error(f"Error sending voice note via Bot API: {exc}")

        elif self.client:
            try:
                async with self.client.action(chat_id, "record-audio"):
                    await asyncio.sleep(2.0)
                await self.client.send_file(
                    chat_id,
                    file_path,
                    voice_note=True,
                    reply_to=reply_to_msg_id,
                    attributes=[DocumentAttributeAudio(voice=True, waveform=waveform, duration=5)],
                )
                logger.info(f"Dispatched native voice note via Telethon to [{chat_id}].")
            except Exception as exc:
                logger.error(f"Error sending voice note via Telethon: {exc}")

    async def send_photo(
        self,
        chat_id: int,
        photo_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> None:
        """
        Sends selfie or photo with caption.
        """
        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Outgoing Photo] Chat {chat_id} -> {photo_path} (Caption: '{caption}')")
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "upload_photo"},
                )
                await asyncio.sleep(1.2)

                with open(photo_path, "rb") as f:
                    files = {"photo": (os.path.basename(photo_path), f, "image/jpeg")}
                    data: Dict[str, Any] = {"chat_id": str(chat_id), "caption": caption or ""}
                    if reply_to_msg_id:
                        data["reply_to_message_id"] = str(reply_to_msg_id)
                    res = await http.post(f"{self.bot_api_url}/sendPhoto", data=data, files=files)
                    if res.status_code == 200:
                        logger.info(f"📸 [Photo Sent] Dispatched real photographic selfie to chat [{chat_id}].")
                    else:
                        logger.warning(f"Failed to send photo: {res.text}")
            except Exception as exc:
                logger.error(f"Error sending photo via Bot API: {exc}")

        elif self.client:
            try:
                async with self.client.action(chat_id, "photo"):
                    await asyncio.sleep(2.0)
                await self.client.send_file(
                    chat_id,
                    photo_path,
                    caption=caption or "",
                    reply_to=reply_to_msg_id,
                )
                logger.info(f"Dispatched photo via Telethon to chat [{chat_id}].")
            except Exception as exc:
                logger.error(f"Error sending photo via Telethon: {exc}")

    async def close(self) -> None:
        self._is_running = False
        if self._bot_polling_task and not self._bot_polling_task.done():
            self._bot_polling_task.cancel()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        if self.client and not self._mock_mode:
            await self.client.disconnect()
            logger.info("Telegram client disconnected.")


mtproto_manager = TelegramMTProtoManager()
