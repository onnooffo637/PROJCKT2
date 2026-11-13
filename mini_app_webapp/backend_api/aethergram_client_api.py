"""
Embedded AetherGram Mod Client Backend API (Project Aether-Human V5.0).
Provides full Telegram Web Client data, live dialogs, anti-delete inspection,
ghost mode, live message sending, AI X-Ray inspection, auto-AI toggling,
real avatar proxying, live profile studio, and strict multi-bot/chat-scope isolation.
Restricted strictly to The Sovereign King.
"""

from __future__ import annotations

import base64
import html
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

from security_and_rbac.rbac_ui_guard import rbac_guard
from aether_human_core.config.settings import settings
from aether_human_core.config.llm_router import llm_pool
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.psychology_engine.affinity_matrix import RelationshipTier
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from bot_factory.interactive_userbot_auth import interactive_userbot
from bot_factory.factory_manager import bot_factory
from admin_telemetry_and_archiver.ghost_anti_delete_catcher import ghost_catcher
from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

logger = logging.getLogger("Aether.MiniApp.AetherGramAPI")

aethergram_router = APIRouter(prefix="/api/webapp/aethergram", tags=["AetherGram Mod Client"])

# In-memory registry for per-chat AI Auto-Reply overrides: chat_id -> bool (default True)
chat_ai_toggle_registry: Dict[int, bool] = {}

# Ensure avatar cache directory exists
AVATAR_CACHE_DIR = os.path.join(os.getcwd(), "artifacts", "avatars")
os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)


class SendMessagePayload(BaseModel):
    user_id: int = 0
    account_type: str = "userbot"  # 'userbot', 'main_bot', or 'bot_...'
    text: str
    reply_to_msg_id: Optional[int] = None


class ToggleAiPayload(BaseModel):
    user_id: int = 0
    enabled: bool


class SuggestReplyPayload(BaseModel):
    user_id: int = 0
    chat_title: str = "محادثة"
    last_user_message: str = ""


class ModifyAffinityPayload(BaseModel):
    user_id: int = 0
    affinity_score: float
    role: Optional[str] = None
    relationship_tier: Optional[str] = None


class SendVoicePayload(BaseModel):
    user_id: int = 0
    text: str
    account_type: str = "userbot"


class ProfileUpdatePayload(BaseModel):
    user_id: int = 0
    account_type: str = "userbot"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    about: Optional[str] = None
    username: Optional[str] = None


class ProfileStoryPayload(BaseModel):
    user_id: int = 0
    caption: str
    story_type: str = "text"  # 'text' or 'photo'


@aethergram_router.get("/accounts")
async def list_available_accounts(user_id: int = 0) -> Dict[str, Any]:
    """
    Returns the fleet of active accounts switchable in the Omni-Account Bar,
    including an option for unified merged mode.
    """
    rbac_guard.verify_king_access(user_id)

    accounts = []

    # 1. Userbot account
    ub_stats = await interactive_userbot.get_stats()
    if ub_stats.get("active"):
        accounts.append({
            "id": "userbot",
            "name": f"{ub_stats.get('first_name')} (اليوزربوت الحي)",
            "type": "USERBOT",
            "user_id": ub_stats.get("user_id"),
            "username": ub_stats.get("username"),
            "phone": ub_stats.get("phone"),
            "status": "🟢 متصل عبر MTProto",
            "avatar_icon": "👤",
        })
    else:
        accounts.append({
            "id": "userbot",
            "name": "اليوزربوت (غير متصل)",
            "type": "USERBOT",
            "status": "⚪ بانتظار تسجيل الدخول",
            "avatar_icon": "👤",
            "needs_login": True,
        })

    # 2. Main Official Bot (Omar)
    accounts.append({
        "id": "main_bot",
        "name": "عمر (البوت الرسمي الأساسي)",
        "type": "OFFICIAL_BOT",
        "username": getattr(mtproto_manager, "bot_username", "omarggforbot"),
        "status": "🟢 نشط على Bot API",
        "avatar_icon": "🤖",
    })

    # 3. Factory Sub-Bots (e.g. Maryam)
    for b in bot_factory.list_all_bots():
        if b.instance_id != "master_omar_official":
            accounts.append({
                "id": b.instance_id,
                "name": b.name,
                "type": b.bot_type.value,
                "status": "🟢 نشط" if b.is_active else "⚪ متوقف",
                "avatar_icon": "👧" if b.gender.value == "FEMALE" else "👦",
            })

    # 4. Merged Unified Mode
    accounts.append({
        "id": "all_accounts",
        "name": "🌐 جميع الحسابات (وضع الدمج الموحد)",
        "type": "UNIFIED_MERGED",
        "status": "✨ عرض مدمج لجميع المحادثات",
        "avatar_icon": "🌐",
    })

    return {"ok": True, "accounts": accounts}


