"""
In-App MTProto Interactive Web Login API (AetherGram Native Auth).
Allows The King to authenticate the Userbot directly from inside the Telegram Mini App
via phone number, 5-digit OTP code keypad, and 2FA cloud password.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from security_and_rbac.rbac_ui_guard import rbac_guard
from bot_factory.interactive_userbot_auth import interactive_userbot
from aether_human_core.config.settings import settings

logger = logging.getLogger("Aether.MiniApp.MTProtoAuthAPI")

mtproto_auth_router = APIRouter(prefix="/api/webapp/mtproto", tags=["MTProto In-App Auth"])


class SendCodeRequest(BaseModel):
    user_id: int = 0
    phone: Optional[str] = None
    phone_number: Optional[str] = None


class VerifyOtpRequest(BaseModel):
    user_id: int = 0
    code: str
    password: Optional[str] = None


class Verify2FARequest(BaseModel):
    user_id: int = 0
    password: str


@mtproto_auth_router.get("/status")
async def get_mtproto_auth_status(user_id: int = 0) -> Dict[str, Any]:
    """
    Returns current connection and login state of the userbot.
    """
    rbac_guard.verify_king_access(user_id)

    is_authed = False
    me_info = None
    if interactive_userbot.client and interactive_userbot.client.is_connected():
        try:
            if await interactive_userbot.client.is_user_authorized():
                is_authed = True
                me = await interactive_userbot.client.get_me()
                me_info = {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name or "",
                    "username": me.username or "",
                    "phone": me.phone or interactive_userbot.phone,
                }
        except Exception:
            pass

    return {
        "is_authorized": is_authed,
        "is_waiting_for_otp": interactive_userbot.is_waiting_for_otp,
        "is_waiting_for_2fa": interactive_userbot.is_waiting_for_2fa,
        "phone": interactive_userbot.phone or settings.telegram_phone_number,
        "user": me_info,
    }


@mtproto_auth_router.post("/send_code")
async def send_code_for_userbot(req: SendCodeRequest) -> Dict[str, Any]:
    """
    Initiates MTProto SMS/Telegram OTP request to the specified phone number.
    """
    rbac_guard.verify_king_access(req.user_id)

    target_phone = req.phone or req.phone_number or settings.telegram_phone_number
    if not target_phone:
        raise HTTPException(status_code=400, detail="رقم الهاتف مطلوب للبدء.")

    ok, msg = await interactive_userbot.request_phone_code(target_phone, notify_king=True)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "ok": True,
        "message": msg,
        "phone": interactive_userbot.phone,
        "status": "WAITING_FOR_OTP",
    }


@mtproto_auth_router.post("/verify_otp")
async def verify_otp_for_userbot(req: VerifyOtpRequest) -> Dict[str, Any]:
    """
    Submits 5-digit OTP code to complete MTProto userbot sign-in.
    """
    rbac_guard.verify_king_access(req.user_id)

    ok, msg = await interactive_userbot.submit_otp(code=req.code, password=req.password)
    if not ok:
        if interactive_userbot.is_waiting_for_2fa:
            return {
                "ok": False,
                "needs_2fa": True,
                "message": msg,
                "status": "WAITING_FOR_2FA",
            }
        raise HTTPException(status_code=400, detail=msg)

    status_data = await get_mtproto_auth_status(req.user_id)
    return {
        "ok": True,
        "message": msg,
        "status": "AUTHORIZED",
        "data": status_data,
    }


@mtproto_auth_router.post("/verify_2fa")
async def verify_2fa_for_userbot(req: Verify2FARequest) -> Dict[str, Any]:
    """
    Submits 2FA cloud password to complete sign-in.
    """
    rbac_guard.verify_king_access(req.user_id)

    ok, msg = await interactive_userbot.submit_2fa(password=req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    status_data = await get_mtproto_auth_status(req.user_id)
    return {
        "ok": True,
        "message": msg,
        "status": "AUTHORIZED",
        "data": status_data,
    }

router = mtproto_auth_router
