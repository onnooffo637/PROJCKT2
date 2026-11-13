"""
Interactive Telethon Userbot Authentication & Management Service.
Handles automated SMS/Telegram OTP requesting, 2FA submission, profile editing, and live stats.
Designed for Project Aether-Human (V2.0 - V4.0).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional, Tuple, Dict, Any
import httpx
from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
)
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.help import GetConfigRequest

from aether_human_core.config.settings import settings
from bot_factory.models import BotPlatformType, BotGender
from bot_factory.factory_manager import bot_factory

logger = logging.getLogger("Aether.BotFactory.InteractiveAuth")

# Global strong-reference task registry to prevent Python GC premature collection
_active_auth_tasks = set()


class InteractiveUserbotAuthManager:
    """
    Coordinates interactive phone login, OTP confirmation, and Telethon profile supervision.
    """

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.is_waiting_for_otp: bool = False
        self.is_waiting_for_2fa: bool = False
        self._login_lock = asyncio.Lock()
        self.session_name = "aether_userbot"
        self._is_active: bool = False
        self._init_task: Optional[asyncio.Task] = None

    def start_background_init(self) -> asyncio.Task:
        """
        Launches initialization as a strongly-referenced background task.
        Guarantees single-flight execution and prevents 'Task was destroyed but it is pending'.
        """
        if self._init_task is not None and not self._init_task.done():
            return self._init_task

        task = asyncio.create_task(self.initialize_or_request_login())
        self._init_task = task
        _active_auth_tasks.add(task)
        task.add_done_callback(_active_auth_tasks.discard)
        return task

    async def initialize_or_request_login(self) -> None:
        """
        Executed on engine startup. If userbot session exists and is authorized, boots it.
        If phone number is provided and not authorized, automatically requests OTP code and notifies The King.
        """
        api_id = settings.telegram_api_id
        api_hash = settings.telegram_api_hash
        phone = settings.telegram_phone_number

        if not api_id or not api_hash or api_id == 0:
            logger.info("Telethon API credentials not fully set. Interactive login skipped.")
            return

        try:
            for attempt in range(3):
                try:
                    self.client = TelegramClient(self.session_name, api_id, api_hash)
                    await self.client.connect()
                    break
                except Exception as ce:
                    if "locked" in str(ce).lower() and attempt < 2:
                        await asyncio.sleep(2.0)
                        continue
                    raise

            if await self.client.is_user_authorized():
                me = await self.client.get_me()
                self._is_active = True
                logger.info(f"✨ Telethon Userbot authorized as: [{me.first_name}] (ID: {me.id}, Phone: {me.phone})")
                self._register_userbot_in_factory(me)
                self._attach_userbot_handlers()
                return

            if phone:
                logger.info(f"Initiating autonomous login sequence for Userbot phone: {phone}...")
                await self.request_phone_code(phone, notify_king=True)

        except Exception as exc:
            logger.error(f"Error during interactive userbot startup sequence: {exc}")

    async def request_phone_code(self, phone: str, notify_king: bool = True) -> Tuple[bool, str]:
        """
        Requests OTP verification code via Telegram API for the specified phone number.
        """
        async with self._login_lock:
            api_id = settings.telegram_api_id
            api_hash = settings.telegram_api_hash

            if not api_id or not api_hash:
                return False, "❌ عفواً: TELEGRAM_API_ID أو TELEGRAM_API_HASH غير مضبوطين في ملف .env"

            clean_phone = phone.strip().replace(" ", "").replace("-", "")
            self.phone = clean_phone

            if not self.client:
                self.client = TelegramClient(self.session_name, api_id, api_hash)

            if not self.client.is_connected():
                await self.client.connect()

            if await self.client.is_user_authorized():
                me = await self.client.get_me()
                self._is_active = True
                self._register_userbot_in_factory(me)
                self._attach_userbot_handlers()
                return True, f"✅ الحساب مصرح ونشط بالفعل باسم: <b>{me.first_name}</b> (<code>{me.id}</code>)!"

            try:
                res = await self.client.send_code_request(clean_phone)
                self.phone_code_hash = res.phone_code_hash
                self.is_waiting_for_otp = True
                self.is_waiting_for_2fa = False

                logger.info(f"Telegram OTP code dispatched to phone [{clean_phone}]. Waiting for user entry...")

                if notify_king:
                    await self._notify_king_code_requested(clean_phone)

                return True, f"📨 تم إرسال كود التفعيل إلى حساب تيليجرام للرقم <code>{clean_phone}</code> بنجاح!"

            except FloodWaitError as fe:
                msg = f"⏳ تليجرام فرض حظر مؤقت للمحاولات (FloodWait) لمدة {fe.seconds} ثانية. يرجى الانتظار."
                logger.warning(msg)
                return False, msg
            except Exception as e:
                err = f"❌ فشل إرسال كود التفعيل للرقم {clean_phone}: {e}"
                logger.error(err)
                return False, err

    async def submit_otp(self, code: str, password: Optional[str] = None) -> Tuple[bool, str]:
        """
        Submits the received OTP code and completes the sign-in handshake.
        """
        async with self._login_lock:
            if not self.client or not self.phone or not self.phone_code_hash:
                return False, "⚠️ لا توجد عملية تسجيل دخول جارية حالياً. ابدأ بطلب الكود أولاً عبر: <code>/auth_userbot +22602269964</code>"

            clean_code = code.strip().replace(" ", "").replace("-", "")

            try:
                await self.client.sign_in(
                    phone=self.phone,
                    code=clean_code,
                    phone_code_hash=self.phone_code_hash,
                )
            except SessionPasswordNeededError:
                self.is_waiting_for_otp = False
                self.is_waiting_for_2fa = True

                if password:
                    try:
                        await self.client.sign_in(password=password.strip())
                    except Exception as pe:
                        return False, f"❌ كلمة سر التحقق بخطوتين غير صحيحة: {pe}"
                else:
                    return False, (
                        "🔐 <b>هذا الحساب محمي بالتحقق بخطوتين (Two-Step Verification)!</b>\n"
                        "يرجى إرسال كلمة المرور عبر الأمر:\n"
                        "<code>/2fa كلمة_المرور</code>"
                    )
            except PhoneCodeInvalidError:
                return False, "❌ كود التفعيل الذي أدخلته غير صحيح! تأكد من الأرقام وأعد المحاولة."
            except PhoneCodeExpiredError:
                self.is_waiting_for_otp = False
                return False, "⌛ انتهت صلاحية كود التفعيل. يرجى طلب كود جديد عبر: <code>/auth_userbot</code>"
            except Exception as exc:
                return False, f"❌ خطأ أثناء تسجيل الدخول: {exc}"

            if await self.client.is_user_authorized():
                self.is_waiting_for_otp = False
                self.is_waiting_for_2fa = False
                self._is_active = True
                me = await self.client.get_me()

                self._register_userbot_in_factory(me)
                self._attach_userbot_handlers()
                await self._notify_king_login_success(me)

                return True, (
                    f"🎉 <b>تم تسجيل الدخول وتفعيل اليوزربوت بنجاح تام!</b> 🤖\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>الاسم:</b> <b>{me.first_name}</b>\n"
                    f"🆔 <b>الأيدي:</b> <code>{me.id}</code>\n"
                    f"📱 <b>الرقم:</b> <code>{self.phone}</code>\n"
                    f"🏷️ <b>المعرف:</b> @{me.username or 'بدون معرف'}"
                )

            return False, "❌ لم يكتمل تسجيل الدخول، يرجى المحاولة مجدداً."

    async def submit_2fa(self, password: str) -> Tuple[bool, str]:
        """
        Completes Two-Step verification handshake.
        """
        async with self._login_lock:
            if not self.client:
                return False, "⚠️ لا يوجد اتصال نشط باليوزربوت."
            try:
                await self.client.sign_in(password=password.strip())
                if await self.client.is_user_authorized():
                    self.is_waiting_for_2fa = False
                    self._is_active = True
                    me = await self.client.get_me()
                    self._register_userbot_in_factory(me)
                    self._attach_userbot_handlers()
                    await self._notify_king_login_success(me)
                    return True, f"🎉 تم تأكيد كلمة سر التحقق بخطوتين وتفعيل اليوزربوت للحساب: <b>{me.first_name}</b>!"
                return False, "❌ فشل تسجيل الدخول بكلمة المرور."
            except Exception as exc:
                return False, f"❌ خطأ أثناء إدخال كلمة سر 2FA: {exc}"

    async def update_profile(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        about: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Updates the Userbot's native Telegram First Name, Last Name, or Bio/About.
        """
        if not self.client or not await self.client.is_user_authorized():
            return False, "⚠️ اليوزربوت غير مسجل أو غير متصل حالياً."

        try:
            me = await self.client.get_me()
            cur_first = first_name if first_name is not None else (me.first_name or "")
            cur_last = last_name if last_name is not None else (me.last_name or "")
            cur_about = about if about is not None else ""

            await self.client(UpdateProfileRequest(
                first_name=cur_first,
                last_name=cur_last,
                about=cur_about,
            ))

            # Re-sync local factory config
            inst = bot_factory.get_bot(f"userbot_{me.id}")
            if inst:
                inst.name = cur_first
                if cur_about:
                    inst.bio = cur_about
                bot_factory.update_bot(inst)

            return True, f"✅ تم تحديث بروفايل اليوزربوت بنجاح!\nالاسم: <b>{cur_first}</b>\nالبايو: <i>{cur_about}</i>"
        except Exception as exc:
            return False, f"❌ فشل تعديل بروفايل اليوزربوت: {exc}"

    async def get_stats(self) -> Dict[str, Any]:
        """
        Returns live operational statistics for the active userbot.
        """
        if not self.client or not await self.client.is_user_authorized():
            return {"active": False, "status": "غير متصل / بانتظار التفعيل"}

        try:
            me = await self.client.get_me()
            dialogs = await self.client.get_dialogs(limit=100)
            groups = [d for d in dialogs if d.is_group]
            channels = [d for d in dialogs if d.is_channel]
            dms = [d for d in dialogs if d.is_user]

            return {
                "active": True,
                "user_id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name or "",
                "username": me.username or "بدون معرف",
                "phone": me.phone or self.phone,
                "total_dialogs": len(dialogs),
                "groups_count": len(groups),
                "channels_count": len(channels),
                "dms_count": len(dms),
                "status": "🟢 متصل ونشط على شبكة MTProto",
            }
        except Exception as e:
            return {"active": False, "error": str(e), "status": "خطأ في جلب الإحصائيات"}

    def _register_userbot_in_factory(self, me: Any) -> None:
        inst_id = f"userbot_{me.id}"
        if not bot_factory.get_bot(inst_id):
            bot_factory.create_bot(
                instance_id=inst_id,
                name=me.first_name or "Omar Userbot",
                bot_type=BotPlatformType.MTPROTO_USERBOT,
                token_or_session=self.session_name,
                gender=BotGender.MALE,
                age=24,
                template_code="OMAR_CHARISMATIC",
                bio="حساب اليوزربوت البشري التلقائي للكيان الذكي عمر 2.0",
                dialect="syrian",
            )
            logger.info(f"Registered Userbot [{inst_id}] in Bot Factory database.")

    def _attach_userbot_handlers(self) -> None:
        """
        Attaches event handlers to Telethon client for human-like group & private messaging,
        plus raw VoIP phone call and video-blocking interception.
        """
        if not self.client:
            return

        from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
        mtproto_manager.client = self.client
        mtproto_manager._register_telethon_handlers()
        logger.info("Telethon Userbot event handlers and VoIP Call Interceptor hooked successfully via MTProtoManager.")

    async def _notify_king_code_requested(self, phone: str) -> None:
        token = settings.telegram_bot_token
        king_id = settings.the_king_user_id
        if not token or not king_id:
            return

        text = (
            f"📲 <b>طلب كود تفعيل اليوزربوت (Telethon MTProto)</b> 🤖\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>الرقم المطلوب:</b> <code>{phone}</code>\n"
            f"🆔 <b>API ID:</b> <code>{settings.telegram_api_id}</code>\n\n"
            f"✨ أرسل تيليجرام كود التحقق في رسالة إلى حسابك، من فضلك أرسله هنا بالأمر:\n"
            f"<code>/otp 12345</code>\n\n"
            f"💡 <i>(لو الحساب عليه كلمة سر خطوتين 2FA، اكتبها مع الكود:</i> <code>/otp 12345 باسورد</code><i>)</i>"
        )
        try:
            async with httpx.AsyncClient(timeout=8.0) as http:
                await http.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": king_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception as e:
            logger.debug(f"Failed to notify king of OTP code request: {e}")

    async def _notify_king_login_success(self, me: Any) -> None:
        token = settings.telegram_bot_token
        king_id = settings.the_king_user_id
        if not token or not king_id:
            return

        text = (
            f"👑 <b>تهانينا يا صاحب السيادة: اليوزربوت يعمل الآن بكامل طاقته!</b> 🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>اسم الحساب:</b> <b>{me.first_name}</b>\n"
            f"🆔 <b>الأيدي:</b> <code>{me.id}</code>\n"
            f"📱 <b>الرقم:</b> <code>{self.phone}</code>\n"
            f"🏷️ <b>المعرف:</b> @{me.username or 'بدون معرف'}\n\n"
            f"🛠️ <b>التحكم الكامل المتاح لك الآن من الشات:</b>\n"
            f"• <code>/userbot_stats</code> - فحص إحصائيات الحساب وشاتاته\n"
            f"• <code>/userbot_name &lt;الاسم&gt;</code> - تغيير اسم الحساب في تيليجرام فورياً\n"
            f"• <code>/userbot_bio &lt;الوصف&gt;</code> - تغيير البايو والوصف للحساب\n"
            f"• <code>/userbot_persona &lt;الشخصية&gt;</code> - ضبط أسلوب وشخصية الحساب\n"
        )
        try:
            async with httpx.AsyncClient(timeout=8.0) as http:
                await http.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": king_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception as e:
            logger.debug(f"Failed to notify king of login success: {e}")


interactive_userbot = InteractiveUserbotAuthManager()