@aethergram_router.get("/chats")
async def get_chats_list(
    user_id: int = 0,
    account: str = "userbot",
    folder: str = "all",
) -> Dict[str, Any]:
    """
    Retrieves dialogs/chats strictly isolated by folder and account namespace.
    """
    rbac_guard.verify_king_access(user_id)

    chats: List[Dict[str, Any]] = []
    seen_chat_ids = set()
    f_lower = (folder or "all").lower()

    # Case A: Userbot Account selected -> Query real Telethon dialogs
    if account in ("userbot", "userbot_primary") and interactive_userbot.client and interactive_userbot.client.is_connected():
        try:
            if await interactive_userbot.client.is_user_authorized():
                dialogs = await interactive_userbot.client.get_dialogs(limit=70)
                for d in dialogs:
                    chat_type = "user" if d.is_user else ("group" if d.is_group else "channel")

                    # Strict Folder Isolation
                    if f_lower in ("dm", "private", "user") and chat_type != "user":
                        continue
                    elif f_lower in ("group", "groups") and chat_type != "group":
                        continue
                    elif f_lower in ("channel", "channels") and chat_type != "channel":
                        continue

                    last_msg_text = getattr(d.message, "message", "") or "[وسائط / ميديا]"
                    date_str = d.date.strftime("%H:%M") if hasattr(d, "date") and d.date else ""

                    has_del = any(del_item.get("chat_id") == d.id for del_item in ghost_catcher.get_deleted_messages(d.id))
                    if f_lower in ("deleted", "anti_delete") and not has_del:
                        continue

                    seen_chat_ids.add(d.id)
                    chats.append({
                        "id": d.id,
                        "chat_id": d.id,
                        "title": d.title or d.name or "محادثة",
                        "type": chat_type,
                        "unread_count": d.unread_count,
                        "last_message": last_msg_text[:50],
                        "time": date_str,
                        "time_str": date_str,
                        "pinned": d.pinned,
                        "is_deleted": has_del,
                        "ai_enabled": chat_ai_toggle_registry.get(d.id, True),
                    })
        except Exception as exc:
            logger.debug(f"Error fetching telethon dialogs: {exc}")

    # Case B: Main Bot or Factory Sub-Bot or Merged Mode -> Query local database
    if not chats or account in ("main_bot", "all_accounts") or account.startswith("bot_"):
        try:
            from sqlalchemy import text
            async with db_manager.session() as session:
                # Query recent chats from chats table with robust column fallback
                chat_rows = await session.execute(
                    text("SELECT coalesce(telegram_id, chat_id) AS telegram_id, title, chat_type, coalesce(updated_at, last_message_at, created_at) AS updated_at FROM chats ORDER BY coalesce(updated_at, last_message_at, created_at) DESC LIMIT 50")
                )
                for c in chat_rows.fetchall():
                    c_dict = dict(c._mapping)
                    cid = c_dict["telegram_id"]
                    if cid in seen_chat_ids:
                        continue

                    raw_type = c_dict.get("chat_type", "private")
                    is_group = cid < 0 or raw_type in ("group", "supergroup")
                    is_channel = raw_type == "channel"
                    c_type = "channel" if is_channel else ("group" if is_group else "user")

                    # Strict Folder Isolation
                    if f_lower in ("dm", "private", "user") and c_type != "user":
                        continue
                    elif f_lower in ("group", "groups") and c_type != "group":
                        continue
                    elif f_lower in ("channel", "channels") and c_type != "channel":
                        continue

                    has_del = any(del_item.get("chat_id") == cid for del_item in ghost_catcher.get_deleted_messages(cid))
                    if f_lower in ("deleted", "anti_delete") and not has_del:
                        continue

                    seen_chat_ids.add(cid)
                    chats.append({
                        "id": cid,
                        "chat_id": cid,
                        "title": c_dict.get("title") or f"محادثة {cid}",
                        "type": c_type,
                        "unread_count": 0,
                        "last_message": "[محادثة مسجلة]",
                        "time": "الآن",
                        "time_str": "الآن",
                        "is_deleted": has_del,
                        "ai_enabled": chat_ai_toggle_registry.get(cid, True),
                    })

                # If folder is private/all, also include users with affinity records
                if f_lower in ("all", "dm", "private", "user"):
                    user_rows = await session.execute(
                        text("SELECT telegram_id, first_name, username, affinity_score, relationship_tier, role, updated_at FROM users ORDER BY updated_at DESC LIMIT 40")
                    )
                    for u in user_rows.fetchall():
                        u_dict = dict(u._mapping)
                        uid = u_dict["telegram_id"]
                        if uid in seen_chat_ids:
                            continue

                        has_del = any(del_item.get("chat_id") == uid for del_item in ghost_catcher.get_deleted_messages(uid))
                        if f_lower in ("deleted", "anti_delete") and not has_del:
                            continue

                        seen_chat_ids.add(uid)
                        chats.append({
                            "id": uid,
                            "chat_id": uid,
                            "title": u_dict.get("first_name") or f"المستخدم {uid}",
                            "type": "user",
                            "username": u_dict.get("username") or "",
                            "unread_count": 0,
                            "last_message": f"المعزة: {u_dict.get('affinity_score', 0):.0f}% | الرتبة: {u_dict.get('role', 'MEMBER')}",
                            "time": "الآن",
                            "time_str": "الآن",
                            "is_deleted": has_del,
                            "ai_enabled": chat_ai_toggle_registry.get(uid, True),
                        })
        except Exception as exc:
            logger.debug(f"Error fetching DB chats: {exc}")

    return {"ok": True, "chats": chats, "count": len(chats), "account": account, "folder": folder}


