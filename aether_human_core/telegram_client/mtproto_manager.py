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
import re
import time
from typing import Optional, List, Any, Dict, Tuple
import httpx
from telethon import TelegramClient, events
from telethon.tl.types import (
    DocumentAttributeAudio,
    ReactionEmoji,
)

from aether_human_core.config.settings import settings
from core_config.sovereignty_rules import sovereignty_guard
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
        # Task 2.1: Userbot Read -> Think -> Type state machine tracking
        self._userbot_last_conv_ts: Dict[int, float] = {}
        self._userbot_active_conv_flag: Dict[int, bool] = {}

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
                    asyncio.create_task(self._start_session_keep_alive())
                    # Concurrently initialize the interactive Userbot (Dual Entity Architecture)
                    from bot_factory.interactive_userbot_auth import interactive_userbot
                    interactive_userbot.start_background_init()
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

    async def _start_session_keep_alive(self) -> None:
        """
        Periodically verifies and refreshes Telegram Bot API token & MTProto Userbot session
        to prevent session termination or sudden logouts.
        """
        logger.info("Autonomous Telegram Session Keep-Alive daemon active (Heartbeats every 10m).")
        while self._is_running:
            await asyncio.sleep(600.0)  # Every 10 minutes
            try:
                if self.bot_token:
                    http = await self._get_http()
                    await http.get(f"{self.bot_api_url}/getMe", timeout=10.0)
                if self.client and await self.client.is_user_authorized():
                    from telethon.tl.functions.help import GetConfigRequest
                    await self.client(GetConfigRequest())
                logger.debug("Telegram Session Keep-Alive heartbeat validated successfully.")
            except Exception as e:
                logger.debug(f"Session keep-alive ping notice: {e}")

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
        # Intercept Message Edits (Ghost Anti-Delete / Forensic Auditing)
        if "edited_message" in update or "edited_channel_post" in update:
            em = update.get("edited_message") or update.get("edited_channel_post")
            from admin_telemetry_and_archiver.ghost_anti_delete_catcher import ghost_catcher
            await ghost_catcher.handle_message_edit(
                chat_id=em.get("chat", {}).get("id", 0),
                message_id=em.get("message_id", 0),
                new_text=em.get("text", "") or em.get("caption", ""),
            )
            return

        update_id = update.get("update_id")
        if update_id:
            if not hasattr(self, "_seen_updates"):
                self._seen_updates = set()
            if update_id in self._seen_updates:
                return
            self._seen_updates.add(update_id)
            if len(self._seen_updates) > 2000:
                self._seen_updates.clear()

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
        sender_username = sender.get("username")

        # Anti-Spam Silent Drop Middleware (with Cross-Bot Deduplication)
        from aether_human_core.telegram_client.anti_spam_guard import anti_spam_guard
        if anti_spam_guard.is_spam(sender_id, bot_id="master_omar_official", chat_id=chat_id, message_id=message_id):
            logger.info(f"🚫 [Anti-Spam] Silently dropped spam update from [{sender_id} ({sender_name})].")
            return

        # 0.0 In-Bot BotFather & Factory Admin Wizard / Direct Commands
        try:
            from bot_factory.factory_manager import bot_factory as _bf_mgr
            from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher as _mb_disp
            master_bot_cfg = _bf_mgr.get_bot("master_omar_official")
            if master_bot_cfg and await _mb_disp.handle_in_bot_admin_action_or_command(
                bot=master_bot_cfg,
                msg=msg,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                is_group=(chat_type in ("group", "supergroup")) or (chat_id < 0),
            ):
                return
        except Exception as _bf_err:
            logger.debug(f"Master bot admin wizard check note: {_bf_err}")
        
        # 0. Task 3.2: Deep Multimodal Vision & File Parsing (Stickers, GIFs, Photos, Documents)
        from aether_human_core.telegram_client.handlers.media_handler import media_handler as _mh_vis
        media_type = "text"
        if msg.get("voice") or msg.get("audio"):
            media_type = "voice"
            message_text = "[رسالة صوتية]"
        elif msg.get("sticker") or msg.get("animation") or msg.get("photo") or msg.get("document"):
            http_vis = await self._get_http()
            inspected = await _mh_vis.inspect_bot_api_media(msg, self.bot_token, http_vis)
            if inspected:
                message_text, media_type = inspected
            else:
                message_text = msg.get("text", "") or msg.get("caption", "") or "[وسائط]"
        else:
            message_text = msg.get("text", "") or msg.get("caption", "")

        # 0.5 Unified Immediate Incoming Message Persistence
        try:
            from aether_human_core.database.postgres.connection import db_manager
            from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
            async with db_manager.session() as db_sess:
                m_repo = MessageRepository(db_sess)
                await m_repo.get_or_create_chat(
                    chat_id=chat_id,
                    title=chat.get("title") or sender_name,
                    chat_type=chat_type,
                )
                await m_repo.log_message(
                    telegram_message_id=message_id,
                    chat_id=chat_id,
                    sender_id=sender_id,
                    text=message_text,
                    media_type=media_type,
                    is_from_bot=False,
                    reply_to_msg_id=msg.get("reply_to_message", {}).get("message_id"),
                )
                await db_sess.commit()
        except Exception as persist_err:
            logger.debug(f"Persistence error on incoming msg {message_id}: {persist_err}")

        # Check Puppeteer control command from The King in Forum Supergroup
        reply_to = msg.get("reply_to_message")
        if reply_to and chat_id == settings.admin_telemetry_supergroup_id:
            from admin_telemetry_and_archiver.live_puppeteer_controller import puppeteer_controller
            reply_text = reply_to.get("text", "") or reply_to.get("caption", "")
            puppet_res = await puppeteer_controller.handle_king_control_command(
                sender_id=sender_id,
                replied_text=reply_text,
                command_text=message_text,
            )
            if puppet_res:
                await self.send_message(chat_id=chat_id, text=puppet_res, reply_to_msg_id=message_id)
                return

        # Synchronize live Cloudflare WebApp MenuButton per user to eliminate mobile client caching
        from cloud_and_resource_guard.cloudflare_tunnel_manager import cloudflare_manager
        asyncio.create_task(cloudflare_manager.sync_user_if_needed(sender_id))

        # Command interception (/start, /menu, /panel, /stats, /mood, /admins, /rules, /dialects, /media, /add_admin, /del_admin, /add_rule, /del_rule, /ban_word, /unban_word)
        if message_text.startswith("/"):
            logger.info(f"⚡ [Command Inbound] From [{sender_name} ({sender_id})] in chat [{chat_id}]: '{message_text}'")
            try:
                handled_cmd = await self._handle_command(
                    chat_id=chat_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text,
                    reply_to_msg_id=message_id,
                )
                if handled_cmd:
                    return
            except Exception as cmd_exc:
                logger.error(f"Error executing command '{message_text}': {cmd_exc}", exc_info=True)

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

        reply_to = msg.get("reply_to_message", {})
        reply_to_from = reply_to.get("from", {})
        is_reply_to_me = bool(reply_to and reply_to_from.get("id") == self.bot_id)
        reply_to_other = bool(reply_to and reply_to_from.get("id") and reply_to_from.get("id") != self.bot_id)

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
                        is_reply_to_me=is_reply_to_me,
                    )
                    return

        # 2. Photo request detection
        handled_photo = await media_handler.handle_photo_request(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message_text,
            is_reply_to_me=is_reply_to_me,
            reply_to_other=reply_to_other,
            media_type=media_type,
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
            is_reply_to_me=is_reply_to_me,
            reply_to_other=reply_to_other,
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
                sender_username=sender_username,
                media_type=media_type,
            )

        # 4. Group handling
        elif chat_type in ("group", "supergroup"):
            # Suppress all processing and loops if message is inside the King's Telemetry Supergroup
            if chat_id == settings.admin_telemetry_supergroup_id:
                logger.debug("Suppressing group_handler for message originating in Telemetry Supergroup.")
                return

            chat_title = chat.get("title", "جروب عام")
            reply_to = msg.get("reply_to_message", {})
            reply_from = reply_to.get("from", {})
            is_reply = False
            is_reply_to_other = False
            if reply_from:
                our_bot_id = getattr(self, "bot_id", 8677519723)
                if reply_from.get("id") == our_bot_id:
                    is_reply = True
                else:
                    # User replied to another member or another bot (like Batman)!
                    is_reply_to_other = True

            bot_tag = f"@{getattr(self, 'bot_username', 'omarggforbot')}".lower()
            is_tagged = bot_tag in message_text.lower()
            reply_to_msg_id = reply_to.get("message_id") if reply_to else None
            reply_to_from_id = reply_from.get("id") if reply_from else None

            await group_handler.handle_group_message(
                message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_gender=sender_gender,
                message_text=message_text,
                chat_title=chat_title,
                is_reply_to_bot=is_reply,
                is_reply_to_other=is_reply_to_other,
                is_bot_mentioned=is_tagged,
                sender_username=sender_username,
                target_bot_name="عمر",
                target_bot_id="master_omar_official",
                reply_to_msg_id=reply_to_msg_id,
                reply_to_from_id=reply_to_from_id,
                media_type=media_type,
            )

    # =========================================================================
    # Task 2.1: Realistic Human Read -> Think -> Type State Machine Helpers
    # =========================================================================

    DEAD_END_SINGLE_PHRASES = {
        "ماشي", "ماشى", "تمام", "اوك", "أوك", "اوكي", "أوكي", "ok", "okay", "k", "kk",
        "طيب", "خلاص", "فل", "قشطه", "قشطة", "حاضر", "تمام ماشي", "ماشي تمام",
        "اوك تمام", "طيب ماشي", "خلاص ماشي", "تمام يسطا", "ماشي يسطا", "اشطا", "أشطا",
        "👍", "👌", "🤝", "🙏",
    }

    def compute_userbot_phase1_unseen_delay(self, chat_id: int, sender_id: int) -> Tuple[float, bool]:
        """
        Phase 1 — Variable Unseen Delay (Before ✓✓ Seen):
        - If Userbot is already in an active rapid conversation with this user (last message < 2 mins ago),
          wait 2–8 seconds before marking Seen.
        - If this is a new message or Userbot was idle/busy, wait a realistic random delay (15 to 90 seconds,
          configurable via settings) before calling client.send_read_acknowledge().
        """
        now = time.time()
        last_ts = self._userbot_last_conv_ts.get(chat_id, 0.0)
        elapsed = now - last_ts
        is_active_rapid = (last_ts > 0.0 and elapsed < 120.0)
        self._userbot_active_conv_flag[chat_id] = is_active_rapid

        if is_active_rapid:
            delay = random.uniform(2.0, 8.0)
            return delay, True

        idle_min = float(getattr(settings, "userbot_idle_unseen_min_sec", 15.0))
        idle_max = float(getattr(settings, "userbot_idle_unseen_max_sec", 90.0))
        # Scale slightly shorter if Creator (KING_USER_ID) is messaging while idle, still within 15-30s realistic window
        if sovereignty_guard.is_the_king(sender_id) or (settings.the_king_user_id and sender_id == settings.the_king_user_id):
            delay = random.uniform(idle_min, min(30.0, idle_max))
        else:
            delay = random.uniform(idle_min, idle_max)
        return delay, False

    def compute_userbot_phase2_think_delay(self, message_text: str, sender_id: int, chat_id: int = 0) -> float:
        """
        Phase 2 — Human Thinking Pause (After ✓✓ Seen, Before Typing...):
        Once Seen (✓✓) is marked, wait a realistic reading & thinking pause of 15 to 75 seconds
        scaled by message complexity, urgency, and current mood.
        """
        think_min = float(getattr(settings, "userbot_think_min_sec", 15.0))
        think_max = float(getattr(settings, "userbot_think_max_sec", 75.0))

        text_clean = (message_text or "").strip()
        words_cnt = len(text_clean.split())

        # Check urgency or Creator priority
        urgent_keywords = ["بسرعة", "بسرعه", "ضروري", "عاجل", "الحقني", "الحقيني", "فوراً", "فورا", "طارئ"]
        is_urgent = (sovereignty_guard.is_the_king(sender_id) or (settings.the_king_user_id and sender_id == settings.the_king_user_id)) or any(uk in text_clean.lower() for uk in urgent_keywords)

        if is_urgent:
            base_think = random.uniform(think_min, min(24.0, think_max))
        elif words_cnt <= 5:
            base_think = random.uniform(think_min, min(32.0, think_max))
        elif words_cnt <= 18:
            base_think = random.uniform(max(think_min, 22.0), min(50.0, think_max))
        else:
            base_think = random.uniform(max(think_min, 35.0), think_max)

        # Mood scaling from endocrine engine
        try:
            from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
            h = endocrine_engine.get_current_state()
            if h.cortisol > 0.65 or h.serotonin < 0.35:
                # Tired or annoyed -> thinks/hesitates longer before typing
                base_think = min(think_max, base_think * 1.25)
            elif h.dopamine > 0.72:
                # Excited/energetic -> towards the quicker end of 15-75s
                base_think = max(think_min, base_think * 0.85)
        except Exception:
            pass

        return round(max(think_min, min(think_max, base_think)), 2)

    def evaluate_selective_reply_filter(
        self,
        message_text: str,
        media_type: str,
        sender_id: int,
        is_active_conv: bool,
    ) -> Tuple[bool, Optional[str]]:
        """
        Task 2.1 (4) — Selective Human Reply Filter (Not Obligated to Reply to Everything):
        If a user sends a dead-end message ('ماشي', 'تمام', 'اوك', or a random sticker after an
        active/finished exchange), Userbot can mark it Seen (✓✓) or leave a single reaction (👍)
        and choose NOT to reply.
        Returns: (should_skip_text_reply, optional_reaction_emoji)
        """
        raw = (message_text or "").strip()
        if not raw and media_type == "text":
            return True, None

        # Never skip questions, slash commands, or media requests
        if "?" in raw or "؟" in raw or raw.startswith("/"):
            return False, None

        norm = (
            raw.lower()
            .replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            .replace("ة", "ه").replace("ى", "ي")
        )
        norm_stripped = re.sub(r"[.!،,؟?~…]+", "", norm).strip()

        # Never skip if user explicitly calls the bot by name or asks for photo/voice
        must_reply_tokens = ["عمر", "ريمي", "gg", "جي جي", "صور", "صوت", "ريكورد", "فويس", "احكي", "قولي", "رايك"]
        if any(tok in norm_stripped for tok in must_reply_tokens):
            return False, None

        # Case A: Dead-end short closure phrase ('تمام', 'ماشي', 'اوك', etc.)
        if norm_stripped in self.DEAD_END_SINGLE_PHRASES:
            # 65% leave a casual reaction (👍 / 👌 / ❤️), 35% pure Seen (✓✓)
            emoji = random.choice(["👍", "👌", "❤️", None, None])
            return True, emoji

        # Case B: Random sticker after an already active/wrapping conversation
        if media_type == "sticker" and is_active_conv:
            if random.random() < 0.55:
                emoji = random.choice(["😂", "❤️", "👍", None])
                return True, emoji

        return False, None

    def _register_telethon_handlers(self) -> None:
        """
        Registers event handlers on active Telethon client.
        Passes exact client instance, target bot profile, and is_userbot=True
        to ensure replies and typing states originate strictly from the Userbot account.
        """
        if not self.client:
            return

        @self.client.on(events.NewMessage(incoming=True))
        async def on_new_message(event):
            sender = await event.get_sender()
            sender_id = event.sender_id
            sender_name = getattr(sender, "first_name", "صديق") or "صديق"
            chat_id = event.chat_id

            # Anti-Spam Silent Drop Middleware (with Cross-Bot Deduplication)
            from aether_human_core.telegram_client.anti_spam_guard import anti_spam_guard
            if anti_spam_guard.is_spam(sender_id, bot_id="userbot_gg", chat_id=chat_id, message_id=event.id):
                logger.info(f"🚫 [Anti-Spam] Silently dropped spam message on Userbot from [{sender_id} ({sender_name})].")
                return

            sender_gender = "female" if sender_name in ("سارة", "نورا", "حبيبتي") else "unknown"
            msg_text = event.raw_text or ""
            media_type = "text"

            # Task 3.2: Deep Multimodal Vision & File Parsing in Telethon Userbot
            from aether_human_core.telegram_client.handlers.media_handler import media_handler as _ub_mh_vis
            if getattr(event, "voice", None) or getattr(event, "audio", None):
                media_type = "voice"
                msg_text = "[رسالة صوتية]"
            elif getattr(event, "sticker", None) or getattr(event, "gif", None) or getattr(event, "photo", None) or getattr(event, "document", None):
                inspected_ub = await _ub_mh_vis.inspect_telethon_media(event)
                if inspected_ub:
                    msg_text, media_type = inspected_ub
                elif getattr(event, "sticker", None):
                    sticker_emoji = getattr(getattr(event, "file", None), "emoji", "") or "✨"
                    msg_text = f"[ملصق تعبيري: {sticker_emoji}]"
                    media_type = "sticker"
                elif getattr(event, "photo", None):
                    media_type = "photo"
                    msg_text = msg_text or "[صورة]"

            # Pull current Telethon userbot identity dynamically
            try:
                me = await self.client.get_me()
                userbot_id = getattr(me, "id", 0)
                userbot_name = getattr(me, "first_name", "Gg") or "Gg"
            except Exception:
                userbot_id = 0
                userbot_name = "Gg"

            # Persist incoming userbot message
            try:
                from aether_human_core.database.postgres.connection import db_manager
                from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
                async with db_manager.session() as db_sess:
                    m_repo = MessageRepository(db_sess)
                    await m_repo.get_or_create_chat(
                        chat_id=event.chat_id,
                        title=sender_name if event.is_private else "جروب",
                        chat_type="private" if event.is_private else "supergroup",
                    )
                    await m_repo.log_message(
                        telegram_message_id=event.id,
                        chat_id=event.chat_id,
                        sender_id=sender_id,
                        text=msg_text,
                        media_type=media_type,
                        is_from_bot=False,
                        reply_to_msg_id=getattr(event, "reply_to_msg_id", None),
                    )
                    await db_sess.commit()
            except Exception as ub_p_err:
                logger.debug(f"Persistence error on userbot incoming: {ub_p_err}")

            from aether_human_core.telegram_client.handlers.dm_handler import dm_handler
            from aether_human_core.telegram_client.handlers.group_handler import group_handler
            from aether_human_core.telegram_client.handlers.media_handler import media_handler

            # 0.9 Task 4.2: If Bot Arena is active in this group, handle sibling/owner messages immediately
            if event.is_group:
                from bot_factory.sibling_bot_network import sibling_network as _ub_sbn
                from bot_factory.group_arbiter import group_arbiter as _ub_ga
                _ub_ga.record_presence(event.chat_id, f"userbot_{userbot_id or 8656468004}")
                if _ub_sbn.is_arena_active(event.chat_id):
                    if _ub_sbn.is_server_sibling(sender_id):
                        # Another sibling bot spoke in the Arena; mark seen briefly and don't trigger normal handler
                        return
                    is_king_ub = (sender_id == settings.the_king_user_id) or (sender_id in settings.super_admin_ids_list)
                    if is_king_ub and _ub_sbn.is_arena_stop_phrase(msg_text):
                        if _ub_sbn.try_claim_arena_command(event.chat_id, event.id):
                            await _ub_sbn.stop_bot_arena(event.chat_id, reason="أمر إيقاف نصي من المطور")
                            await self.send_message(event.chat_id, "🛑 تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑", reply_to_msg_id=event.id)
                        return
                    _ub_sbn.record_arena_human_interjection(
                        chat_id=event.chat_id,
                        message_id=event.id,
                        sender_id=sender_id,
                        sender_name=sender_name,
                        message_text=msg_text,
                        is_owner=is_king_ub,
                    )
                    return

            # 1. Task 2.1 Phase 1 — Variable Unseen Delay before marking ✓✓ Seen
            if event.is_private:
                unseen_delay, is_active_conv = self.compute_userbot_phase1_unseen_delay(event.chat_id, sender_id)
            else:
                # In groups, mark seen within 2-8s if active or 5-18s if idle so group turn election stays natural
                last_g_ts = self._userbot_last_conv_ts.get(event.chat_id, 0.0)
                is_active_conv = (time.time() - last_g_ts) < 120.0
                unseen_delay = random.uniform(2.0, 6.0) if is_active_conv else random.uniform(5.0, 15.0)

            logger.info(
                f"⏳ [Userbot Phase 1: Unseen Delay] Waiting {unseen_delay:.1f}s before ✓✓ Seen "
                f"in chat [{event.chat_id}] (active_conv={is_active_conv}, Msg ID: {event.id})..."
            )
            await asyncio.sleep(unseen_delay)
            from telethon import functions
            try:
                await self.client.send_read_acknowledge(event.chat_id, max_id=event.id)
                logger.info(f"✓✓ [Userbot Phase 1: Seen] Marked Seen via send_read_acknowledge for chat [{event.chat_id}] (Msg ID: {event.id})")
            except Exception:
                try:
                    await self.client(functions.messages.ReadHistoryRequest(peer=event.chat_id, max_id=event.id))
                    logger.info(f"✓✓ [Userbot Phase 1: Seen] Marked Seen via ReadHistoryRequest for chat [{event.chat_id}] (Msg ID: {event.id})")
                except Exception as rx:
                    logger.debug(f"ReadHistoryRequest notice: {rx}")

            self._userbot_last_conv_ts[event.chat_id] = time.time()

            # 1.5 Task 2.1 (4) — Selective Human Reply Filter for dead-end messages in private chat
            if event.is_private:
                skip_reply, react_emoji = self.evaluate_selective_reply_filter(
                    message_text=msg_text,
                    media_type=media_type,
                    sender_id=sender_id,
                    is_active_conv=is_active_conv,
                )
                if skip_reply:
                    if react_emoji:
                        await asyncio.sleep(random.uniform(1.5, 4.0))
                        await self.send_reaction(
                            chat_id=event.chat_id,
                            message_id=event.id,
                            emoji=react_emoji,
                            is_userbot=True,
                            userbot_client=self.client,
                        )
                    logger.info(
                        f"🤫 [Userbot Selective Reply Filter] Dead-end message '{msg_text[:30]}' from [{sender_name}] "
                        f"left on ✓✓ Seen (reaction={react_emoji}) without text reply."
                    )
                    return

            # 2. Emotional Ghosting is COMPLETELY DISABLED per architectural sovereignty rules:
            # All genuine user messages must receive an authentic, human reply without being dropped.

            if event.is_private:
                # Check photo request with Userbot Gg identity
                is_photo_req = await media_handler.handle_photo_request(
                    message_id=event.id,
                    chat_id=sender_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=msg_text,
                    is_userbot=True,
                    persona_name="Gg",
                    gender="female",
                    userbot_client=self.client,
                    media_type=media_type,
                )
                if is_photo_req:
                    return

                # Check voice note request with strict Userbot transport
                is_voice_req = await media_handler.handle_voice_request(
                    message_id=event.id,
                    chat_id=sender_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=msg_text,
                    is_userbot=True,
                    userbot_client=self.client,
                    target_bot_name=userbot_name,
                )
                if is_voice_req:
                    return

                await dm_handler.handle_dm_message(
                    message_id=event.id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_gender=sender_gender,
                    message_text=msg_text,
                    is_userbot=True,
                    userbot_client=self.client,
                    target_bot_name=userbot_name,
                    target_bot_id=f"userbot_{userbot_id}",
                    media_type=media_type,
                )

            elif event.is_group:
                if event.chat_id == settings.admin_telemetry_supergroup_id:
                    return
                chat = await event.get_chat()
                title = getattr(chat, "title", "جروب عام")

                is_reply_to_our_bot = False
                is_reply_to_other = False
                reply_to_msg_id = None
                reply_to_from_id = None
                if event.is_reply:
                    try:
                        reply_msg = await event.get_reply_message()
                        if reply_msg:
                            reply_to_msg_id = reply_msg.id
                            reply_to_from_id = getattr(reply_msg, "sender_id", None)
                            if reply_to_from_id == userbot_id or getattr(reply_msg, "out", False):
                                is_reply_to_our_bot = True
                            else:
                                is_reply_to_other = True
                    except Exception:
                        pass

                await group_handler.handle_group_message(
                    message_id=event.id,
                    chat_id=event.chat_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_gender=sender_gender,
                    message_text=msg_text,
                    chat_title=title,
                    is_reply_to_bot=is_reply_to_our_bot,
                    is_reply_to_other=is_reply_to_other,
                    is_bot_mentioned=(userbot_name in msg_text or "عمر" in msg_text),
                    is_userbot=True,
                    userbot_client=self.client,
                    target_bot_name=userbot_name,
                    target_bot_id=f"userbot_{userbot_id}",
                    reply_to_msg_id=reply_to_msg_id,
                    reply_to_from_id=reply_to_from_id,
                    media_type=media_type,
                )

        # Wire raw VoIP incoming call interception directly on Telethon client
        from telethon import types
        from live_voip_call_engine.call_signaling_interceptor import call_signaling_interceptor
        from live_voip_call_engine.full_duplex_pipeline import full_duplex_pipeline

        @self.client.on(events.Raw(types=[types.UpdatePhoneCall, types.UpdatePhoneCallSignalingData]))
        async def on_raw_phone_call(update):
            if isinstance(update, types.UpdatePhoneCallSignalingData):
                asyncio.create_task(full_duplex_pipeline.handle_signaling_data(update.phone_call_id, update.data))
                return

            call = getattr(update, "phone_call", None)
            if not call:
                return

            if isinstance(call, types.PhoneCallRequested):
                logger.info(f"📞 Incoming Telethon VoIP phone call detected: ID={call.id}, Video={getattr(call, 'video', False)}")
                asyncio.create_task(call_signaling_interceptor.handle_incoming_telethon_call(self.client, call))
            elif isinstance(call, types.PhoneCall):
                logger.info(f"📞 VoIP PhoneCall active/connected update: ID={call.id}")
                asyncio.create_task(full_duplex_pipeline.handle_phone_call_connected(call, self.client))
            elif isinstance(call, types.PhoneCallDiscarded):
                logger.info(f"📞 VoIP PhoneCall discarded/ended: ID={call.id} (Reason: {getattr(call, 'reason', None)})")
                asyncio.create_task(full_duplex_pipeline.handle_phone_call_ended(call.id))

    async def send_typing_indicator(
        self,
        chat_id: int,
        duration_sec: float,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
    ) -> None:
        """
        Broadcasts human typing indicator proportional to response length.
        Enforces Telethon Userbot transport when called for userbot.
        """
        max_cap = 25.0 if (is_userbot or userbot_client is not None) else 6.0
        sleep_dur = max(0.8, min(duration_sec, max_cap))
        if self._mock_mode:
            logger.debug(f"[Simulation] Typing in chat {chat_id} for {sleep_dur}s...")
            await asyncio.sleep(min(sleep_dur, 2.0))
            return

        if is_userbot or userbot_client is not None:
            active = userbot_client or self.client
            if active:
                try:
                    from telethon import functions, types
                    remaining = sleep_dur
                    while remaining > 0:
                        try:
                            await active(
                                functions.messages.SetTypingRequest(
                                    peer=chat_id,
                                    action=types.SendMessageTypingAction(),
                                )
                            )
                        except Exception:
                            pass
                        step = min(4.0, remaining)
                        await asyncio.sleep(step)
                        remaining -= step
                except Exception as exc:
                    logger.debug(f"Telethon typing action exception: {exc}")
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                )
                await asyncio.sleep(sleep_dur)
            except Exception as exc:
                logger.debug(f"Typing action exception: {exc}")
        elif self.client:
            try:
                async with self.client.action(chat_id, "typing"):
                    await asyncio.sleep(sleep_dur)
            except Exception as exc:
                logger.debug(f"Telethon typing action exception: {exc}")

    async def mark_seen(
        self,
        chat_id: int,
        max_id: int,
        delay_sec: float = 2.0,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
    ) -> None:
        """
        Simulates delayed read receipt (Seen) and dispatches real MTProto ReadHistoryRequest.
        """
        await asyncio.sleep(delay_sec)
        active = userbot_client or self.client
        if active and (is_userbot or userbot_client is not None):
            from telethon import functions
            try:
                await active(functions.messages.ReadHistoryRequest(peer=chat_id, max_id=max_id))
                logger.info(f"✓✓ Seen marked via MTProto for chat [{chat_id}] (Msg ID: {max_id}).")
            except Exception as rx:
                logger.debug(f"ReadHistoryRequest exception: {rx}")
        else:
            logger.debug(f"Simulated read receipt in chat [{chat_id}] (Msg ID: {max_id}).")

    ALLOWED_BOT_REACTION_EMOJIS = {
        "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢",
        "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊️", "🤡", "🥱", "🥴", "😍", "🐳",
        "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓",
        "🍾", "🍿", "☕", "🍸"
    }

    async def send_reaction(
        self,
        chat_id: int,
        message_id: int,
        emoji: str,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
    ) -> None:
        """
        Attaches emoji reaction to a message.
        Routes to Telethon when is_userbot=True, avoiding Bot API 400 Bad Request.
        """
        target_emoji = emoji
        if target_emoji not in self.ALLOWED_BOT_REACTION_EMOJIS:
            # Smart fallback mapping for unsupported emojis
            fallback_map = {
                "👀": "🤔", "🗿": "😐", "✨": "🔥", "🤍": "❤️", "🖤": "💔", "🤝": "👍"
            }
            target_emoji = fallback_map.get(emoji, "👍" if emoji not in ("💔", "👎") else "💔")

        if self._mock_mode:
            logger.info(f"[Simulation] Reacted with '{target_emoji}' to msg {message_id} in chat {chat_id}.")
            return

        if is_userbot or userbot_client is not None:
            active = userbot_client or self.client
            if active:
                try:
                    from telethon import functions, types
                    await active(
                        functions.messages.SendReactionRequest(
                            peer=chat_id,
                            msg_id=message_id,
                            reaction=[types.ReactionEmoji(emoticon=target_emoji)],
                        )
                    )
                    logger.info(f"Attached Userbot reaction '{target_emoji}' to msg [{message_id}] in chat [{chat_id}].")
                except Exception as exc:
                    logger.debug(f"Userbot reaction exception: {exc}")
            return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/setMessageReaction",
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reaction": [{"type": "emoji", "emoji": target_emoji}],
                    },
                )
                logger.info(f"Attached reaction '{target_emoji}' to message [{message_id}] in chat [{chat_id}].")
            except Exception as exc:
                logger.debug(f"Bot reaction not supported or chat too restricted: {exc}")
        elif self.client:
            try:
                from telethon import functions, types
                await self.client(
                    functions.messages.SendReactionRequest(
                        peer=chat_id,
                        msg_id=message_id,
                        reaction=[types.ReactionEmoji(emoticon=target_emoji)],
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
        text, markup, alert, trigger = await telegram_menu.handle_callback(data, user_id, user_name, chat_id=chat_id)

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
                    "reply_markup": self.sanitize_markup_for_chat(markup, chat_id) if markup else {},
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
            from cloud_and_resource_guard.cloudflare_tunnel_manager import cloudflare_manager
            asyncio.create_task(cloudflare_manager.sync_telegram_menu_button(specific_user_id=sender_id))
            text, markup = await telegram_menu.render_main_dashboard(sender_id, user_name=sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/webapp", "/app", "/game", "/mini_app", "/تطبيق"):
            from cloud_and_resource_guard.cloudflare_tunnel_manager import cloudflare_manager
            asyncio.create_task(cloudflare_manager.sync_telegram_menu_button(specific_user_id=sender_id))
            text, markup = await telegram_menu.render_webapp_panel()
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        # ==========================================
        # Interactive Telethon Userbot Authentication & Management
        # ==========================================
        elif cmd in ("/otp", "/code", "/كود"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام فقط 👑", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/otp &lt;الكود&gt; [كلمة_المرور_2FA]</code>", {}, reply_to_msg_id)
                return True
            code = parts[1]
            password = parts[2] if len(parts) > 2 else None
            ok, msg = await interactive_userbot.submit_otp(code=code, password=password)
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        elif cmd in ("/2fa", "/password"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام فقط 👑", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/2fa &lt;كلمة_المرور&gt;</code>", {}, reply_to_msg_id)
                return True
            ok, msg = await interactive_userbot.submit_2fa(password=parts[1])
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        elif cmd in ("/auth_userbot", "/login_userbot", "/تفعيل_يوزربوت"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام فقط 👑", {}, reply_to_msg_id)
                return True
            phone = parts[1] if len(parts) > 1 else settings.telegram_phone_number
            if not phone:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/auth_userbot +22602269964</code>", {}, reply_to_msg_id)
                return True
            ok, msg = await interactive_userbot.request_phone_code(phone=phone, notify_king=True)
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        elif cmd in ("/userbot_name", "/اسم_اليوزربوت"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام فقط 👑", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/userbot_name &lt;الاسم الجديد&gt;</code>", {}, reply_to_msg_id)
                return True
            new_name = " ".join(parts[1:])
            ok, msg = await interactive_userbot.update_profile(first_name=new_name)
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        elif cmd in ("/userbot_bio", "/بايو_اليوزربوت"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام فقط 👑", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/userbot_bio &lt;الوصف الجديد&gt;</code>", {}, reply_to_msg_id)
                return True
            new_bio = " ".join(parts[1:])
            ok, msg = await interactive_userbot.update_profile(about=new_bio)
            await self.send_message_with_keyboard(chat_id, msg, {}, reply_to_msg_id)
            return True

        elif cmd in ("/userbot_stats", "/احصائيات_اليوزربوت"):
            from bot_factory.interactive_userbot_auth import interactive_userbot
            stats = await interactive_userbot.get_stats()
            if not stats.get("active"):
                await self.send_message_with_keyboard(chat_id, f"⚠️ <b>حالة اليوزربوت:</b> {stats.get('status', 'غير متصل')}", {}, reply_to_msg_id)
                return True
            resp = (
                f"🤖 <b>إحصائيات حساب اليوزربوت الحي</b> ⚡\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>الاسم:</b> <b>{stats['first_name']} {stats['last_name']}</b>\n"
                f"🆔 <b>الأيدي:</b> <code>{stats['user_id']}</code>\n"
                f"📱 <b>الرقم:</b> <code>{stats['phone']}</code>\n"
                f"🏷️ <b>المعرف:</b> @{stats['username']}\n"
                f"💬 <b>إجمالي المحادثات:</b> {stats['total_dialogs']}\n"
                f"👥 <b>الجروبات:</b> {stats['groups_count']}\n"
                f"📢 <b>القنوات:</b> {stats['channels_count']}\n"
                f"📩 <b>الخاص:</b> {stats['dms_count']}\n"
                f"🟢 <b>الحالة:</b> {stats['status']}"
            )
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # ==========================================
        # Multi-Tenant Isolated Sandbox Persona Commands
        # ==========================================
        elif cmd in ("/persona", "/my_persona", "/شخصيتي"):
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/set_name", "/اسم_شخصيتي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/set_name سارة</code>", {}, reply_to_msg_id)
                return True
            p_name = " ".join(parts[1:])
            persona_virtualizer.update_persona(sender_id, persona_name=p_name)
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, f"✅ تم تغيير اسم شخصية البوت في الخاص إلى: <b>{p_name}</b>!", markup, reply_to_msg_id)
            return True

        elif cmd in ("/set_gender", "/نوع_شخصيتي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            if len(parts) < 2 or parts[1].lower() not in ("male", "female", "ولد", "بنت"):
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/set_gender female</code> أو <code>male</code>", {}, reply_to_msg_id)
                return True
            g = "female" if parts[1].lower() in ("female", "بنت") else "male"
            persona_virtualizer.update_persona(sender_id, gender=g)
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, f"✅ تم تحويل جنس الشخصية إلى: <b>{'بنت 👧' if g == 'female' else 'ولد 👦'}</b>!", markup, reply_to_msg_id)
            return True

        elif cmd in ("/set_dialect", "/لهجة_شخصيتي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            if len(parts) < 2:
                text, markup = await telegram_menu.render_persona_dialects_menu(sender_id)
                await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
                return True
            dia = parts[1].lower()
            persona_virtualizer.update_persona(sender_id, dialect=dia)
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, f"✅ تم ضبط اللهجة إلى: <b>{dia}</b> بنجاح!", markup, reply_to_msg_id)
            return True

        elif cmd in ("/set_prompt", "/توجيه_شخصيتي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/set_prompt خليك دكتور نفسي وتكلم بهدوء وحنية</code>", {}, reply_to_msg_id)
                return True
            custom_p = " ".join(parts[1:])
            persona_virtualizer.update_persona(sender_id, custom_system_prompt=custom_p)
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, "✅ تم حفظ التوجيه المخصص لشخصيتك بنجاح!", markup, reply_to_msg_id)
            return True

        elif cmd in ("/clone_style", "/استنساخ_اسلوبي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            from multi_tenant_sandbox.linguistic_dna_cloner import linguistic_cloner
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/clone_style [الصق فقرة من محادثاتك أو رسائلك المعتادة]</code>", {}, reply_to_msg_id)
                return True
            sample_text = " ".join(parts[1:])
            dna = linguistic_cloner.analyze_and_clone(sample_text)
            persona_virtualizer.attach_linguistic_dna(sender_id, dna)
            text, markup = await telegram_menu.render_my_persona_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, "🧬 تم استخراج وتحليل بصمتك اللغوية ودمجها مع شخصية البوت معك بنجاح!", markup, reply_to_msg_id)
            return True

        # ==========================================
        # Custom Commands (Multi-Tenant Sandbox)
        # ==========================================
        elif cmd in ("/add_cmd", "/اضف_امر"):
            from multi_tenant_sandbox.custom_command_compiler import custom_commands
            if len(parts) < 3:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/add_cmd /الكلمة الرد الذي تريده</code>", {}, reply_to_msg_id)
                return True
            trig = parts[1]
            resp = " ".join(parts[2:])
            custom_commands.register_command(sender_id, trig, resp)
            text, markup = await telegram_menu.render_my_commands_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, f"✅ تم حفظ أمرك المخصص: <code>{trig}</code> بنجاح!", markup, reply_to_msg_id)
            return True

        elif cmd in ("/del_cmd", "/احذف_امر"):
            from multi_tenant_sandbox.custom_command_compiler import custom_commands
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "⚠️ الاستخدام: <code>/del_cmd /الكلمة</code>", {}, reply_to_msg_id)
                return True
            trig = parts[1]
            ok = custom_commands.delete_command(sender_id, trig)
            text, markup = await telegram_menu.render_my_commands_panel(sender_id)
            msg = f"✅ تم حذف الأمر <code>{trig}</code>!" if ok else f"⚠️ الأمر <code>{trig}</code> غير موجود."
            await self.send_message_with_keyboard(chat_id, msg, markup, reply_to_msg_id)
            return True

        elif cmd in ("/commands", "/my_commands", "/اوامري"):
            text, markup = await telegram_menu.render_my_commands_panel(sender_id)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        # ==========================================
        # Group & Direct Chat Games
        # ==========================================
        elif cmd in ("/games", "/play", "/العاب", "/الالعاب"):
            from aether_human_core.telegram_client.handlers.group_games_handler import group_games
            text, markup = group_games.render_games_lobby(sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/xo", "/اكس_او"):
            from aether_human_core.telegram_client.handlers.group_games_handler import group_games
            text, markup = group_games.start_xo_game(chat_id, sender_id, sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/trivia", "/سؤال", "/مسابقة"):
            from aether_human_core.telegram_client.handlers.group_games_handler import group_games
            text, markup = group_games.start_trivia_question(sender_name)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/rps", "/حجرة"):
            text = (
                f"✊✋✌️ <b>تحدي حجرة ورقة مقص ضد عُـمـر!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"اختر حركتك بذكاء يا <b>{sender_name}</b> وسأكشف حركتي فوراً:"
            )
            buttons = [
                [
                    {"text": "🪨 حجرة", "callback_data": "rps:rock", "style": "primary"},
                    {"text": "📄 ورقة", "callback_data": "rps:paper", "style": "primary"},
                    {"text": "✂️ مقص", "callback_data": "rps:scissors", "style": "primary"},
                ],
                [{"text": "🔙 ساحة الألعاب 🎮", "callback_data": "menu:games", "style": "danger"}],
            ]
            await self.send_message_with_keyboard(chat_id, text, {"inline_keyboard": buttons}, reply_to_msg_id)
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

        # OSINT Search Command (/u_search) - Admin & King
        elif cmd in ("/u_search", "/osint", "/whois"):
            if not await admin_manager.is_admin(sender_id):
                await self.send_message_with_keyboard(chat_id, "🚫 عذراً، الوصول لملفات OSINT مقتصر على الأدمنز والملك فقط.", {}, reply_to_msg_id)
                return True
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/u_search &lt;user_id | @username&gt;</code>", {}, reply_to_msg_id)
                return True
            from admin_telemetry_and_archiver.osint_search_and_filter_engine import osint_engine
            target = parts[1]
            dossier = await osint_engine.generate_user_dossier(target)
            await self.send_message_with_keyboard(chat_id, dossier, {}, reply_to_msg_id)
            return True


        elif cmd in ("/bots_chat", "/حوار", "/bot_arena", "/ساحة_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                await self.send_message_with_keyboard(chat_id, "🚫 هذا الأمر مخصص لمالك النظام (ECENN) فقط 👑", {}, reply_to_msg_id)
                return True
            if not sibling_network.try_claim_arena_command(chat_id, reply_to_msg_id):
                return True
            custom_topic = message_text[len(parts[0]):].strip()
            if custom_topic:
                sibling_network.set_arena_topic(chat_id, custom_topic)
            text, markup = await telegram_menu.render_bot_arena_panel(user_id=sender_id, chat_id=chat_id)
            await self.send_message_with_keyboard(chat_id, text, markup, reply_to_msg_id)
            return True

        elif cmd in ("/stop_chat", "/ايقاف_الحوار"):
            from bot_factory.sibling_bot_network import sibling_network
            if sender_id != settings.the_king_user_id and sender_id not in settings.super_admin_ids_list:
                return True
            if not sibling_network.try_claim_arena_command(chat_id, reply_to_msg_id):
                return True
            stopped = await sibling_network.stop_bot_arena(chat_id, reason="أمر /stop_chat من المطور")
            if not stopped and chat_id > 0:
                # If sent in DM, stop all active arena sessions across groups
                for active_cid in list(sibling_network._arena_sessions.keys()):
                    if await sibling_network.stop_bot_arena(active_cid, reason="أمر /stop_chat من الخاص"):
                        stopped = True
            msg_txt = (
                "🛑 <b>تم إيقاف حوار البوتات فوراً بأمرك يا كبير! 👑</b>"
                if stopped
                else "ℹ️ <b>لا يوجد حوار بوتات نشط حالياً لإيقافه.</b>"
            )
            await self.send_message_with_keyboard(chat_id, msg_txt, {}, reply_to_msg_id)
            return True

        # Multi-Persona Debate Engine (/debate)
        elif cmd in ("/debate", "/مناظرة"):
            topic = message_text[len(parts[0]):].strip()
            if not topic:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/debate موضوع المناظرة أو المحاضرة</code>", {}, reply_to_msg_id)
                return True
            from multi_tenant_sandbox.multi_persona_debate import persona_debate_engine
            await self.send_message(chat_id, f"🎙️ جاري تجهيز حلبة النقاش والمناظرة حول: <b>{topic}</b>...")
            turns = await persona_debate_engine.generate_debate(topic=topic)
            formatted_turns = "\n\n".join(f"🗣️ <b>{t['speaker']}:</b>\n{t['text']}" for t in turns)
            resp = f"🎭 <b>غرفة المناظرة الفكرية المزدوجة</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n{formatted_turns}"
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # Custom Sandbox Command Registration (/custom)
        elif cmd in ("/custom", "/set_cmd"):
            if len(parts) < 3:
                help_msg = (
                    "ℹ️ <b>تسجيل أمر خاص بك في مساحتك الخاصة:</b>\n"
                    "<code>/custom &lt;الكلمة_أو_الأمر&gt; &lt;الرد المطلوب&gt;</code>\n"
                    "<i>يعمل فقط معك في الشات الخاص دون أن يراه أو يستخدمه أي شخص آخر.</i>"
                )
                await self.send_message_with_keyboard(chat_id, help_msg, {}, reply_to_msg_id)
                return True
            from multi_tenant_sandbox.custom_command_compiler import custom_commands
            trigger = parts[1]
            response_text = message_text.split(parts[1], 1)[1].strip()
            custom_commands.register_command(user_id=sender_id, trigger=trigger, response=response_text)
            resp = f"✨ <b>تم حفظ أمرك الخاص بنجاح:</b>\nعندما تكتب <code>{trigger}</code> في الخاص، سيرد عليك فوراً بـ:\n<blockquote>{response_text}</blockquote>"
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # List Custom Commands (/my_commands)
        elif cmd in ("/my_commands", "/اوامري"):
            from multi_tenant_sandbox.custom_command_compiler import custom_commands
            user_cmds = custom_commands.list_commands(sender_id)
            if not user_cmds:
                await self.send_message_with_keyboard(chat_id, "📭 ليس لديك أي أوامر خاصة مسجلة بعد. استخدم <code>/custom</code> لإضافة أمر.", {}, reply_to_msg_id)
                return True
            lines = "\n".join(f"• <code>{c.command_trigger}</code> ➔ {c.response_template[:30]}..." for c in user_cmds)
            resp = f"📋 <b>أوامرك الخاصة في مساحتك المعزولة:</b>\n\n{lines}"
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # Custom Isolated Persona Configuration (/set_persona)
        elif cmd in ("/set_persona", "/شخصيتي"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            if len(parts) < 2:
                help_msg = (
                    "🎭 <b>تخصيص شخصية عمر معك في الخاص:</b>\n"
                    "<code>/set_persona &lt;الاسم&gt; [اللهجة: syrian, egyptian, saudi, lebanese, fusha]</code>\n\n"
                    "مثال: <code>/set_persona سارة syrian</code>\n"
                    "لإعادة الشخصية للأصلية: <code>/reset_persona</code>"
                )
                await self.send_message_with_keyboard(chat_id, help_msg, {}, reply_to_msg_id)
                return True
            p_name = parts[1]
            p_dialect = parts[2].lower() if len(parts) > 2 else "egyptian_syrian"
            persona = persona_virtualizer.update_persona(user_id=sender_id, persona_name=p_name, dialect=p_dialect)
            resp = (
                f"🎭 <b>تم تحديث شخصيتك الخاصة بنجاح!</b>\n"
                f"• الاسم المعتمد معك: <b>{persona.persona_name}</b>\n"
                f"• اللهجة: <code>{persona.dialect}</code>\n"
                f"<i>هذه الإعدادات معزولة تماماً في محادثتك الخاصة ولن تؤثر على أي مستخدم آخر.</i>"
            )
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # Reset Isolated Persona (/reset_persona)
        elif cmd in ("/reset_persona", "/شخصية_افتراضية"):
            from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
            persona_virtualizer.reset_persona(sender_id)
            resp = "🔄 <b>تمت استعادة شخصية عمر الافتراضية بنجاح!</b>"
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # Linguistic DNA Cloner (/clone_dna)
        elif cmd in ("/clone_dna", "/استنساخ"):
            sample = message_text[len(parts[0]):].strip()
            if len(sample) < 15:
                await self.send_message_with_keyboard(chat_id, "ℹ️ أرسل نصاً أطول أو محادثة لتحليل بصمتك اللغوية: <code>/clone_dna نص كلامك هنا...</code>", {}, reply_to_msg_id)
                return True
            from multi_tenant_sandbox.linguistic_dna_cloner import linguistic_cloner
            dna = linguistic_cloner.clone_and_apply_to_user(sender_id, sample)
            words = ", ".join(dna.get("favorite_words", [])[:6])
            emojis = " ".join(dna.get("top_emojis", [])[:4])
            resp = (
                f"🧬 <b>تم استنساخ وتحليل بصمتك اللغوية بنجاح!</b>\n"
                f"• معدل طول الجملة: {dna.get('avg_words_per_message')} كلمة\n"
                f"• أكثر الكلمات تكراراً: {words or 'متنوع'}\n"
                f"• الإيموجي المفضل: {emojis or 'لا يوجد'}\n"
                f"<i>سيقوم عمر الآن بمحاكاة أسلوبك في الكلام والتعبير معك في الخاص.</i>"
            )
            await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            return True

        # Human Alarm Wakeup Call (/alarm)
        elif cmd in ("/alarm", "/منبه", "/صحيني"):
            if len(parts) < 2:
                await self.send_message_with_keyboard(chat_id, "ℹ️ الاستخدام: <code>/alarm &lt;عدد الدقائق&gt; [ملاحظة]</code>\nمثال: <code>/alarm 30 صحيني عشان الامتحان</code>", {}, reply_to_msg_id)
                return True
            try:
                minutes = float(parts[1])
                note = message_text.split(parts[1], 1)[1].strip() if len(parts) > 2 else ""
                delay_sec = max(10.0, minutes * 60.0)
                from live_voip_call_engine.outbound_call_scheduler import outbound_scheduler
                outbound_scheduler.schedule_wakeup_call(
                    user_id=sender_id,
                    user_name=sender_name,
                    delay_seconds=delay_sec,
                    note=note,
                )
                resp = f"⏰ <b>تم ضبط المنبه البشري بنجاح!</b>\nعمر هيرن عليك بعد <b>{int(minutes)} دقيقة</b> عشان يصحيك بنشاط! ☕📞"
                await self.send_message_with_keyboard(chat_id, resp, {}, reply_to_msg_id)
            except ValueError:
                await self.send_message_with_keyboard(chat_id, "⚠️ اكتب الوقت بالدقائق كأرقام فقط.", {}, reply_to_msg_id)
            return True

        return False

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
    ) -> bool:
        """
        Sends formatted text message or separate notification alert.
        Protected by Anti-Ban Flood Token Bucket and Anti-Toxicity Outgoing Speech Sanitizer.
        """
        from aether_human_core.config.anti_ban_shield import anti_ban_shield
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        await anti_ban_shield.wait_for_telegram_slot(chat_id)
        text = anti_toxicity.sanitize_outgoing_speech(text)

        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Outgoing Message] Chat {chat_id} -> '{text[:60]}...'")
            return True

        # Outgoing message logging
        try:
            from aether_human_core.database.postgres.connection import db_manager
            from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
            async with db_manager.session() as db_sess:
                m_repo = MessageRepository(db_sess)
                await m_repo.log_message(
                    telegram_message_id=int(time.time() * 1000) % 1000000000,
                    chat_id=chat_id,
                    sender_id=getattr(self, "bot_id", 8677519723),
                    text=text,
                    media_type="text",
                    is_from_bot=True,
                    reply_to_msg_id=reply_to_msg_id,
                )
                await db_sess.commit()
        except Exception as out_err:
            logger.debug(f"Persistence error on send_message: {out_err}")

        if self.bot_token:
            http = await self._get_http()
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            }
            if reply_to_msg_id:
                payload["reply_to_message_id"] = reply_to_msg_id
            try:
                res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                if res.status_code == 200:
                    logger.info(f"📤 [Telegram Message Sent] Chat [{chat_id}]: '{text[:40]}...'")
                    return True
                else:
                    payload.pop("parse_mode", None)
                    fb_res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                    return fb_res.status_code == 200
            except Exception as exc:
                logger.error(f"Error sending message via Bot API: {exc}")
                return False
        elif self.client:
            try:
                await self.client.send_message(chat_id, text, reply_to=reply_to_msg_id)
                return True
            except Exception as exc:
                logger.error(f"Error sending message via Telethon: {exc}")
                return False
        return False

    async def send_ephemeral_message(
        self,
        chat_id: int,
        text: str,
        duration_sec: float = 4.5,
        reply_to_msg_id: Optional[int] = None,
    ) -> bool:
        """
        Sends a transient status update message that automatically deletes itself
        after `duration_sec` seconds. Simulates a momentary toast notification in private chat.
        """
        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Ephemeral ({duration_sec}s)] Chat {chat_id} -> '{text[:60]}...'")
            return True

        from aether_human_core.config.anti_ban_shield import anti_ban_shield
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        await anti_ban_shield.wait_for_telegram_slot(chat_id)
        text = anti_toxicity.sanitize_outgoing_speech(text)

        if self.bot_token:
            http = await self._get_http()
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            }
            if reply_to_msg_id:
                payload["reply_to_message_id"] = reply_to_msg_id
            try:
                res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                if res.status_code != 200:
                    payload.pop("parse_mode", None)
                    res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)

                if res.status_code == 200:
                    msg_id = res.json().get("result", {}).get("message_id")
                    if msg_id:
                        asyncio.create_task(self._auto_delete_message(chat_id, msg_id, duration_sec))
                    return True
            except Exception as exc:
                logger.error(f"Error sending ephemeral message via Bot API: {exc}")
                return False
        elif self.client:
            try:
                sent_msg = await self.client.send_message(chat_id, text, reply_to=reply_to_msg_id)
                if sent_msg:
                    asyncio.create_task(self._auto_delete_telethon_message(sent_msg, duration_sec))
                return True
            except Exception as exc:
                logger.error(f"Error sending ephemeral message via Telethon: {exc}")
                return False
        return False

    async def _auto_delete_message(self, chat_id: int, message_id: int, delay_sec: float) -> None:
        """Background helper to delete an ephemeral message after delay."""
        try:
            await asyncio.sleep(delay_sec)
            if self.bot_token:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/deleteMessage",
                    json={"chat_id": chat_id, "message_id": message_id},
                )
                logger.debug(f"Ephemeral message [{message_id}] in chat [{chat_id}] auto-deleted.")
        except Exception as exc:
            logger.debug(f"Could not auto-delete ephemeral message [{message_id}]: {exc}")

    async def _auto_delete_telethon_message(self, msg: Any, delay_sec: float) -> None:
        """Background helper for Telethon message deletion."""
        try:
            await asyncio.sleep(delay_sec)
            await msg.delete()
        except Exception:
            pass

    def sanitize_markup_for_chat(self, markup: Any, chat_id: int) -> Any:
        """
        Sanitizes inline keyboard:
        - Validates style attributes to valid Telegram colors.
        - In groups (chat_id < 0), converts forbidden 'web_app' buttons to direct 'url' buttons,
          preventing Telegram 400 Bad Request: BUTTON_TYPE_INVALID.
        """
        if not isinstance(markup, dict) or "inline_keyboard" not in markup:
            return markup
        import json
        clean_markup = json.loads(json.dumps(markup))
        valid_styles = {"primary", "success", "danger"}
        is_group_chat = int(chat_id) < 0
        for row in clean_markup.get("inline_keyboard", []):
            for btn in row:
                if "style" in btn and btn["style"] not in valid_styles:
                    btn["style"] = "primary"
                if is_group_chat and "web_app" in btn:
                    wa_dict = btn.pop("web_app", {})
                    wa_url = wa_dict.get("url") if isinstance(wa_dict, dict) else ""
                    if wa_url and wa_url.startswith("https://"):
                        btn["url"] = wa_url
                    else:
                        btn["url"] = f"https://t.me/{self.bot_username}?start=webapp"
        return clean_markup

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

            # Sanitize reply_markup styles and web_app buttons for groups
            clean_markup = self.sanitize_markup_for_chat(reply_markup, chat_id)

            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": clean_markup,
            }
            if reply_to_msg_id:
                payload["reply_to_message_id"] = reply_to_msg_id
            try:
                res = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                if res.status_code != 200:
                    logger.warning(f"sendMessage attempt 1 failed ({res.status_code}): {res.text}")
                    # Attempt 2: Pop parse_mode (in case of HTML formatting errors)
                    payload.pop("parse_mode", None)
                    res2 = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                    # Attempt 3: If still failing and reply_markup exists, strip style tags entirely
                    if res2.status_code != 200 and "reply_markup" in payload:
                        no_style_markup = json.loads(json.dumps(payload["reply_markup"]))
                        if "inline_keyboard" in no_style_markup:
                            for r in no_style_markup["inline_keyboard"]:
                                for b in r:
                                    b.pop("style", None)
                        payload["reply_markup"] = no_style_markup
                        res3 = await http.post(f"{self.bot_api_url}/sendMessage", json=payload)
                        if res3.status_code != 200:
                            logger.error(f"sendMessage retry 3 failed ({res3.status_code}): {res3.text}")
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
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
        **kwargs,
    ) -> None:
        """
        Sends sequential message bubbles with realistic typing latencies and typo self-corrections.
        Protected by Anti-Ban Flood Token Bucket and Anti-Toxicity Outgoing Speech Sanitizer.
        Strictly routes replies through the originating transport client (Userbot MTProto vs Bot API).
        """
        http = await self._get_http() if self.bot_token else None
        from aether_human_core.config.anti_ban_shield import anti_ban_shield
        from aether_human_core.psychology_engine.anti_toxicity import anti_toxicity

        # Consolidate messages in groups and cap private bubbles to avoid 429 Too Many Requests
        is_group = (chat_id < 0)
        if is_group and len(bursts) > 1:
            combined_text = "\n".join([b.text for b in bursts if b.text.strip()])
            bursts = [
                BurstMessage(
                    text=combined_text,
                    typing_delay_sec=min(bursts[0].typing_delay_sec, 1.2),
                    has_typo=False,
                )
            ]
        elif len(bursts) > 3:
            bursts = bursts[:3]

        active_userbot = userbot_client or self.client

        for i, burst in enumerate(bursts):
            # Enforce Telegram Anti-Ban Token-Bucket & per-chat rate limits
            await anti_ban_shield.wait_for_telegram_slot(chat_id)

            # Strictly sanitize outgoing text - ZERO PROFANITY GUARANTEE & natural colloquial formatting
            burst.text = anti_toxicity.sanitize_outgoing_speech(burst.text)
            burst.text = burst.text.replace("،", " ").replace(" ,", " ").replace(",", " ")
            while "  " in burst.text:
                burst.text = burst.text.replace("  ", " ")
            burst.text = burst.text.strip()

            if burst.correction_text:
                burst.correction_text = anti_toxicity.sanitize_outgoing_speech(burst.correction_text)
                burst.correction_text = burst.correction_text.replace("،", " ").replace(",", " ").strip()

            # 1. Task 2.1 Phase 3 — Realistic Slow Human Typing (~3.5 to 5 chars/sec for Userbot)
            if is_userbot or userbot_client is not None:
                cps = random.uniform(3.5, 5.0)
                char_count = max(1, len(burst.text))
                dynamic_typing_dur = max(1.5, min(char_count / cps, 24.0))
                logger.info(
                    f"⌨️ [Userbot Phase 3: Slow Typing] {char_count} chars at {cps:.2f} chars/sec "
                    f"-> typing for {dynamic_typing_dur:.1f}s in chat [{chat_id}]"
                )
            else:
                words_cnt = len(burst.text.split())
                dynamic_typing_dur = max(burst.typing_delay_sec, min(words_cnt * 0.20, 5.0))
            await self.send_typing_indicator(
                chat_id, dynamic_typing_dur, is_userbot=is_userbot, userbot_client=userbot_client
            )

            # 2. Transmit message bubble
            reply_target = reply_to_msg_id if i == 0 else None

            if is_userbot or userbot_client is not None:
                # STRICT USERBOT TRANSPORT: MUST SEND FROM USERBOT ACCOUNT VIA MTPROTO
                if active_userbot:
                    try:
                        await active_userbot.send_message(chat_id, burst.text, reply_to=reply_target)
                        logger.info(f"📤 [Userbot MTProto Sent] Chat [{chat_id}]: '{burst.text}'")
                    except FloodWaitError as fwe:
                        logger.warning(f"Telethon FloodWait on chat [{chat_id}]: {fwe.seconds}s. Sleeping...")
                        await asyncio.sleep(fwe.seconds + 1)
                        await active_userbot.send_message(chat_id, burst.text, reply_to=reply_target)
                    except Exception as exc:
                        logger.error(f"Failed to send burst message via Userbot MTProto: {exc}")
                else:
                    logger.warning(f"Userbot requested but active_userbot client is None for chat {chat_id}")
            elif self._mock_mode or (not self.bot_token and not self.client):
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
                    if res.status_code == 429:
                        try:
                            retry_sec = res.json().get("parameters", {}).get("retry_after", 5)
                        except Exception:
                            retry_sec = 5
                        logger.warning(f"Telegram 429 rate limit on chat [{chat_id}]. Sleeping for {retry_sec + 1}s...")
                        await asyncio.sleep(retry_sec + 1)
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
                            # 100% Fix for 400 Bad Request: chat not found
                            # If master bot is not present in chat_id, delegate delivery to Userbot MTProto or a present sibling bot
                            if "chat not found" in fallback_res.text.lower() or "chat_not_found" in fallback_res.text.lower():
                                logger.warning(f"Chat [{chat_id}] not found for Bot API! Attempting delivery via Userbot MTProto or present sibling...")
                                sent_via_fallback = False
                                if self.client and self.client.is_connected():
                                    try:
                                        await self.client.send_message(chat_id, burst.text, reply_to=reply_target)
                                        logger.info(f"📤 [Userbot MTProto Fallback Sent] Chat [{chat_id}]: '{burst.text}'")
                                        sent_via_fallback = True
                                    except Exception as ub_exc:
                                        logger.error(f"Failed fallback via Userbot MTProto for chat [{chat_id}]: {ub_exc}")
                                if not sent_via_fallback:
                                    try:
                                        from bot_factory.group_arbiter import group_arbiter
                                        delegate = group_arbiter.get_delegate_bot(chat_id)
                                        if delegate and delegate.bot_id != str(getattr(self, "bot_id", 0)):
                                            if delegate.token_or_session and not delegate.is_userbot:
                                                del_url = f"https://api.telegram.org/bot{delegate.token_or_session}/sendMessage"
                                                del_payload = {"chat_id": chat_id, "text": burst.text}
                                                if reply_target:
                                                    del_payload["reply_to_message_id"] = reply_target
                                                del_res = await http.post(del_url, json=del_payload)
                                                if del_res.status_code == 200:
                                                    logger.info(f"📤 [Delegate Sibling Bot ({delegate.name}) Sent] Chat [{chat_id}]: '{burst.text}'")
                                    except Exception as del_exc:
                                        logger.error(f"Failed delegate fallback send: {del_exc}")
                except Exception as exc:
                    logger.error(f"Error dispatching burst message via Bot API: {exc}")
            elif self.client:
                try:
                    await self.client.send_message(chat_id, burst.text, reply_to=reply_target)
                except FloodWaitError as fwe:
                    logger.warning(f"Telethon FloodWait on chat [{chat_id}]: {fwe.seconds}s. Sleeping...")
                    await asyncio.sleep(fwe.seconds + 1)
                    await self.client.send_message(chat_id, burst.text, reply_to=reply_target)
                except Exception as exc:
                    logger.error(f"Failed to send burst message via Telethon: {exc}")

            # Persist outgoing burst message
            try:
                from aether_human_core.database.postgres.connection import db_manager
                from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
                async with db_manager.session() as db_sess:
                    m_repo = MessageRepository(db_sess)
                    await m_repo.log_message(
                        telegram_message_id=int(time.time() * 1000) % 1000000000,
                        chat_id=chat_id,
                        sender_id=getattr(self, "bot_id", 8677519723),
                        text=burst.text,
                        media_type="text",
                        is_from_bot=True,
                        reply_to_msg_id=reply_target,
                    )
                    await db_sess.commit()
            except Exception as b_err:
                logger.debug(f"Persistence error on burst outgoing: {b_err}")

            # 3. Handle typo self-correction
            if burst.has_typo and burst.correction_text:
                await asyncio.sleep(random.uniform(0.4, 0.8))
                if is_userbot or userbot_client is not None:
                    if active_userbot:
                        try:
                            await active_userbot.send_message(chat_id, burst.correction_text)
                            logger.info(f"📤 [Userbot Typo Self-Correction] Chat [{chat_id}]: '{burst.correction_text}'")
                        except Exception:
                            pass
                elif self.bot_token and http:
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

            if is_userbot or userbot_client is not None:
                self._userbot_last_conv_ts[chat_id] = time.time()

            # Realistic pause between multi-bubble messages
            if i < len(bursts) - 1:
                if is_userbot or userbot_client is not None:
                    await asyncio.sleep(random.uniform(1.8, 3.8))
                else:
                    await asyncio.sleep(random.uniform(0.2, 0.5))

    async def send_voice_note(
        self,
        chat_id: int,
        file_path: str,
        waveform: bytes = b"",
        duration: int = 5,
        reply_to_msg_id: Optional[int] = None,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
    ) -> None:
        """
        Sends audio note as native Telegram voice note with accurate duration metadata and waveform.
        Strictly routes to Userbot when is_userbot=True.
        """
        if self._mock_mode or (not self.bot_token and not self.client):
            logger.info(f"[Simulation Outgoing Voice] Chat {chat_id} -> File: {file_path} (Duration: {duration}s)")
            return

        effective_duration = max(1, duration)

        if is_userbot or userbot_client is not None:
            active = userbot_client or self.client
            if active:
                try:
                    await active.send_file(
                        entity=chat_id,
                        file=file_path,
                        voice_note=True,
                        reply_to=reply_to_msg_id,
                    )
                    logger.info(f"📤 [Userbot MTProto Voice Sent] Chat [{chat_id}]: '{file_path}'")
                    return
                except Exception as exc:
                    logger.error(f"Failed to send voice note via Userbot Telethon: {exc}")
                    return

        if self.bot_token:
            try:
                http = await self._get_http()
                await http.post(
                    f"{self.bot_api_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": "record_voice"},
                )
                await asyncio.sleep(1.0)

                mime_type = "audio/ogg" if file_path.endswith(".ogg") else "audio/mpeg"
                with open(file_path, "rb") as f:
                    files = {"voice": (os.path.basename(file_path), f, mime_type)}
                    data: Dict[str, Any] = {
                        "chat_id": str(chat_id),
                        "duration": str(effective_duration),
                    }
                    if reply_to_msg_id:
                        data["reply_to_message_id"] = str(reply_to_msg_id)
                    res = await http.post(f"{self.bot_api_url}/sendVoice", data=data, files=files)
                    if res.status_code == 200:
                        logger.info(f"🎙️ [Voice Sent] Dispatched native voice note to chat [{chat_id}] (Duration: {effective_duration}s).")
                    else:
                        logger.warning(f"Failed to send voice note: {res.text}")
            except Exception as exc:
                logger.error(f"Error sending voice note via Bot API: {exc}")

        elif self.client:
            try:
                async with self.client.action(chat_id, "record-audio"):
                    await asyncio.sleep(1.5)
                await self.client.send_file(
                    chat_id,
                    file_path,
                    voice_note=True,
                    reply_to=reply_to_msg_id,
                    attributes=[DocumentAttributeAudio(voice=True, waveform=waveform, duration=effective_duration)],
                )
                logger.info(f"Dispatched native voice note via Telethon to [{chat_id}] (Duration: {effective_duration}s).")
            except Exception as exc:
                logger.error(f"Error sending voice note via Telethon: {exc}")

    async def send_photo(
        self,
        chat_id: int,
        photo_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
        is_userbot: bool = False,
        userbot_client: Optional[Any] = None,
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
