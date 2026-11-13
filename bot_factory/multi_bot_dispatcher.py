"""
Multi-Bot Dynamic Polling Dispatcher for Project Aether-Human (V6.0).
Coordinates autonomous high-concurrency HTTP long-polling loops, one-shot MTProto DC token wake-up
for newly created @BotFather tokens, live Telegram profile synchronization (Name, Bio, Description,
Commands, Global & Per-User WebApp MenuButton), and Group Privacy relay across all factory official bots.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from typing import Dict, Optional, Any, List
import httpx

from bot_factory.models import BotInstanceConfig, BotPlatformType, BotGender
from bot_factory.factory_manager import bot_factory
from aether_human_core.config.settings import settings, CO_ADMIN_ID

logger = logging.getLogger("Aether.BotFactory.Dispatcher")


class MultiBotPollingDispatcher:
    """
    Manages active HTTP long-polling tasks, one-shot MTProto DC token wake-up for newly created tokens,
    live Telegram profile & per-user WebApp MenuButton synchronization, and independent update lifecycles
    for all sub-bots registered in the Bot Factory.
    """

    def __init__(self):
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._is_running: bool = False
        self._http_client: Optional[httpx.AsyncClient] = None
        self._bot_usernames: Dict[str, str] = {}
        self._wake_locks: Dict[str, asyncio.Lock] = {}
        self._pending_admin_actions: Dict[Tuple[int, str], Dict[str, Any]] = {}

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(40.0, connect=10.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            )
        return self._http_client

    def start_dispatcher(self) -> None:
        """
        Scans BotFactory database and launches polling loops for all active official sub-bots.
        """
        if self._is_running:
            return
        self._is_running = True
        logger.info("Initiating Multi-Bot Polling Dispatcher for factory bots...")

        all_bots = bot_factory.list_all_bots()
        for bot in all_bots:
            if bot.instance_id == "master_omar_official":
                continue  # Master Omar is polled by mtproto_manager
            if bot.bot_type == BotPlatformType.OFFICIAL_BOT and bot.is_active:
                self.start_bot_polling(bot)

    def start_bot_polling(self, bot: BotInstanceConfig) -> None:
        """
        Spawns or restarts a polling task for an individual factory bot.
        """
        if not bot.token_or_session or ":" not in bot.token_or_session:
            logger.debug(f"Skipping polling for bot [{bot.name}]: No valid Bot Token.")
            return

        if bot.instance_id == "master_omar_official":
            try:
                asyncio.create_task(self.push_botfather_profile_update(bot))
            except Exception:
                pass
            return

        # Cancel existing task if running
        if bot.instance_id in self._polling_tasks:
            t = self._polling_tasks[bot.instance_id]
            if not t.done():
                t.cancel()

        task = asyncio.create_task(self._poll_bot_loop(bot))
        self._polling_tasks[bot.instance_id] = task
        logger.info(f"🚀 Started dedicated polling loop for factory bot: {bot.name} ({bot.instance_id})")

    def stop_bot_polling(self, instance_id: str) -> None:
        if instance_id in self._polling_tasks:
            t = self._polling_tasks.pop(instance_id)
            if not t.done():
                t.cancel()
            logger.info(f"Stopped polling loop for bot: {instance_id}")

    def reload_bot(self, instance_id: str) -> None:
        """
        Hot-reloads a running bot in memory with its newest config from factory database,
        and immediately pushes any updated Name / Bio / MenuButton to Telegram.
        """
        bot = bot_factory.get_bot(instance_id)
        if not bot or not bot.is_active:
            self.stop_bot_polling(instance_id)
            return
        logger.info(
            f"🔥 [Hot-Reload] Restarting live polling & syncing profile/MenuButton for bot: {bot.name} ({bot.instance_id})"
        )
        self.start_bot_polling(bot)

    def stop_all(self) -> None:
        self._is_running = False
        for inst_id, task in list(self._polling_tasks.items()):
            if not task.done():
                task.cancel()
        self._polling_tasks.clear()
        logger.info("Multi-Bot Polling Dispatcher stopped.")

    # =========================================================================
    # One-Shot MTProto DC Wake-Up & Live Profile / MenuButton Synchronization
    # =========================================================================

    async def _wake_token_on_telegram_dc_once(self, bot: BotInstanceConfig) -> bool:
        """
        One-shot helper: If a brand-new bot token from @BotFather initially returns 502 Bad Gateway
        on Telegram's HTTP Bot API gateway, briefly connects via Telethon MTProto (`ImportBotAuthorizationRequest`),
        registers its profile on Telegram's Data Center, and immediately disconnects so standard HTTP Bot API
        polling (`getUpdates` / `sendMessage`) works at 100% speed.
        """
        token = bot.token_or_session
        if not token or ":" not in token:
            return False

        if bot.instance_id not in self._wake_locks:
            self._wake_locks[bot.instance_id] = asyncio.Lock()

        async with self._wake_locks[bot.instance_id]:
            client = None
            try:
                from telethon import TelegramClient, functions
                from aether_human_core.config.settings import settings

                if not settings.telegram_api_id or not settings.telegram_api_hash:
                    return False

                os.makedirs("sessions", exist_ok=True)
                tok_hash = hashlib.md5(token.encode("utf-8")).hexdigest()[:8]
                session_path = os.path.join("sessions", f"wake_{bot.instance_id}_{tok_hash}")

                client = TelegramClient(
                    session_path,
                    settings.telegram_api_id,
                    settings.telegram_api_hash,
                )
                await asyncio.wait_for(client.start(bot_token=token), timeout=15.0)
                me = await asyncio.wait_for(client.get_me(), timeout=8.0)
                username = getattr(me, "username", "") or ""
                if username:
                    self._bot_usernames[bot.instance_id] = username

                about_text = (bot.bio or f"{bot.name} — شخصية ذكية من منظومة Aether ✨").strip()[:115]
                loc_str = f" من {bot.origin_location}" if bot.origin_location else ""
                desc_text = (
                    f"✨ {bot.name}{loc_str}\n"
                    f"{about_text}\n\n"
                    f"اضغط /start لبدء المحادثة أو فتح لوحة التحكم الخاصة بـ {bot.name}."
                )[:500]
                try:
                    await client(
                        functions.bots.SetBotInfoRequest(
                            lang_code="",
                            name=bot.name[:64],
                            about=about_text,
                            description=desc_text,
                        )
                    )
                except Exception:
                    pass
                logger.info(f"⚡ [MTProto DC Wake-Up] Unlocked token for @{username} ({bot.name}) on Telegram DC!")
                return True
            except Exception as exc:
                logger.debug(f"MTProto one-shot wake notice for [{bot.name}]: {exc}")
                return False
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

    async def _sync_bot_profile_via_http(self, bot: BotInstanceConfig, api_url: str) -> None:
        """
        Pushes the bot's configured Name, Bio, Description, Commands, and WebApp MenuButton via HTTP Bot API.
        """
        http = await self._get_http()
        about_text = (bot.bio or f"{bot.name} — شخصية ذكية من منظومة Aether ✨").strip()[:115]
        loc_str = f" من {bot.origin_location}" if bot.origin_location else ""
        desc_text = (
            f"✨ {bot.name}{loc_str}\n"
            f"{about_text}\n\n"
            f"اضغط /start لبدء المحادثة أو فتح لوحة التحكم الخاصة بـ {bot.name}."
        )[:500]
        try:
            await http.post(f"{api_url}/setMyName", json={"name": bot.name[:64]}, timeout=10.0)
            await http.post(f"{api_url}/setMyShortDescription", json={"short_description": about_text}, timeout=10.0)
            await http.post(f"{api_url}/setMyDescription", json={"description": desc_text}, timeout=10.0)
            await http.post(
                f"{api_url}/setMyCommands",
                json={
                    "commands": [
                        {"command": "start", "description": f"بدء المحادثة وفتح لوحة تحكم {bot.name} ✨"},
                        {"command": "menu", "description": f"عرض القائمة التفاعلية لـ {bot.name} 🎛️"},
                        {"command": "botfather", "description": f"تعديل اسم وصورة وبايو {bot.name} (للأدمن) ⚙️"},
                        {"command": "bots_chat", "description": "تشغيل ساحة حوار البوتات الحي في الجروب 🎭"},
                        {"command": "stop_chat", "description": "إيقاف حوار البوتات في الجروب 🛑"},
                    ]
                },
                timeout=10.0,
            )
            await self.sync_bot_menu_button(bot)
        except Exception as exc:
            logger.debug(f"Profile HTTP sync notice for [{bot.name}]: {exc}")

    async def push_botfather_profile_update(self, bot: BotInstanceConfig) -> Tuple[bool, str]:
        """
        Immediately pushes the bot's Name, Bio (Short Description), Description, and Menu Button
        to Telegram BotFather via Official HTTP Bot API (`setMyName`, `setMyShortDescription`, `setMyDescription`).
        """
        if not bot or bot.bot_type != BotPlatformType.OFFICIAL_BOT:
            return False, "هذا الحساب ليس بوت BotFather رسمي."
        token = bot.token_or_session
        if not token or ":" not in token:
            return False, "توكن البوت غير صالح."

        api_url = f"https://api.telegram.org/bot{token}"
        http = await self._get_http()
        about_text = (bot.bio or f"{bot.name} — شخصية ذكية من منظومة Aether ✨").strip()[:115]
        loc_str = f" من {bot.origin_location}" if bot.origin_location else ""
        desc_text = (
            f"✨ {bot.name}{loc_str}\n"
            f"{about_text}\n\n"
            f"اضغط /start لبدء المحادثة أو فتح لوحة التحكم الخاصة بـ {bot.name}."
        )[:500]

        warnings: List[str] = []
        try:
            r_name = await http.post(f"{api_url}/setMyName", json={"name": bot.name[:64]}, timeout=10.0)
            if r_name.status_code != 200:
                warnings.append(f"ملاحظة الاسم: {r_name.json().get('description', '')}")

            r_short = await http.post(
                f"{api_url}/setMyShortDescription",
                json={"short_description": about_text},
                timeout=10.0,
            )
            if r_short.status_code != 200:
                warnings.append(f"ملاحظة البايو: {r_short.json().get('description', '')}")

            await http.post(
                f"{api_url}/setMyDescription",
                json={"description": desc_text},
                timeout=10.0,
            )
            await self.sync_bot_menu_button(bot)
            if warnings:
                return True, f"✅ تم حفظ التعديلات في النظام وتحديث تليجرام ({' | '.join(warnings)})"
            return True, f"✅ تم تحديث اسم وبايو البوت «{bot.name}» في تليجرام (BotFather) وفي النظام فوراً!"
        except Exception as exc:
            logger.warning(f"push_botfather_profile_update error for [{bot.name}]: {exc}")
            return False, f"تم الحفظ في النظام، وتعذر الوصول المؤقت لواجهة تليجرام: {exc}"

    async def upload_botfather_profile_photo(
        self, bot: BotInstanceConfig, image_bytes: bytes
    ) -> Tuple[bool, str]:
        """
        Normalizes `image_bytes` to JPEG, saves locally for the Mini-App avatar, and pushes it live
        to Telegram BotFather via `POST /setMyProfilePhoto` (`InputProfilePhotoStatic`).
        """
        if not bot or not image_bytes:
            return False, "لم يتم استلام بيانات الصورة."

        jpeg_bytes = image_bytes
        try:
            import io
            from PIL import Image

            with Image.open(io.BytesIO(image_bytes)) as im:
                rgb_im = im.convert("RGB")
                # Center-crop to square if rectangular (Telegram profile photos require square or clean aspect)
                w, h = rgb_im.size
                if w != h:
                    side = min(w, h)
                    left = (w - side) // 2
                    top = (h - side) // 2
                    rgb_im = rgb_im.crop((left, top, left + side, top + side))
                if rgb_im.size[0] > 1024:
                    rgb_im = rgb_im.resize((1024, 1024))
                out_buf = io.BytesIO()
                rgb_im.save(out_buf, format="JPEG", quality=92)
                jpeg_bytes = out_buf.getvalue()
        except Exception as pil_ex:
            logger.debug(f"PIL avatar normalization notice: {pil_ex}")

        # 1. Save locally and update bot.avatar_url in BotFactory DB
        os.makedirs(os.path.join(os.getcwd(), "artifacts", "bot_avatars"), exist_ok=True)
        local_path = os.path.join(os.getcwd(), "artifacts", "bot_avatars", f"{bot.instance_id}.jpg")
        with open(local_path, "wb") as f:
            f.write(jpeg_bytes)

        avatar_rel_url = f"/api/webapp/bot_avatar/{bot.instance_id}?v={int(time.time())}"
        bot.avatar_url = avatar_rel_url
        bot_factory._save_database()

        # 2. Push to Telegram BotFather via Official Bot API `setMyProfilePhoto`
        token = bot.token_or_session
        if bot.bot_type == BotPlatformType.OFFICIAL_BOT and token and ":" in token:
            import json as _json
            api_url = f"https://api.telegram.org/bot{token}/setMyProfilePhoto"
            http = await self._get_http()
            try:
                res = await http.post(
                    api_url,
                    data={"photo": _json.dumps({"type": "static", "photo": "attach://avatar"})},
                    files={"avatar": ("avatar.jpg", jpeg_bytes, "image/jpeg")},
                    timeout=25.0,
                )
                if res.status_code == 200 and res.json().get("ok"):
                    logger.info(f"🖼️ Successfully updated Telegram BotFather Profile Photo for [{bot.name}]!")
                    return (
                        True,
                        f"🖼️✅ تم تغيير الصورة الشخصية (Profile Photo) للبوت «{bot.name}» في تليجرام (BotFather) وفي التطبيق المصغر بنجاح!",
                    )
                else:
                    desc = res.json().get("description", res.text)
                    logger.warning(f"setMyProfilePhoto response for [{bot.name}]: {desc}")
                    return (
                        True,
                        f"✅ تم تحديث صورة «{bot.name}» في التطبيق المصغر (ملاحظة تليجرام: {desc})",
                    )
            except Exception as exc:
                logger.warning(f"setMyProfilePhoto exception for [{bot.name}]: {exc}")
                return True, f"✅ تم تحديث صورة «{bot.name}» في التطبيق المصغر."

        return True, f"✅ تم حفظ وتحديث صورة «{bot.name}» بنجاح!"

    def set_pending_admin_action(
        self,
        user_id: int,
        bot_id: str,
        action: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._pending_admin_actions[(int(user_id), str(bot_id))] = {
            "action": action,
            "extra": extra or {},
            "timestamp": time.time(),
        }

    def clear_pending_admin_action(self, user_id: int, bot_id: str) -> None:
        self._pending_admin_actions.pop((int(user_id), str(bot_id)), None)

    async def _send_html_with_fallback(
        self,
        api_url: str,
        chat_id: int,
        text: str,
        markup: Optional[Dict[str, Any]] = None,
        reply_to_msg_id: Optional[int] = None,
    ) -> None:
        http = await self._get_http()
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if markup:
            payload["reply_markup"] = markup
        if reply_to_msg_id:
            payload["reply_to_message_id"] = reply_to_msg_id

        res = await http.post(f"{api_url}/sendMessage", json=payload, timeout=12.0)
        if res.status_code != 200 and markup and "inline_keyboard" in markup:
            clean_rows = []
            for row in markup.get("inline_keyboard", []):
                clean_rows.append([{k: v for k, v in b.items() if k != "style"} for b in row])
            payload["reply_markup"] = {"inline_keyboard": clean_rows}
            await http.post(f"{api_url}/sendMessage", json=payload, timeout=12.0)

    async def _extract_photo_bytes_from_msg(
        self, msg: Dict[str, Any], token: str
    ) -> Optional[bytes]:
        """
        Extracts image bytes from a Telegram message (or its reply_to_message) via Bot API getFile.
        """
        http = await self._get_http()
        api_url = f"https://api.telegram.org/bot{token}"
        target_msg = msg
        if not target_msg.get("photo") and not target_msg.get("document"):
            if msg.get("reply_to_message"):
                target_msg = msg["reply_to_message"]

        file_id = None
        if target_msg.get("photo"):
            photos = target_msg["photo"]
            if isinstance(photos, list) and photos:
                file_id = photos[-1].get("file_id")
        elif target_msg.get("document"):
            doc = target_msg["document"]
            mime = (doc.get("mime_type") or "").lower()
            if mime.startswith("image/"):
                file_id = doc.get("file_id")

        if not file_id:
            return None

        try:
            r_info = await http.get(f"{api_url}/getFile", params={"file_id": file_id}, timeout=15.0)
            if r_info.status_code == 200 and r_info.json().get("ok"):
                file_path = r_info.json()["result"]["file_path"]
                dl = await http.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=25.0)
                if dl.status_code == 200:
                    return dl.content
        except Exception as ex:
            logger.warning(f"Failed to download photo from message: {ex}")
        return None

    async def handle_in_bot_admin_action_or_command(
        self,
        bot: BotInstanceConfig,
        msg: Dict[str, Any],
        chat_id: int,
        sender_id: int,
        sender_name: str,
        is_group: bool,
    ) -> bool:
        """
        Handles direct in-bot BotFather & Persona editing commands and interactive button wizard steps
        for authorized bot admins (e.g. Marselin CO_ADMIN_ID on Bato, or Supreme King KING_USER_ID on any bot).
        Returns True if the message was consumed as an admin action/command.
        """
        raw_text = (msg.get("text") or msg.get("caption") or "").strip()
        cmd_word = raw_text.split()[0].lower().split("@")[0] if raw_text else ""
        cmd_arg = raw_text[len(raw_text.split()[0]):].strip() if raw_text and len(raw_text.split()) > 1 else ""

        token = bot.token_or_session
        api_url = f"https://api.telegram.org/bot{token}"

        # 1. Check if user is canceling an active wizard step
        pending = self._pending_admin_actions.get((int(sender_id), bot.instance_id))
        if pending and time.time() - pending.get("timestamp", 0) > 600:
            self.clear_pending_admin_action(sender_id, bot.instance_id)
            pending = None

        if cmd_word in ("/cancel", "/الغاء", "إلغاء", "الغاء") and pending:
            self.clear_pending_admin_action(sender_id, bot.instance_id)
            from aether_human_core.telegram_client.telegram_menu import telegram_menu
            p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, bot.instance_id)
            await self._send_html_with_fallback(
                api_url,
                chat_id,
                f"✅ <b>تم إلغاء عملية التعديل الحالية.</b>\n\n{p_txt}",
                p_mk,
                reply_to_msg_id=msg.get("message_id"),
            )
            return True

        # If a slash command like /start or /menu arrives, clear any pending wizard and let normal command handler run
        if cmd_word in ("/start", "/menu", "/panel", "/control", "/dashboard"):
            if pending:
                self.clear_pending_admin_action(sender_id, bot.instance_id)
            return False

        # 2. Direct One-Line BotFather & Persona Commands inside the bot
        direct_admin_cmds = (
            "/botfather", "/تعديل_البوت", "/اعدادات_البوت",
            "/set_bot_name", "/اسم_البوت",
            "/set_bot_bio", "/بايو_البوت",
            "/set_bot_photo", "/صورة_البوت",
            "/set_bot_prompt", "/برومبت_البوت",
            "/set_bot_country", "/بلد_البوت",
        )
        if cmd_word in direct_admin_cmds:
            if not bot_factory.can_user_manage_bot(sender_id, bot):
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    "⛔ <b>عذراً:</b> هذه الأوامر مخصصة فقط لمالك وأدمن هذا البوت.",
                    reply_to_msg_id=msg.get("message_id"),
                )
                return True

            from aether_human_core.telegram_client.telegram_menu import telegram_menu

            if cmd_word in ("/botfather", "/تعديل_البوت", "/اعدادات_البوت"):
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, bot.instance_id)
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

            if cmd_word in ("/set_bot_name", "/اسم_البوت"):
                if not cmd_arg:
                    self.set_pending_admin_action(sender_id, bot.instance_id, "set_name", {"target_bot_id": bot.instance_id})
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        f"✏️ <b>تغيير اسم البوت «{bot.name}» في BotFather:</b>\n"
                        f"أرسل الآن الاسم الجديد في رسالة (أو أرسل /cancel للإلغاء):",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                bot_factory.update_bot_persona(instance_id=bot.instance_id, name=cmd_arg)
                updated_bot = bot_factory.get_bot(bot.instance_id) or bot
                _, bf_msg = await self.push_botfather_profile_update(updated_bot)
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, bot.instance_id, status_banner=bf_msg)
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

            if cmd_word in ("/set_bot_bio", "/بايو_البوت"):
                if not cmd_arg:
                    self.set_pending_admin_action(sender_id, bot.instance_id, "set_bio", {"target_bot_id": bot.instance_id})
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        f"📝 <b>تغيير بايو البوت «{bot.name}» في BotFather:</b>\n"
                        f"أرسل الآن البايو (النبذة التعريفية) الجديد في رسالة (أو أرسل /cancel للإلغاء):",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                bot_factory.update_bot_persona(instance_id=bot.instance_id, bio=cmd_arg)
                updated_bot = bot_factory.get_bot(bot.instance_id) or bot
                _, bf_msg = await self.push_botfather_profile_update(updated_bot)
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, bot.instance_id, status_banner=bf_msg)
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

            if cmd_word in ("/set_bot_photo", "/صورة_البوت"):
                img_bytes = await self._extract_photo_bytes_from_msg(msg, token)
                if not img_bytes:
                    self.set_pending_admin_action(sender_id, bot.instance_id, "set_photo", {"target_bot_id": bot.instance_id})
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        f"🖼️ <b>تغيير الصورة الشخصية (Profile Photo) للبوت «{bot.name}» في BotFather:</b>\n"
                        f"📸 أرسل الآن الصورة الجديدة في الشات مباشرًة (أو أرسل /cancel للإلغاء):",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                updated_bot = bot_factory.get_bot(bot.instance_id) or bot
                _, bf_msg = await self.upload_botfather_profile_photo(updated_bot, img_bytes)
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, bot.instance_id, status_banner=bf_msg)
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

            if cmd_word in ("/set_bot_prompt", "/برومبت_البوت"):
                if not cmd_arg:
                    self.set_pending_admin_action(sender_id, bot.instance_id, "set_prompt", {"target_bot_id": bot.instance_id})
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        f"🧠 <b>تغيير برومبت وشخصية البوت «{bot.name}»:</b>\n"
                        f"أرسل الآن تعليمات الشخصية والبرومبت الجديد في رسالة (أو أرسل /cancel للإلغاء):",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                bot_factory.update_bot_persona(instance_id=bot.instance_id, system_prompt=cmd_arg)
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(
                    sender_id, bot.instance_id, status_banner="✅ تم تحديث برومبت وشخصية البوت بنجاح!"
                )
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

            if cmd_word in ("/set_bot_country", "/بلد_البوت"):
                if not cmd_arg:
                    self.set_pending_admin_action(sender_id, bot.instance_id, "set_origin", {"target_bot_id": bot.instance_id})
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        f"🌍 <b>تغيير بلد وموطن البوت «{bot.name}»:</b>\n"
                        f"أرسل الآن اسم البلد أو المدينة (مثلاً: سوريا، دمشق، العراق، مصر، السعودية):",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                bot_factory.update_bot_persona(instance_id=bot.instance_id, origin_location=cmd_arg)
                updated_bot = bot_factory.get_bot(bot.instance_id) or bot
                await self.push_botfather_profile_update(updated_bot)
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(
                    sender_id, bot.instance_id, status_banner=f"🌍✅ تم تحديث موطن ومنطقة توقيت البوت إلى «{cmd_arg}»!"
                )
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
                return True

        # 3. Interactive Multi-Step Button Wizard Execution
        if not pending:
            return False

        action = pending.get("action", "")
        extra = pending.get("extra", {})
        target_bot_id = extra.get("target_bot_id") or bot.instance_id
        target_bot = bot_factory.get_bot(target_bot_id) or bot
        from aether_human_core.telegram_client.telegram_menu import telegram_menu

        if action == "set_photo":
            if not bot_factory.can_user_manage_bot(sender_id, target_bot):
                self.clear_pending_admin_action(sender_id, bot.instance_id)
                return True
            img_bytes = await self._extract_photo_bytes_from_msg(msg, token)
            if not img_bytes:
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    "⚠️ <b>يرجى إرسال صورة (Photo) الآن</b> لتعيينها كصورة شخصية للبوت في تليجرام (أو أرسل /cancel للإلغاء):",
                    reply_to_msg_id=msg.get("message_id"),
                )
                return True
            self.clear_pending_admin_action(sender_id, bot.instance_id)
            _, bf_msg = await self.upload_botfather_profile_photo(target_bot, img_bytes)
            p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(sender_id, target_bot.instance_id, status_banner=bf_msg)
            await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
            return True

        if action in ("set_name", "set_bio", "set_prompt", "set_origin", "set_dialect"):
            if not bot_factory.can_user_manage_bot(sender_id, target_bot):
                self.clear_pending_admin_action(sender_id, bot.instance_id)
                return True
            if not raw_text:
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    "⚠️ يرجى إرسال النص المطلوب (أو أرسل /cancel للإلغاء):",
                    reply_to_msg_id=msg.get("message_id"),
                )
                return True

            self.clear_pending_admin_action(sender_id, bot.instance_id)
            if action == "set_name":
                bot_factory.update_bot_persona(instance_id=target_bot.instance_id, name=raw_text)
                updated_bot = bot_factory.get_bot(target_bot.instance_id) or target_bot
                _, status_banner = await self.push_botfather_profile_update(updated_bot)
            elif action == "set_bio":
                bot_factory.update_bot_persona(instance_id=target_bot.instance_id, bio=raw_text)
                updated_bot = bot_factory.get_bot(target_bot.instance_id) or target_bot
                _, status_banner = await self.push_botfather_profile_update(updated_bot)
            elif action == "set_prompt":
                bot_factory.update_bot_persona(instance_id=target_bot.instance_id, system_prompt=raw_text)
                status_banner = f"🧠✅ تم تحديث برومبت وشخصية البوت «{target_bot.name}» بنجاح!"
            elif action == "set_origin":
                bot_factory.update_bot_persona(instance_id=target_bot.instance_id, origin_location=raw_text)
                updated_bot = bot_factory.get_bot(target_bot.instance_id) or target_bot
                await self.push_botfather_profile_update(updated_bot)
                status_banner = f"🌍✅ تم تحديث بلد وتوقيت البوت «{target_bot.name}» إلى «{raw_text}»!"
            else:
                bot_factory.update_bot_persona(instance_id=target_bot.instance_id, primary_dialect=raw_text)
                status_banner = f"🗣️✅ تم تحديث لهجة البوت «{target_bot.name}» بنجاح!"

            p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(
                sender_id, target_bot.instance_id, status_banner=status_banner
            )
            await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
            return True

        if action == "create_bot_token":
            if not bot_factory.is_factory_admin(sender_id):
                self.clear_pending_admin_action(sender_id, bot.instance_id)
                return True
            cand_token = raw_text.strip()
            if ":" not in cand_token or len(cand_token) < 25:
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    "⚠️ <b>التوكن غير صالح!</b>\nيرجى نسخ توكن البوت من @BotFather بالصيغة الصحيحة (مثال: <code>123456789:ABCdef...</code>) أو أرسل /cancel للإلغاء:",
                    reply_to_msg_id=msg.get("message_id"),
                )
                return True
            http = await self._get_http()
            try:
                r_me = await http.get(f"https://api.telegram.org/bot{cand_token}/getMe", timeout=10.0)
                if r_me.status_code != 200 or not r_me.json().get("ok"):
                    await self._send_html_with_fallback(
                        api_url,
                        chat_id,
                        "❌ <b>تليجرام رفض هذا التوكن!</b> تأكد من نسخ التوكن الصحيح من @BotFather أو أرسل /cancel للإلغاء:",
                        reply_to_msg_id=msg.get("message_id"),
                    )
                    return True
                me_info = r_me.json()["result"]
                tg_bot_name = me_info.get("first_name", "بوت جديد")
                tg_bot_user = me_info.get("username", "")
            except Exception as ex:
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    f"⚠️ تعذر التحقق من التوكن: {ex}\nحاول مرة أخرى أو أرسل /cancel للإلغاء:",
                    reply_to_msg_id=msg.get("message_id"),
                )
                return True

            self.set_pending_admin_action(
                sender_id,
                bot.instance_id,
                "create_bot_name_country",
                {"new_token": cand_token, "default_name": tg_bot_name, "username": tg_bot_user},
            )
            await self._send_html_with_fallback(
                api_url,
                chat_id,
                f"✅ <b>تم التحقق من التوكن بنجاح!</b> (@{tg_bot_user})\n\n"
                f"✍️ أرسل الآن <b>اسم البوت والبلد والوصف</b> في سطر واحد أو عدة أسطر:\n"
                f"<i>مثال:</i>\n"
                f"<code>الاسم: ليث\nالبلد: سوريا\nالبايو: مساعد ذكي ومهذب\nالبرومبت: أنت ليث شاب سوري ذكي ومحترم...</code>\n\n"
                f"💡 <i>أو أرسل اسم البوت فقط (مثلاً: {tg_bot_name}) وسيتم إنشاؤه وتفعيله فوراً!</i>",
                reply_to_msg_id=msg.get("message_id"),
            )
            return True

        if action == "create_bot_name_country":
            if not bot_factory.is_factory_admin(sender_id):
                self.clear_pending_admin_action(sender_id, bot.instance_id)
                return True
            self.clear_pending_admin_action(sender_id, bot.instance_id)
            new_token = extra.get("new_token", "")
            new_name = extra.get("default_name", "بوت ذكي")
            new_origin = "سوريا" if int(sender_id) == CO_ADMIN_ID else ""
            new_bio = ""
            new_prompt = ""
            new_gender = BotGender.MALE

            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
            if len(lines) == 1 and ":" not in lines[0]:
                new_name = lines[0].strip() or new_name
            else:
                for ln in lines:
                    if ln.startswith(("الاسم:", "اسم:")):
                        new_name = ln.split(":", 1)[1].strip() or new_name
                    elif ln.startswith(("البلد:", "بلد:", "الموطن:")):
                        new_origin = ln.split(":", 1)[1].strip()
                    elif ln.startswith(("البايو:", "بايو:", "الوصف:")):
                        new_bio = ln.split(":", 1)[1].strip()
                    elif ln.startswith(("البرومبت:", "برومبت:", "الشخصية:")):
                        new_prompt = ln.split(":", 1)[1].strip()
                    elif ln.startswith(("الجنس:", "النوع:")):
                        g_val = ln.split(":", 1)[1].strip()
                        if any(w in g_val for w in ("بنت", "أنثى", "انثى", "female")):
                            new_gender = BotGender.FEMALE

            if not new_prompt:
                new_prompt = f"أنت '{new_name}'، شخصية ذكية وودودة، تتحدث بأسلوب طبيعي ومحترم."

            new_inst_id = f"bot_{int(time.time() * 1000)}"
            ok, msg_create, created_bot = bot_factory.create_bot(
                instance_id=new_inst_id,
                name=new_name,
                bot_type=BotPlatformType.OFFICIAL_BOT,
                token_or_session=new_token,
                gender=new_gender,
                bio=new_bio,
                origin_location=new_origin,
                custom_prompt=new_prompt,
                owner_id=int(sender_id),
            )
            if ok and created_bot:
                p_txt, p_mk = await telegram_menu.render_single_bot_editor_panel(
                    sender_id,
                    created_bot.instance_id,
                    status_banner=f"🎉 {msg_create} (@{extra.get('username', '')})",
                )
                await self._send_html_with_fallback(api_url, chat_id, p_txt, p_mk, msg.get("message_id"))
            else:
                await self._send_html_with_fallback(
                    api_url,
                    chat_id,
                    f"❌ تعذر إنشاء البوت: {msg_create}",
                    reply_to_msg_id=msg.get("message_id"),
                )
            return True

        return False

    async def sync_bot_menu_button(
        self,
        bot: BotInstanceConfig,
        tunnel_url: Optional[str] = None,
        specific_chat_id: Optional[int] = None,
    ) -> None:
        """
        Synchronizes the live Cloudflare WebApp Menu Button for a single factory bot
        BOTH globally (default for all users) AND explicitly per-user (for the King, Super Admins,
        and any active `specific_chat_id`) so Telegram never serves a stale cached per-chat Menu Button URL!
        """
        if not bot or bot.bot_type != BotPlatformType.OFFICIAL_BOT:
            return
        token = bot.token_or_session
        if not token or ":" not in token:
            return

        if not tunnel_url:
            try:
                from cloud_and_resource_guard.cloudflare_tunnel_manager import cloudflare_manager
                tunnel_url = cloudflare_manager.get_current_tunnel_url(cache_bust=False)
            except Exception:
                return

        if not tunnel_url or not tunnel_url.startswith("https://") or "api.trycloudflare.com" in tunnel_url:
            return

        base_clean = tunnel_url.split("?")[0].rstrip("/")
        if not base_clean.endswith("/webapp"):
            base_clean = f"{base_clean}/webapp"

        bot_url = f"{base_clean}?bot_id={bot.instance_id}&v={int(time.time())}"
        menu_button_obj = {
            "type": "web_app",
            "text": f"✨ تطبيق {bot.name}",
            "web_app": {"url": bot_url},
        }

        http = await self._get_http()
        endpoint = f"https://api.telegram.org/bot{token}/setChatMenuButton"

        try:
            # 1. Update Global Default Menu Button
            res = await http.post(endpoint, json={"menu_button": menu_button_obj}, timeout=10.0)
            if res.status_code == 200:
                logger.info(f"✅ Synced Menu Button for factory bot [{bot.name}] -> {bot_url}")

            # 2. Explicitly update per-user chat_id Menu Button for King, Super Admins, and specific_chat_id
            from aether_human_core.config.settings import settings
            target_chat_ids = set(settings.super_admin_ids_list) | {
                settings.the_king_user_id,
                settings.the_king_user_id,
                CO_ADMIN_ID,
                8639581207,
            }
            if specific_chat_id and int(specific_chat_id) > 0:
                target_chat_ids.add(int(specific_chat_id))

            for cid in target_chat_ids:
                if not cid or int(cid) <= 0:
                    continue
                try:
                    await http.post(
                        endpoint,
                        json={"chat_id": int(cid), "menu_button": menu_button_obj},
                        timeout=8.0,
                    )
                except Exception:
                    pass
        except Exception as ex:
            logger.debug(f"Failed to sync Menu Button for [{bot.name}]: {ex}")

    async def sync_all_menu_buttons(self, tunnel_url: Optional[str] = None) -> None:
        """
        Synchronizes live Cloudflare WebApp Menu Button across all active factory official bots
        (both globally and per-user for the King and admins).
        """
        all_bots = bot_factory.list_all_bots()
        for bot in all_bots:
            if bot.bot_type == BotPlatformType.OFFICIAL_BOT and bot.token_or_session and ":" in bot.token_or_session:
                await self.sync_bot_menu_button(bot, tunnel_url=tunnel_url)

    async def _poll_bot_loop(self, bot: BotInstanceConfig) -> None:
        """
        Continuous HTTP long-polling worker for a single sub-bot instance.
        If a brand-new token returns HTTP 502 3 times in a row, wakes it once via MTProto
        and continues standard HTTP Bot API polling.
        """
        http = await self._get_http()
        token = bot.token_or_session
        api_url = f"https://api.telegram.org/bot{token}"
        last_update_id = 0

        # 1. Verify bot identity on startup
        for attempt in range(2):
            try:
                me_res = await http.get(f"{api_url}/getMe", timeout=12.0)
                if me_res.status_code == 200 and me_res.json().get("ok"):
                    me_info = me_res.json()["result"]
                    username = me_info.get("username", "")
                    self._bot_usernames[bot.instance_id] = username
                    logger.info(f"✨ Sub-Bot authenticated: @{username} | Name: '{bot.name}'")
                    break
                elif me_res.status_code in (502, 503, 504) and attempt == 0:
                    logger.warning(f"⚡ HTTP {me_res.status_code} on getMe for [{bot.name}]. Running one-shot DC wake-up...")
                    await self._wake_token_on_telegram_dc_once(bot)
                else:
                    logger.warning(f"Could not verify token for bot [{bot.name}]: {me_res.text}")
            except Exception as ce:
                logger.debug(f"getMe notice for [{bot.name}]: {ce}")

        # 2. Sync bot profile (Name, Bio, Description, Commands) & WebApp MenuButton (Global + Per-User)
        asyncio.create_task(self._sync_bot_profile_via_http(bot, api_url))

        # 3. Flush old updates backlog on startup so we only process live messages
        try:
            init_res = await http.get(f"{api_url}/getUpdates", params={"limit": 50, "timeout": 1}, timeout=12.0)
            if init_res.status_code == 200:
                results = init_res.json().get("result", [])
                if results:
                    last_update_id = results[-1]["update_id"]
        except Exception:
            pass

        consecutive_502 = 0
        while self._is_running:
            try:
                live_cfg = bot_factory.get_bot(bot.instance_id)
                if not live_cfg or not live_cfg.is_active:
                    logger.info(f"Bot [{bot.instance_id}] deactivated or removed. Terminating polling loop.")
                    break

                res = await http.get(
                    f"{api_url}/getUpdates",
                    params={"timeout": 25, "offset": last_update_id + 1},
                    timeout=35.0,
                )
                if res.status_code == 200:
                    consecutive_502 = 0
                    data = res.json()
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        asyncio.create_task(self._process_sub_bot_update(live_cfg, update))
                elif res.status_code in (502, 503, 504):
                    consecutive_502 += 1
                    if consecutive_502 == 3:
                        logger.warning(f"⚡ 3x HTTP {res.status_code} on [{bot.name}]. Running one-shot DC wake-up...")
                        await self._wake_token_on_telegram_dc_once(live_cfg)
                    await asyncio.sleep(2.0)
                elif res.status_code == 409:
                    logger.warning(f"Conflict on bot [{bot.name}]: another instance polling. Sleeping 5s...")
                    await asyncio.sleep(5.0)
                else:
                    await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Polling network exception for bot [{bot.name}]: {e}")
                await asyncio.sleep(2.0)

    async def relay_group_message_to_sub_bot(
        self,
        winner_bot_id: str,
        chat_id: int,
        chat_title: str,
        message_id: int,
        sender_id: int,
        sender_name: str,
        sender_username: Optional[str],
        text: str,
        reply_to_msg_id: Optional[int] = None,
        reply_to_from_id: Optional[int] = None,
    ) -> None:
        """
        Relays an addressed group message to a factory sub-bot after a brief 1.2s wait in case
        Telegram's `@BotFather` Group Privacy is enabled on that new sub-bot (so Telegram didn't
        deliver the raw non-command group message directly to the sub-bot).
        Deduplicated by `anti_spam_guard.is_spam(..., bot_id=winner_bot_id, chat_id=chat_id, message_id=message_id)`.
        """
        await asyncio.sleep(1.2)
        bot = bot_factory.get_bot(winner_bot_id)
        if not bot or not bot.is_active or bot.instance_id == "master_omar_official":
            return
        if bot.bot_type != BotPlatformType.OFFICIAL_BOT:
            return

        synthetic_msg: Dict[str, Any] = {
            "message_id": message_id,
            "from": {
                "id": sender_id,
                "first_name": sender_name,
                "username": sender_username,
            },
            "chat": {
                "id": chat_id,
                "type": "supergroup",
                "title": chat_title,
            },
            "text": text,
        }
        if reply_to_msg_id:
            r_dict: Dict[str, Any] = {"message_id": reply_to_msg_id}
            if reply_to_from_id:
                r_dict["from"] = {"id": reply_to_from_id}
            synthetic_msg["reply_to_message"] = r_dict

        synthetic_update = {
            "update_id": int(time.time() * 1000) % 1000000000,
            "message": synthetic_msg,
        }
        await self._process_sub_bot_update(bot, synthetic_update)

    async def _process_sub_bot_callback(self, bot: BotInstanceConfig, cb: Dict[str, Any]) -> None:
        """
        Processes callback queries clicked on interactive inline buttons rendered by sub-bots.
        """
        callback_id = cb.get("id")
        data = cb.get("data", "")
        cb_from = cb.get("from", {})
        cb_user_id = cb_from.get("id")
        cb_user_name = cb_from.get("first_name", "مستخدم")
        cb_msg = cb.get("message", {})
        cb_chat = cb_msg.get("chat", {})
        cb_chat_id = cb_chat.get("id")
        cb_msg_id = cb_msg.get("message_id")
        token = bot.token_or_session
        api_url = f"https://api.telegram.org/bot{token}"
        http = await self._get_http()

        try:
            from aether_human_core.telegram_client.telegram_menu import telegram_menu
            text, markup, alert, action = await telegram_menu.handle_callback(
                data, cb_user_id, cb_user_name, bot_instance=bot, chat_id=cb_chat_id
            )
            await http.post(
                f"{api_url}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": alert or "", "show_alert": bool(alert)},
                timeout=8.0,
            )
            if text and markup and cb_chat_id and cb_msg_id:
                await http.post(
                    f"{api_url}/editMessageText",
                    json={"chat_id": cb_chat_id, "message_id": cb_msg_id, "text": text, "reply_markup": markup, "parse_mode": "HTML"},
                    timeout=8.0,
                )
        except Exception as ex:
            logger.debug(f"Sub-bot callback exception [{bot.name}]: {ex}")

    async def _process_sub_bot_update(self, bot: BotInstanceConfig, update: Dict[str, Any]) -> None:
        """
        Parses update received by a factory sub-bot and routes to cognitive handlers with
        the sub-bot's own identity and system prompt.
        """
        cb = update.get("callback_query")
        if cb:
            await self._process_sub_bot_callback(bot, cb)
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
        sender_username = sender.get("username")

        # Anti-Spam Silent Drop Middleware (with Cross-Bot & Relay Deduplication)
        from aether_human_core.telegram_client.anti_spam_guard import anti_spam_guard
        if anti_spam_guard.is_spam(sender_id, bot_id=bot.instance_id, chat_id=chat_id, message_id=message_id):
            logger.debug(f"🚫 [Deduplicated/Spam] Skipped message {message_id} on sub-bot [{bot.name}] from [{sender_id}].")
            return

        token = bot.token_or_session
        api_url = f"https://api.telegram.org/bot{token}"
        http = await self._get_http()
        is_group = (chat_type in ("group", "supergroup")) or (chat_id < 0)

        # In-Bot BotFather & Persona Admin Wizard / Direct Commands (Intercepts before Vision/AI!)
        if await self.handle_in_bot_admin_action_or_command(
            bot=bot,
            msg=msg,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            is_group=is_group,
        ):
            return

        # Task 3.2: Deep Multimodal Vision & File Parsing for Factory Sub-Bots
        from aether_human_core.telegram_client.handlers.media_handler import media_handler as _sub_mh_vis
        if msg.get("sticker") or msg.get("animation") or msg.get("photo") or msg.get("document"):
            inspected_sub = await _sub_mh_vis.inspect_bot_api_media(msg, token, http)
            if inspected_sub:
                text, media_type = inspected_sub
            else:
                text = msg.get("text", "") or msg.get("caption", "") or "[وسائط]"
                media_type = "text"
        elif msg.get("voice") or msg.get("audio"):
            media_type = "voice"
            voice_transcript = None
            try:
                file_id = (msg.get("voice") or msg.get("audio"))["file_id"]
                file_info = await http.get(f"{api_url}/getFile", params={"file_id": file_id}, timeout=15.0)
                if file_info.status_code == 200:
                    file_path_tg = file_info.json()["result"]["file_path"]
                    dl_res = await http.get(f"https://api.telegram.org/file/bot{token}/{file_path_tg}", timeout=25.0)
                    if dl_res.status_code == 200:
                        os.makedirs(os.path.join(os.getcwd(), "artifacts", "voice_notes"), exist_ok=True)
                        local_voice_path = os.path.join(os.getcwd(), "artifacts", "voice_notes", f"incoming_subbot_{file_id}.ogg")
                        with open(local_voice_path, "wb") as f:
                            f.write(dl_res.content)
                        from aether_human_core.multimodal_engine.acoustic_voice.emotion_detector import acoustic_detector
                        analysis = await acoustic_detector.analyze_voice_note(
                            audio_file_path=local_voice_path, sender_name=sender_name
                        )
                        voice_transcript = analysis.transcript
            except Exception as ve:
                logger.debug(f"Failed to transcribe sub-bot incoming voice: {ve}")

            text = voice_transcript if voice_transcript else "[رسالة صوتية]"
        else:
            text = msg.get("text", "") or msg.get("caption", "")
            media_type = "text"

        # Immediate DB Persistence tagged with this specific bot_id
        try:
            from aether_human_core.database.postgres.connection import db_manager
            from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
            async with db_manager.session() as sess:
                m_repo = MessageRepository(sess)
                await m_repo.get_or_create_chat(
                    chat_id=chat_id,
                    title=chat.get("title") or sender_name,
                    chat_type=chat_type,
                )
                await m_repo.log_message(
                    telegram_message_id=message_id,
                    chat_id=chat_id,
                    sender_id=sender_id,
                    text=text,
                    media_type=media_type,
                    is_from_bot=False,
                    reply_to_msg_id=msg.get("reply_to_message", {}).get("message_id"),
                )
        except Exception as pe:
            logger.debug(f"Sub-bot persistence note: {pe}")

        # Check /start command -> Refresh Menu Button & Send welcome with WebApp button (scoped with bot_id)
        is_group = (chat_type in ("group", "supergroup")) or (chat_id < 0)

        # Get bot username if available
        sub_username = self._bot_usernames.get(bot.instance_id) or getattr(bot, "username", "") or ""
        if not sub_username and ":" in token:
            try:
                sub_username = f"bot_{token.split(':')[0]}"
            except Exception:
                sub_username = bot.name

        if text.startswith(("/start", "/menu", "/panel", "/control", "/dashboard")):
            if not is_group:
                # Immediately refresh this user's Menu Button with the latest live Cloudflare URL
                asyncio.create_task(self.sync_bot_menu_button(bot, specific_chat_id=sender_id))

            from aether_human_core.telegram_client.telegram_menu import telegram_menu
            dash_text, dash_markup = await telegram_menu.render_main_dashboard(
                sender_id, user_name=sender_name, bot_instance=bot
            )
            if is_group:
                # Groups forbid inline web_app buttons! Use direct deep-link to private bot
                target_url = f"https://t.me/{sub_username.replace('@', '')}?start=webapp" if sub_username else "https://t.me"
                dash_markup = {
                    "inline_keyboard": [
                        [{"text": f"💬 فتح لوحة تحكم {bot.name} في الخاص 📱", "url": target_url}]
                    ]
                }

            try:
                res = await http.post(
                    f"{api_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": dash_text,
                        "reply_markup": dash_markup,
                        "parse_mode": "HTML",
                    },
                    timeout=12.0,
                )
                if res.status_code != 200:
                    # Fallback without button 'style' keys if Telegram rejects any button field
                    clean_rows = []
                    for row in dash_markup.get("inline_keyboard", []):
                        clean_rows.append([{k: v for k, v in b.items() if k != "style"} for b in row])
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": dash_text,
                            "reply_markup": {"inline_keyboard": clean_rows},
                            "parse_mode": "HTML",
                        },
                        timeout=12.0,
                    )
                logger.info(f"⚡ [{bot.name} /start] Sent interactive dashboard to [{sender_name} ({sender_id})]")
                if not is_group:
                    from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
                    asyncio.create_task(
                        live_event_streamer.stream_dm_event(
                            sender_id=sender_id,
                            sender_name=sender_name,
                            user_text=text,
                            bot_reply=f"⚡ لوحة تحكم {bot.name}",
                            persona_name=f"{bot.name} (Sub-Bot)",
                        )
                    )
            except Exception as se:
                logger.error(f"Failed to send /start reply for sub-bot [{bot.name}]: {se}")
            return

        # Task 4.1 & 4.2: Handle /bots_chat, /حوار, /stop_chat on sub-bots (deduplicated across group bots)
        cmd_token = text.strip().split()[0].lower().split("@")[0] if text.strip() else ""
        if cmd_token in ("/bots_chat", "/حوار", "/bot_arena", "/ساحة_الحوار", "/stop_chat", "/ايقاف_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network as _mb_sbn
            from aether_human_core.config.settings import settings as _mb_settings
            is_king_mb = (sender_id == _mb_settings.the_king_user_id) or (sender_id in _mb_settings.super_admin_ids_list)
            if is_king_mb and _mb_sbn.try_claim_arena_command(chat_id, message_id):
                if cmd_token in ("/stop_chat", "/ايقاف_الحوار"):
                    stopped = await _mb_sbn.stop_bot_arena(chat_id, reason=f"أمر {cmd_token} عبر {bot.name}")
                    stop_txt = "🛑 <b>تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑</b>" if stopped else "ℹ️ <b>حوار البوتات متوقف بالفعل.</b>"
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": stop_txt, "parse_mode": "HTML", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
                else:
                    from aether_human_core.telegram_client.telegram_menu import telegram_menu
                    parts_cmd = text.strip().split()
                    custom_t = text.strip()[len(parts_cmd[0]):].strip() if parts_cmd else ""
                    if custom_t:
                        _mb_sbn.set_arena_topic(chat_id, custom_t)
                    panel_txt, panel_mk = await telegram_menu.render_bot_arena_panel(user_id=sender_id, chat_id=chat_id)
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": panel_txt, "reply_markup": panel_mk, "parse_mode": "HTML", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
            return

        # In groups/supergroups: Coordinate turn election via Central Multi-Bot Group Arbiter
        if is_group:
            from bot_factory.group_arbiter import group_arbiter
            from bot_factory.sibling_bot_network import sibling_network as _mb_sbn
            from aether_human_core.config.settings import settings as _mb_settings
            group_arbiter.record_presence(chat_id, bot.instance_id)
            if chat.get("title"):
                _mb_sbn._known_group_titles[chat_id] = chat.get("title")

            is_king_mb = (sender_id == _mb_settings.the_king_user_id) or (sender_id in _mb_settings.super_admin_ids_list)
            if is_king_mb and _mb_sbn.is_arena_stop_phrase(text) and _mb_sbn.is_arena_active(chat_id):
                if _mb_sbn.try_claim_arena_command(chat_id, message_id):
                    await _mb_sbn.stop_bot_arena(chat_id, reason="أمر إيقاف نصي من المطور")
                    await http.post(
                        f"{api_url}/sendMessage",
                        json={"chat_id": chat_id, "text": "🛑 تم إيقاف حوار البوتات في الجروب فوراً بأمرك يا كبير! 👑", "reply_to_message_id": message_id},
                        timeout=10.0,
                    )
                return

            if _mb_sbn.is_arena_active(chat_id):
                if not _mb_sbn.is_server_sibling(sender_id):
                    _mb_sbn.record_arena_human_interjection(
                        chat_id=chat_id,
                        message_id=message_id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        message_text=text,
                        is_owner=is_king_mb,
                    )
                return

            reply_to = msg.get("reply_to_message", {})
            reply_to_from = reply_to.get("from", {})
            reply_to_msg_id = reply_to.get("message_id") if reply_to else None
            reply_to_from_id = reply_to_from.get("id") if reply_to_from else None

            decision = await group_arbiter.elect_reply_turn(
                chat_id=chat_id,
                message_id=message_id,
                sender_id=sender_id,
                message_text=text,
                reply_to_from_id=reply_to_from_id,
                reply_to_msg_id=reply_to_msg_id,
                is_group=True,
                requesting_bot_id=bot.instance_id,
            )
            if not decision.should_reply:
                # If another sub-bot won by direct name mention/reply, relay to it in case its Group Privacy is ON
                if (
                    decision.winner_bot_id
                    and decision.winner_bot_id != bot.instance_id
                    and decision.reason in ("DIRECT_NAME_OR_MENTION", "DIRECT_REPLY_MATCH")
                ):
                    asyncio.create_task(
                        self.relay_group_message_to_sub_bot(
                            winner_bot_id=decision.winner_bot_id,
                            chat_id=chat_id,
                            chat_title=chat.get("title") or "مجموعة",
                            message_id=message_id,
                            sender_id=sender_id,
                            sender_name=sender_name,
                            sender_username=sender_username,
                            text=text,
                            reply_to_msg_id=reply_to_msg_id,
                            reply_to_from_id=reply_to_from_id,
                        )
                    )
                logger.debug(
                    f"GroupArbiter: Sub-bot [{bot.name}] staying silent in [{chat_id}]. Reason: {decision.reason}"
                )
                return

            if decision.stagger_delay_sec > 0:
                logger.info(f"GroupArbiter: Sub-bot [{bot.name}] staggering reply by {decision.stagger_delay_sec:.1f}s")
                await asyncio.sleep(decision.stagger_delay_sec)

        # Prepare Combined System Prompt & Strict Gender Guidance (Honoring Bot Origin and Dialect)
        gender_guidance = ""
        if bot.gender == BotGender.FEMALE:
            gender_guidance = (
                f"\n\n🌸 تنبيه الهوية الأنثوية الصارم لـ ({bot.name}): "
                f"أنتِ فتاة وصبية أنثى. "
                f"تحدثي دائماً وأبداً بصيغة المؤنث الطبيعية في تصريفات أفعالك وصفاتك "
                f"(أنا صاحية، مبسوطة، شايفة، فاهمة، مركزة، رحت، جيت، بحب، هكون). "
                f"إياكِ نهائياً أن تتحدثي بصيغة المذكر أو تقولي 'أنا عمر'! "
                f"أنتِ فقط {bot.name}، التزمي بهويتك، بلدك، ولهجتك المحددة في توجيهات شخصيتك بدقة وبدون أي فواصل (، أو ,) في كلامك."
            )
        elif bot.gender == BotGender.MALE and bot.instance_id != "master_omar_official":
            gender_guidance = (
                f"\n\n👔 تنبيه الهوية المستقلة لـ ({bot.name}): "
                f"أنت شاب مستقل بذاتك ولست عمر! "
                f"التزم بهويتك، بلدك، ولهجتك المحددة في توجيهات شخصيتك بدقة وبدون أي فواصل (، أو ,) في كلامك."
            )
        persona_isolation_guidance = (
            f"\n\n🛑 [تنبيه فاصل الهوية والأسلوب المستقل لـ {bot.name}]: "
            "أنت تمتلك شخصيتك، لهجتك، نبرتك، أخلاقك، وحدودك الخاصة والمستقلة بالكامل! "
            "المعلومات المتداولة مع أي بوتات أخرى في المجموعة هي مجرد حقائق سياقية ومعلومات فقط. "
            "يُمنع منعاً باتاً التأثر بأسلوب كلام أو لهجة أو إيحاءات أو إيموجيات أو جرأة أي بوت آخر في المجموعة أو محاكاتها إطلاقاً."
        )
        combined_prompt = (bot.system_prompt or "") + gender_guidance + persona_isolation_guidance

        # Check Photo / Selfie Request (Delegated to centralized media_handler guard)
        from aether_human_core.telegram_client.handlers.media_handler import media_handler as _disp_mh
        is_photo_req = _disp_mh.is_selfie_photo_request(text, media_type=media_type)

        if is_photo_req:
            try:
                is_fem = (bot.gender == BotGender.FEMALE)
                lead_text = (
                    f"عيوني يا {sender_name}، دقيقة ألقطلك صورة سريعة وأنا في البيت 😉📸"
                    if is_fem else
                    f"من عيوني يا {sender_name}، دقيقة ألقطلك سيلفي سريع 😉📸"
                )
                await http.post(
                    f"{api_url}/sendMessage",
                    json={"chat_id": chat_id, "text": lead_text, "reply_to_message_id": message_id},
                    timeout=10.0,
                )
                await http.post(f"{api_url}/sendChatAction", json={"chat_id": chat_id, "action": "upload_photo"}, timeout=5.0)

                from aether_human_core.multimodal_engine.visual_identity.face_lock_pipeline import face_lock_pipeline
                photo_path = await face_lock_pipeline.generate_photo(
                    requester_name=sender_name,
                    gender="female" if is_fem else "male",
                    persona_name=bot.name,
                    bot_id=bot.instance_id,
                )

                if photo_path and os.path.exists(photo_path):
                    caption = (
                        f"سيلفي لعيونك يا {sender_name} 😉✨"
                        if is_fem else
                        f"أحلى سيلفي لعيونك يا {sender_name} 😉📸"
                    )
                    with open(photo_path, "rb") as pf:
                        await http.post(
                            f"{api_url}/sendPhoto",
                            data={"chat_id": str(chat_id), "caption": caption, "reply_to_message_id": str(message_id)},
                            files={"photo": (os.path.basename(photo_path), pf, "image/jpeg")},
                            timeout=35.0,
                        )
                    logger.info(f"📸 [{bot.name} Sent Photo] Chat [{chat_id}] for user [{sender_name}]")
                    if not is_group:
                        from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
                        asyncio.create_task(
                            live_event_streamer.stream_dm_event(
                                sender_id=sender_id,
                                sender_name=sender_name,
                                user_text=text,
                                bot_reply=f"📸 [صورة سيلفي]: {caption}",
                                persona_name=f"{bot.name} (Sub-Bot)",
                            )
                        )
                    return
            except Exception as pe:
                logger.error(f"Error handling photo request for sub-bot [{bot.name}]: {pe}")

        # Check Voice Request or Incoming Voice Message Response
        from aether_human_core.multimodal_engine.acoustic_voice.voice_intent_enforcer import voice_intent_enforcer
        is_voice_req, is_sing, song_name = voice_intent_enforcer.detect_intent(text)
        is_audio_response = (media_type == "voice" or is_voice_req)

        if is_audio_response:
            try:
                is_fem = (bot.gender == BotGender.FEMALE)
                gender_str = "female" if is_fem else "male"
                await http.post(f"{api_url}/sendChatAction", json={"chat_id": chat_id, "action": "record_voice"}, timeout=5.0)

                from aether_human_core.multimodal_engine.acoustic_voice.realistic_voice_generator import voice_generator

                if is_sing:
                    pre_text, lyrics = await voice_intent_enforcer.generate_singing_lyrics(
                        user_message=text,
                        user_name=sender_name,
                        song_name=song_name,
                    )
                    if pre_text:
                        await http.post(
                            f"{api_url}/sendMessage",
                            json={"chat_id": chat_id, "text": pre_text, "reply_to_message_id": message_id},
                            timeout=10.0,
                        )
                    voice_script = lyrics
                else:
                    from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator
                    resp = await cognitive_orchestrator.process_incoming_event(
                        telegram_message_id=message_id,
                        chat_id=chat_id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        message_text=text,
                        media_type=media_type,
                        chat_type=chat_type,
                        chat_title=chat.get("title") or f"محادثة مع {sender_name}",
                        extra_system_instruction=combined_prompt,
                        target_bot_name=bot.name,
                        target_bot_id=bot.instance_id,
                        is_userbot=False,
                    )
                    voice_script = resp.raw_response_text
                    if not voice_script or len(voice_script.strip()) < 2:
                        voice_script = (
                            f"أهلاً بيك يا {sender_name}، سمعتك ومبسوطة إني بتكلم معاك بصوتي!"
                            if is_fem else
                            f"يا مرحب بيك يا {sender_name}، معاك وسامعك وتحت أمرك في أي وقت!"
                        )

                voice_script = voice_script.strip()

                voice_path, waveform, duration = await voice_generator.generate_voice_note(
                    text_content=voice_script,
                    emotional_tone="WARM",
                    format_ext="ogg",
                    dialect_code=bot.primary_dialect or "egyptian",
                    is_singing=is_sing,
                    gender=gender_str,
                    voice_override=getattr(bot, "voice_profile", None),
                    custom_pitch=getattr(bot, "voice_pitch", 0),
                    custom_rate=getattr(bot, "voice_rate", 0),
                    bot_name=bot.name,
                    bot_id=bot.instance_id,
                )

                if voice_path and os.path.exists(voice_path):
                    with open(voice_path, "rb") as vf:
                        res = await http.post(
                            f"{api_url}/sendVoice",
                            data={"chat_id": str(chat_id), "duration": str(duration), "reply_to_message_id": str(message_id)},
                            files={"voice": (os.path.basename(voice_path), vf, "audio/ogg")},
                            timeout=35.0,
                        )
                        if res.status_code == 200:
                            logger.info(f"🎤 [{bot.name} Sent Voice Note] Chat [{chat_id}]: '{voice_script[:40]}...'")
                            if not is_group:
                                from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
                                asyncio.create_task(
                                    live_event_streamer.stream_dm_event(
                                        sender_id=sender_id,
                                        sender_name=sender_name,
                                        user_text=text,
                                        bot_reply=f"🎙️ [رسالة صوتية]: {voice_script}",
                                        persona_name=f"{bot.name} (Sub-Bot)",
                                    )
                                )
                            return
            except Exception as ve:
                logger.error(f"Error handling voice synthesis for sub-bot [{bot.name}]: {ve}")

        # Cognitive Processing with this sub-bot's own Persona
        try:
            from aether_human_core.cognitive_engine.orchestrator import cognitive_orchestrator

            resp = await cognitive_orchestrator.process_incoming_event(
                telegram_message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                message_text=text,
                media_type=media_type,
                chat_type=chat_type,
                chat_title=chat.get("title") or f"محادثة مع {sender_name}",
                extra_system_instruction=combined_prompt,
                target_bot_name=bot.name,
                target_bot_id=bot.instance_id,
                is_userbot=False,
            )

            # Send emoji reaction if recommended
            if getattr(resp, "reaction_emoji", None):
                try:
                    await http.post(
                        f"{api_url}/setMessageReaction",
                        json={
                            "chat_id": chat_id,
                            "message_id": message_id,
                            "reaction": [{"type": "emoji", "emoji": resp.reaction_emoji}],
                        },
                        timeout=5.0,
                    )
                except Exception:
                    pass

            if getattr(resp, "decision_type", "") == "REACT_ONLY":
                return

            reply_text = resp.raw_response_text
            if reply_text:
                # Remove robotic commas for natural flow
                clean_reply = reply_text.replace("،", " ").replace(" ,", " ").replace(",", " ")
                while "  " in clean_reply:
                    clean_reply = clean_reply.replace("  ", " ")
                clean_reply = clean_reply.strip()

                # Enforce strict 150-char maximum length in groups
                if is_group and len(clean_reply) > 150:
                    clean_reply = clean_reply[:150].rsplit(" ", 1)[0] + "..."

                # Simulate typing on sub-bot
                await http.post(f"{api_url}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                await asyncio.sleep(min(max(len(clean_reply.split()) * 0.18, 1.2), 4.0))

                # Send reply via this sub-bot's token
                send_payload = {
                    "chat_id": chat_id,
                    "text": clean_reply,
                    "reply_to_message_id": message_id,
                }
                res = await http.post(f"{api_url}/sendMessage", json=send_payload)
                if res.status_code == 200:
                    logger.info(f"📤 [{bot.name} Sent] Chat [{chat_id}]: '{clean_reply[:50]}...'")

                    if is_group:
                        from bot_factory.group_arbiter import group_arbiter
                        group_arbiter.register_banter_reply(chat_id, bot.instance_id)
                        tease_res = group_arbiter.evaluate_sibling_teasing_trigger(chat_id, bot.instance_id, clean_reply)
                        if tease_res:
                            teasing_bot, tease_text = tease_res
                            asyncio.create_task(self._schedule_sibling_tease(chat_id, message_id, teasing_bot, tease_text))

                    if not is_group:
                        from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer
                        asyncio.create_task(
                            live_event_streamer.stream_dm_event(
                                sender_id=sender_id,
                                sender_name=sender_name,
                                user_text=text,
                                bot_reply=clean_reply,
                                persona_name=f"{bot.name} (Sub-Bot)",
                            )
                        )

                    # Log outgoing message
                    try:
                        from aether_human_core.database.postgres.connection import db_manager
                        from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
                        async with db_manager.session() as db_sess:
                            m_repo = MessageRepository(db_sess)
                            await m_repo.log_message(
                                telegram_message_id=int(time.time() * 1000) % 1000000000,
                                chat_id=chat_id,
                                sender_id=sender_id,
                                text=clean_reply,
                                media_type="text",
                                is_from_bot=True,
                                reply_to_msg_id=message_id,
                            )
                            await db_sess.commit()
                    except Exception:
                        pass
        except Exception as orch_err:
            logger.error(f"Error orchestrating message on sub-bot [{bot.name}]: {orch_err}")

    async def _schedule_sibling_tease(
        self,
        chat_id: int,
        reply_to_msg_id: int,
        teasing_bot: Any,
        tease_text: str,
    ) -> None:
        """
        Delivers realistic teasing / banter from Bot B to Bot A after a human-like delay (4-6s).
        """
        await asyncio.sleep(random.uniform(4.0, 6.0))
        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        from aether_human_core.telegram_client.human_typer import human_typer
        bursts = human_typer.prepare_message_bursts(tease_text, is_group=True)
        if getattr(teasing_bot, "is_userbot", False):
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=reply_to_msg_id,
                is_userbot=True,
            )
        elif getattr(teasing_bot, "bot_id", "") == "master_omar_official":
            await mtproto_manager.dispatch_burst_messages(
                chat_id=chat_id,
                bursts=bursts,
                reply_to_msg_id=reply_to_msg_id,
                is_userbot=False,
            )
        else:
            token = getattr(teasing_bot, "token_or_session", "")
            if token and ":" in token:
                try:
                    http = await self._get_http()
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
                    logger.debug(f"Failed to dispatch sub-bot sibling tease: {ex}")


# Global Dispatcher Singleton
multi_bot_dispatcher = MultiBotPollingDispatcher()