@aethergram_router.get("/chat/{chat_id}/messages")
async def get_chat_messages(
    chat_id: int,
    user_id: int = 0,
    account: str = "userbot",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Fetches comprehensive message history strictly confined to the requested chat_id:
    - Never leaks group messages sent by this user into private chat views!
    - Hybrid history backfill via Telethon Userbot if local history < 15.
    - Forensic deleted messages from Ghost Anti-Delete Catcher.
    """
    rbac_guard.verify_king_access(user_id)

    messages: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. Fetch strictly from Local Database where chat_id == target_chat_id
    try:
        from sqlalchemy import select, desc
        from aether_human_core.database.postgres.models import MessageRecordModel, UserModel
        async with db_manager.session() as session:
            stmt = (
                select(MessageRecordModel, UserModel.first_name)
                .outerjoin(UserModel, MessageRecordModel.sender_id == UserModel.telegram_id)
                .where(MessageRecordModel.chat_id == chat_id)
                .order_by(desc(MessageRecordModel.created_at))
                .limit(limit)
            )
            res = await session.execute(stmt)
            for m_rec, u_name in res.all():
                msg_id = m_rec.telegram_message_id or m_rec.id
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                s_name = "البوت" if m_rec.is_from_bot else (u_name or "المستخدم")
                messages.append({
                    "id": msg_id,
                    "chat_id": chat_id,
                    "sender_id": m_rec.sender_id,
                    "sender_name": s_name,
                    "text": m_rec.text or "[ميديا / ملف]",
                    "media_type": m_rec.media_type or "text",
                    "is_outgoing": m_rec.is_from_bot,
                    "date": m_rec.created_at.strftime("%H:%M") if m_rec.created_at else "",
                    "is_deleted": False,
                    "is_edited": False,
                })
    except Exception as db_exc:
        logger.debug(f"Error reading DB messages for chat {chat_id}: {db_exc}")

    # 2. Hybrid History Backfill via Telethon if count < 15 or Userbot requested
    if (len(messages) < 15 or account in ("userbot", "userbot_primary")) and interactive_userbot.client and interactive_userbot.client.is_connected():
        try:
            if await interactive_userbot.client.is_user_authorized():
                async for m in interactive_userbot.client.iter_messages(chat_id, limit=limit):
                    if m.id in seen_ids:
                        continue
                    seen_ids.add(m.id)
                    sender = await m.get_sender()
                    s_name = getattr(sender, "first_name", "") or "مستخدم"
                    m_type = "photo" if m.photo else ("voice" if (m.voice or m.audio) else "text")
                    m_text = m.raw_text or ("[صورة]" if m.photo else ("[تسجيل صوتي]" if (m.voice or m.audio) else "[ميديا / وسائط]"))

                    msg_obj = {
                        "id": m.id,
                        "chat_id": chat_id,
                        "sender_id": m.sender_id,
                        "sender_name": s_name,
                        "text": m_text,
                        "media_type": m_type,
                        "is_outgoing": m.out,
                        "date": m.date.strftime("%H:%M") if m.date else "",
                        "is_deleted": False,
                        "is_edited": bool(m.edit_date),
                    }
                    messages.append(msg_obj)

                    # Persist backfilled message
                    try:
                        from aether_human_core.database.postgres.repositories.message_repo import MessageRepository
                        async with db_manager.session() as b_session:
                            m_repo = MessageRepository(b_session)
                            await m_repo.log_message(
                                telegram_message_id=m.id,
                                chat_id=chat_id,
                                sender_id=m.sender_id or chat_id,
                                text=m_text,
                                media_type=m_type,
                                is_from_bot=m.out,
                            )
                            await b_session.commit()
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug(f"Error fetching iter_messages: {exc}")

    # 3. Check Ghost Anti-Delete cache for forensic deleted messages
    deleted_count = 0
    del_records = ghost_catcher.get_deleted_messages(chat_id)
    for d_rec in del_records:
        d_id = d_rec.get("message_id", 0)
        messages.append({
            "id": d_id,
            "chat_id": chat_id,
            "sender_id": d_rec.get("sender_id", 0),
            "sender_name": d_rec.get("sender_name", "مجهول"),
            "text": d_rec.get("text", ""),
            "media_type": "text",
            "is_outgoing": False,
            "date": "محفوظ 🗑️",
            "is_deleted": True,
            "original_text": d_rec.get("text", ""),
            "is_edited": False,
        })
        deleted_count += 1

    # Sort chronologically from oldest to newest
    messages.sort(key=lambda x: int(x.get("id", 0)) if str(x.get("id", 0)).isdigit() else 0)

    return {
        "ok": True,
        "chat_id": chat_id,
        "messages": messages,
        "count": len(messages),
        "deleted_intercepted": deleted_count,
        "ghost_mode_active": True,
    }


_failed_avatar_cache: Dict[int, float] = {}


@aethergram_router.get("/avatar/{account_id}/{peer_id}")
async def get_telegram_avatar_proxy(account_id: str, peer_id: int):
    """
    Downloads, caches locally in artifacts/avatars/{peer_id}.jpg, and serves real Telegram avatars
    via Telethon Userbot or Official Bot API. Fallbacks to high-res SVG avatar if no photo exists.
    """
    cache_file = os.path.join(AVATAR_CACHE_DIR, f"{peer_id}.jpg")

    # 1. Return from disk cache if exists and not empty
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 100:
        return FileResponse(cache_file, media_type="image/jpeg")

    # 2. Attempt download via active Telethon Client
    if interactive_userbot.client and interactive_userbot.client.is_connected():
        try:
            if await interactive_userbot.client.is_user_authorized():
                photo_path = await interactive_userbot.client.download_profile_photo(
                    peer_id, file=cache_file, download_big=False
                )
                if photo_path and os.path.exists(cache_file) and os.path.getsize(cache_file) > 100:
                    return FileResponse(cache_file, media_type="image/jpeg")
        except Exception as exc:
            logger.debug(f"Telethon avatar fetch notice for [{peer_id}]: {exc}")

    # 3. Attempt download via Bot API if peer_id > 0 and not recently failed
    token = settings.telegram_bot_token
    now_t = time.time()
    has_recent_fail = (peer_id in _failed_avatar_cache and (now_t - _failed_avatar_cache[peer_id] < 600.0))
    if token and peer_id > 0 and not has_recent_fail:
        try:
            async with httpx.AsyncClient(timeout=6.0) as http:
                res = await http.get(
                    f"https://api.telegram.org/bot{token}/getUserProfilePhotos",
                    params={"user_id": peer_id, "limit": 1},
                )
                if res.status_code == 200:
                    photos = res.json().get("result", {}).get("photos", [])
                    if photos and photos[0]:
                        file_id = photos[0][-1]["file_id"]
                        f_info = await http.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id})
                        if f_info.status_code == 200:
                            fp = f_info.json()["result"]["file_path"]
                            dl = await http.get(f"https://api.telegram.org/file/bot{token}/{fp}")
                            if dl.status_code == 200:
                                with open(cache_file, "wb") as f:
                                    f.write(dl.content)
                                return FileResponse(cache_file, media_type="image/jpeg")
                    _failed_avatar_cache[peer_id] = now_t
                else:
                    _failed_avatar_cache[peer_id] = now_t
        except Exception as ex:
            _failed_avatar_cache[peer_id] = now_t
            logger.debug(f"Bot API avatar fetch notice for [{peer_id}]: {ex}")

    # 4. Generate elegant Cyberpunk SVG Avatar with Initial
    initial = str(abs(peer_id))[:1]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#00F5D4;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#7928CA;stop-opacity:1" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="50" fill="url(#grad)" />
      <text x="50" y="62" font-family="Arial, sans-serif" font-size="38" font-weight="bold" fill="#ffffff" text-anchor="middle">{initial}</text>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@aethergram_router.post("/profile/update")
async def update_account_profile(payload: ProfileUpdatePayload) -> Dict[str, Any]:
    """
    Applies live First Name, Last Name, Bio/About, or Username changes to the active account.
    """
    rbac_guard.verify_king_access(payload.user_id)

    # Userbot profile update via MTProto
    if payload.account_type in ("userbot", "userbot_primary"):
        ok, msg = await interactive_userbot.update_profile(
            first_name=payload.first_name,
            last_name=payload.last_name,
            about=payload.about,
        )
        if payload.username and interactive_userbot.client and interactive_userbot.client.is_connected():
            try:
                from telethon.tl.functions.account import UpdateUsernameRequest
                clean_un = payload.username.replace("@", "").strip()
                await interactive_userbot.client(UpdateUsernameRequest(username=clean_un))
                msg += f" والمعرف: @{clean_un}"
            except Exception as ue:
                msg += f" (تنبيه المعرف: {ue})"
        return {"ok": ok, "message": msg}

    # Factory Bot update in database
    bot_cfg = bot_factory.get_bot(payload.account_type)
    if bot_cfg:
        if payload.first_name:
            bot_cfg.name = payload.first_name.strip()
        if payload.about:
            bot_cfg.bio = payload.about.strip()
        bot_factory._save_database()
        return {"ok": True, "message": f"تم تحديث بيانات البوت [{bot_cfg.name}] بنجاح."}

    raise HTTPException(status_code=404, detail="Account not found.")


@aethergram_router.post("/profile/photo")
async def upload_account_photo(
    file: UploadFile = File(...),
    account_type: str = Query("userbot"),
    user_id: int = Query(0),
) -> Dict[str, Any]:
    """
    Uploads new profile photo for the active account via Telethon UploadProfilePhotoRequest.
    """
    rbac_guard.verify_king_access(user_id)

    if not interactive_userbot.client or not interactive_userbot.client.is_connected():
        raise HTTPException(status_code=400, detail="Userbot client is not active.")

    content = await file.read()
    temp_path = os.path.join(AVATAR_CACHE_DIR, f"upload_{int(time.time())}.jpg")
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        from telethon.tl.functions.photos import UploadProfilePhotoRequest
        uploaded_file = await interactive_userbot.client.upload_file(temp_path)
        await interactive_userbot.client(UploadProfilePhotoRequest(file=uploaded_file))
        logger.info("Successfully updated Userbot profile photo via MTProto.")
        return {"ok": True, "message": "تم تحديث وتعيين الصورة الشخصية لليوزربوت بنجاح!"}
    except Exception as exc:
        logger.error(f"Failed to upload profile photo: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile photo: {exc}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@aethergram_router.post("/chat/{chat_id}/modify_affinity")
async def modify_chat_affinity(chat_id: int, payload: ModifyAffinityPayload) -> Dict[str, Any]:
    """
    Directly modifies the user's affinity score, role, and relationship tier.
    """
    rbac_guard.verify_king_access(payload.user_id)
    try:
        async with db_manager.session() as session:
            repo = UserRepository(session)
            u = await repo.get_by_telegram_id(chat_id)
            if u:
                await repo.update_affinity(chat_id, payload.affinity_score)
                if payload.role:
                    await repo.set_user_role(chat_id, payload.role)
                if payload.relationship_tier:
                    u.relationship_tier = payload.relationship_tier
                    await session.commit()
                return {
                    "ok": True,
                    "chat_id": chat_id,
                    "new_affinity": payload.affinity_score,
                    "role": payload.role or u.role,
                    "relationship_tier": payload.relationship_tier or u.relationship_tier,
                }
            raise HTTPException(status_code=404, detail="User record not found.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@aethergram_router.post("/chat/{chat_id}/clear_messages")
async def clear_chat_messages(chat_id: int, user_id: int = 0) -> Dict[str, Any]:
    """
    Clears local database message history for this chat.
    """
    rbac_guard.verify_king_access(user_id)
    try:
        from sqlalchemy import text
        async with db_manager.session() as session:
            await session.execute(text("DELETE FROM messages WHERE chat_id = :cid"), {"cid": chat_id})
            await session.commit()
        return {"ok": True, "chat_id": chat_id, "message": "تم مسح سجل رسائل المحادثة بنجاح."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@aethergram_router.post("/chat/{chat_id}/send_voice")
async def send_voice_to_chat(chat_id: int, payload: SendVoicePayload) -> Dict[str, Any]:
    """
    Synthesizes custom text into a native Telegram voice note via Edge-TTS and dispatches
    it strictly from the selected account (Userbot or Official Bot).
    """
    rbac_guard.verify_king_access(payload.user_id)

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Voice text cannot be empty.")

    from aether_human_core.multimodal_engine.acoustic_voice.realistic_voice_generator import voice_generator
    voice_path, waveform, duration = await voice_generator.generate_voice_note(
        text_content=payload.text,
        emotional_tone="WARM",
        format_ext="ogg",
        dialect_code="egyptian",
    )

    if not voice_path or not os.path.exists(voice_path):
        raise HTTPException(status_code=500, detail="Failed to synthesize voice audio.")

    is_ub = payload.account_type in ("userbot", "userbot_primary")
    await mtproto_manager.send_voice_note(
        chat_id=chat_id,
        file_path=voice_path,
        waveform=waveform,
        duration=duration,
        is_userbot=is_ub,
        userbot_client=interactive_userbot.client if is_ub else None,
    )
    return {"ok": True, "chat_id": chat_id, "duration": duration, "text": payload.text}


@aethergram_router.get("/chat/{chat_id}/summary")
async def get_chat_summary(chat_id: int, user_id: int = 0) -> Dict[str, Any]:
    """
    Generates a rapid 3-bullet AI summary of recent messages in this chat.
    """
    rbac_guard.verify_king_access(user_id)

    # Gather last 25 messages
    from sqlalchemy import select, desc
    from aether_human_core.database.postgres.models import MessageRecordModel
    msgs_text = []
    try:
        async with db_manager.session() as session:
            stmt = select(MessageRecordModel).where(MessageRecordModel.chat_id == chat_id).order_by(desc(MessageRecordModel.created_at)).limit(25)
            rows = (await session.execute(stmt)).scalars().all()
            for r in reversed(rows):
                sender = "البوت" if r.is_from_bot else "المستخدم"
                msgs_text.append(f"{sender}: {r.text}")
    except Exception:
        pass

    if not msgs_text:
        return {"ok": True, "summary": "لا توجد رسائل كافية لتوليد ملخص بعد."}

    context = "\n".join(msgs_text)
    prompt = f"لخص أهم النقاط في هذه المحادثة في 3 أسطر مباشرة ومفيدة:\n{context}\nالملخص:"
    try:
        summary = await asyncio.wait_for(
            llm_pool.generate_text(
                prompt=prompt,
                system_instruction="أنت مساعد تحليلي تلخص المحادثات بدقة ووضوح في 3 نقاط محددة.",
                max_tokens=250,
                temperature=0.4,
            ),
            timeout=4.0,
        )
        return {"ok": True, "summary": summary.strip()}
    except Exception:
        return {"ok": True, "summary": f"المحادثة تحتوي على {len(msgs_text)} رسالة مسجلة بين الطرفين، وحالة التفاعل طبيعية ومستمرة."}


@aethergram_router.get("/media/{file_id}")
async def get_media_proxy(file_id: str):
    """
    Proxies media files directly from Telegram Bot API or local cache.
    """
    local_path = os.path.join(os.getcwd(), "artifacts", "voice_notes", f"incoming_{file_id}.ogg")
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return Response(content=f.read(), media_type="audio/ogg")

    bot_token = settings.telegram_bot_token
    if bot_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"https://api.telegram.org/bot{bot_token}/getFile", params={"file_id": file_id})
                if res.status_code == 200:
                    fpath = res.json()["result"]["file_path"]
                    dl_res = await client.get(f"https://api.telegram.org/file/bot{bot_token}/{fpath}")
                    if dl_res.status_code == 200:
                        mime = dl_res.headers.get("content-type", "application/octet-stream")
                        return Response(content=dl_res.content, media_type=mime)
        except Exception as exc:
            logger.debug(f"Media proxy exception: {exc}")

    raise HTTPException(status_code=404, detail="Media file not found")


@aethergram_router.get("/chat/{chat_id}/xray")
async def get_chat_ai_xray(chat_id: int, user_id: int = 0) -> Dict[str, Any]:
    """
    Returns deep psychological telemetry: affinity, neuro-hormones, role, and last thoughts.
    """
    rbac_guard.verify_king_access(user_id)

    hormones = endocrine_engine.evaluate_psychological_mood()
    affinity = 0.0
    tier = "STRANGER"
    user_name = "مستخدم"
    role = "MEMBER"

    try:
        async with db_manager.session() as session:
            repo = UserRepository(session)
            u = await repo.get_by_telegram_id(chat_id)
            if u:
                affinity = u.affinity_score
                tier = u.relationship_tier
                user_name = u.first_name
                role = u.role
    except Exception:
        pass

    thought = (
        f"المستخدم [{user_name}] رتبته {role}. بتعامل معاه بطريقة متزنة ومباشرة "
        f"ورصيد معزته {affinity:.1f}/100."
    )

    return {
        "ok": True,
        "chat_id": chat_id,
        "user_name": user_name,
        "role": role,
        "affinity_score": affinity,
        "relationship_tier": tier,
        "hormones": {
            "dopamine": int(hormones.get("dopamine", 0.5) * 100),
            "cortisol": int(hormones.get("cortisol", 0.2) * 100),
            "serotonin": int(hormones.get("serotonin", 0.6) * 100),
            "energy": int(hormones.get("energy", 0.8) * 100),
        },
        "secret_persona": "Omar Damascus 24 (Charismatic Tech)",
        "internal_thought": thought,
        "ai_auto_reply": chat_ai_toggle_registry.get(chat_id, True),
    }


@aethergram_router.post("/chat/{chat_id}/send")
async def send_live_chat_message(chat_id: int, payload: SendMessagePayload) -> Dict[str, Any]:
    """
    Dispatches message directly as Userbot or Official Bot.
    """
    rbac_guard.verify_king_access(payload.user_id)

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    # 1. Send via Userbot
    if payload.account_type in ("userbot", "userbot_primary") and interactive_userbot.client and interactive_userbot.client.is_connected():
        try:
            if await interactive_userbot.client.is_user_authorized():
                sent = await interactive_userbot.client.send_message(
                    chat_id, payload.text, reply_to=payload.reply_to_msg_id
                )
                return {"ok": True, "sender": "userbot", "message_id": sent.id, "text": payload.text}
        except Exception as exc:
            logger.error(f"Userbot send error: {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to send as userbot: {exc}")

    # 2. Send via Bot API
    try:
        await mtproto_manager.send_message(
            chat_id=chat_id,
            text=payload.text,
            reply_to_msg_id=payload.reply_to_msg_id,
        )
        return {"ok": True, "sender": "bot", "text": payload.text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send as bot: {exc}")


@aethergram_router.post("/chat/{chat_id}/toggle_ai")
async def toggle_chat_ai(chat_id: int, payload: ToggleAiPayload) -> Dict[str, Any]:
    """
    Toggles autonomous AI replies on or off for this specific chat.
    """
    rbac_guard.verify_king_access(payload.user_id)
    chat_ai_toggle_registry[chat_id] = payload.enabled
    state_str = "مفعل 🤖" if payload.enabled else "متوقف (الرد يدوي فقط) 🛑"
    return {"ok": True, "chat_id": chat_id, "ai_enabled": payload.enabled, "message": f"تم تعديل وضع الرد الآلي: {state_str}"}


@aethergram_router.post("/chat/{chat_id}/suggest_reply")
async def suggest_smart_reply(chat_id: int, payload: SuggestReplyPayload) -> Dict[str, Any]:
    """
    Uses Gemini LLM to draft an authentic suggestion for King to review/edit before sending.
    """
    rbac_guard.verify_king_access(payload.user_id)

    sys_inst = (
        "أنت شاب مصري ذكي وعمرك 24 سنة. اقترح رداً واحداً ذكياً وطبيعياً وجدعاً "
        "على رسالة المستخدم التالية. اكتب نص الرد المقترح مباشرة بدون أي مقدمات أو علامات تنصيص وبدون فواصل."
    )
    user_p = f"رسالة المستخدم في شات [{payload.chat_title}]: '{payload.last_user_message}'\nالرد المقترح:"

    try:
        suggestion = await llm_pool.generate_text(
            prompt=user_p,
            system_instruction=sys_inst,
            max_tokens=200,
            temperature=0.8,
        )
        clean_sugg = suggestion.replace("،", " ").replace(",", " ").strip()
        return {"ok": True, "suggestion": clean_sugg}
    except Exception as exc:
        return {"ok": False, "suggestion": "تسلم يا غالي منور دايماً والله"}


@aethergram_router.post("/group/{group_id}/add_king")
async def add_king_to_group(group_id: int, user_id: int = 0) -> Dict[str, Any]:
    """
    Adds The King to the target group via Userbot invite or direct addition.
    """
    rbac_guard.verify_king_access(user_id)
    from admin_telemetry_and_archiver.group_privilege_escalator import privilege_escalator
    res = await privilege_escalator.evaluate_and_escalate_king(group_id, "مجموعة تليجرام")
    return {"ok": True, "result": res}


router = aethergram_router
