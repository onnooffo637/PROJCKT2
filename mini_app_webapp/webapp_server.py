"""
Telegram Mini App WebApp Backend & Frontend Server for Project Aether-Human (V2.0).
Provides rich glassmorphism UI, interactive game arena (XO Pro, Connect 4, Mega Trivia, Number Guess, RPS),
live neuro-endocrine mood radar, academic research lab, and Multi-Bot Factory manager with editing.
"""

from __future__ import annotations

import logging
import asyncio
import base64
import os
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine
from aether_human_core.cognitive_engine.persona_shifter import persona_shifter
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from core_config.sovereignty_rules import SovereigntyProtocolService, RoyalRank
from official_bot_engine.game_chat_bridge import game_chat_bridge
from official_bot_engine.academic_research_assistant.research_lab import research_assistant
from mini_app_webapp.games_engine import (
    XOGameSession,
    Connect4Session,
    NumberGuessSession,
    RockPaperScissorsEngine,
    TriviaBank,
)
from bot_factory.models import BotPlatformType, BotGender
from bot_factory.persona_templates import template_registry
from bot_factory.factory_manager import bot_factory
from security_and_rbac.rbac_ui_guard import rbac_guard
from mini_app_webapp.backend_api.mtproto_web_auth_api import router as mtproto_auth_router
from mini_app_webapp.backend_api.aethergram_client_api import router as aethergram_router
from mini_app_webapp.backend_api.custom_persona_and_vault_api import router as custom_persona_and_vault_router

logger = logging.getLogger("Aether.MiniApp.Server")

webapp_router = APIRouter(prefix="", tags=["Telegram Mini App"])

# Mount Sub-Routers
webapp_router.include_router(mtproto_auth_router)
webapp_router.include_router(aethergram_router)
webapp_router.include_router(custom_persona_and_vault_router)

from mini_app_webapp.backend_api.aethergram_client_api import get_media_proxy

@webapp_router.get('/api/media/{file_id}')
async def get_media_proxy_alias(file_id: str):
    return await get_media_proxy(file_id)

# In-memory active game sessions keyed by user_id
xo_sessions: Dict[int, XOGameSession] = {}
c4_sessions: Dict[int, Connect4Session] = {}
guess_sessions: Dict[int, NumberGuessSession] = {}


# ==============================================================================
# Pydantic Request Models
# ==============================================================================

class XOMoveRequest(BaseModel):
    user_id: int
    user_name: str = "اللاعب"
    cell_index: int
    difficulty: str = "easy"
    chat_id: Optional[int] = None


class C4MoveRequest(BaseModel):
    user_id: int
    user_name: str = "اللاعب"
    col_index: int
    difficulty: str = "easy"
    chat_id: Optional[int] = None


class GuessRequest(BaseModel):
    user_id: int
    user_name: str = "اللاعب"
    guess: int
    chat_id: Optional[int] = None


class RPSPlayRequest(BaseModel):
    user_id: int
    user_name: str = "اللاعب"
    choice: str
    chat_id: Optional[int] = None


class TriviaAnswerRequest(BaseModel):
    user_id: int
    user_name: str = "اللاعب"
    question_id: int
    selected_option_index: int
    chat_id: Optional[int] = None


class SummarizeRequest(BaseModel):
    title: str = "المحاضرة"
    content: str


class CreateBotRequest(BaseModel):
    user_id: int = 0
    instance_id: str
    name: str
    bot_type: str = "OFFICIAL_BOT"
    token_or_session: str
    gender: str = "MALE"
    age: int = 22
    bio: str = ""
    template_code: Optional[str] = None
    custom_prompt: Optional[str] = None
    dialect: str = ""
    origin_location: str = ""
    chattiness_level: float = 0.5
    voice_profile: Optional[str] = None
    voice_pitch: int = 0
    voice_rate: int = 0
    custom_rules: str = ""
    relationship_creator: str = ""


class ToggleGenderRequest(BaseModel):
    user_id: int = 0
    instance_id: str
    gender: str


class ApplyTemplateRequest(BaseModel):
    user_id: int = 0
    instance_id: str
    template_code: str


class DeleteBotRequest(BaseModel):
    user_id: int = 0
    instance_id: str


class UpdateBotPersonaRequest(BaseModel):
    user_id: int = 0
    instance_id: str
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    bio: Optional[str] = None
    system_prompt: Optional[str] = None
    primary_dialect: Optional[str] = None
    origin_location: Optional[str] = None
    chattiness_level: Optional[float] = None
    voice_profile: Optional[str] = None
    voice_pitch: Optional[int] = None
    voice_rate: Optional[int] = None
    custom_rules: Optional[str] = None
    relationship_creator: Optional[str] = None
    avatar_url: Optional[str] = None


class UploadBotPhotoRequest(BaseModel):
    user_id: int = 0
    instance_id: str
    image_base64: str


# ==============================================================================
# Dynamic Identity & UTC-to-Bot-Timezone Resolver
# ==============================================================================

def detect_bot_id_from_init_data(init_data: Optional[str]) -> Optional[str]:
    """
    Cryptographically identifies which registered Telegram Bot opened the Mini App
    by verifying Telegram's WebApp `initData` HMAC-SHA256 signature against all bot tokens
    in `bot_factory`. Works even if Telegram's client cached an older URL without `?bot_id=`.
    """
    if not init_data or "hash=" not in init_data:
        return None
    try:
        import hashlib
        import hmac
        from urllib.parse import parse_qsl

        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        for b in bot_factory.list_all_bots():
            token = (b.token_or_session or "").strip()
            if not token or ":" not in token:
                continue
            secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
            computed_hash = hmac.new(
                secret_key, data_check_string.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed_hash, received_hash):
                return b.instance_id
    except Exception as exc:
        logger.debug(f"initData HMAC bot detection notice: {exc}")
    return None


def resolve_display_identity(
    user_id: int,
    bot_id: Optional[str] = None,
    init_data: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolves active header brand, title, country, flag, IANA timezone, and UTC-derived local time:
    1. If `bot_id` is provided (or detected from Telegram `init_data` HMAC signature, or matched by name/id),
       resolves that specific bot's country, flag, and UTC-converted local time via `TimezoneResolver`.
    2. If `bot_id` is `master_omar_official` (or empty) and the user has a custom DM persona, resolves custom persona.
    3. Otherwise resolves Master Omar (`master_omar_official`).
    """
    from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
    from utils.timezone_resolver import TimezoneResolver

    AVATAR_MALE = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=150&q=80"
    AVATAR_FEMALE = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=150&q=80"

    effective_bot_id = (bot_id or "").strip()
    if not effective_bot_id and init_data:
        detected = detect_bot_id_from_init_data(init_data)
        if detected:
            effective_bot_id = detected

    # Strict Multi-Admin Isolation: if user is a secondary factory admin (e.g. Marselin 8697154015)
    # and did not pass an owned bot_id (or passed master_omar_official), auto-resolve to their first owned bot!
    if user_id and bot_factory.is_factory_admin(user_id) and not bot_factory.is_supreme_king(user_id):
        if not effective_bot_id or not bot_factory.can_user_manage_bot(user_id, effective_bot_id):
            owned_bots = bot_factory.list_bots_for_user(user_id)
            if owned_bots:
                effective_bot_id = owned_bots[0].instance_id
                bot_id = effective_bot_id

    # Priority 1: Explicit Factory Bot (Sub-Bot, Userbot, or explicitly selected Master Omar)
    if effective_bot_id:
        f_bot = bot_factory.get_bot(effective_bot_id) or bot_factory.get_bot_by_name(effective_bot_id)
        if f_bot and (f_bot.instance_id != "master_omar_official" or bot_id == "master_omar_official"):
            gender = "female" if f_bot.gender.value == "FEMALE" else "male"
            avatar = f_bot.avatar_url or (AVATAR_FEMALE if gender == "female" else AVATAR_MALE)
            dialect = f_bot.primary_dialect or "egyptian"
            origin_loc = getattr(f_bot, "origin_location", "") or ""
            tz_info = TimezoneResolver.resolve_bot_timezone(
                origin_location=origin_loc,
                primary_dialect=dialect,
                system_prompt=f_bot.system_prompt or "",
                bio=f_bot.bio or "",
            )
            is_master = (f_bot.instance_id == "master_omar_official")
            return {
                "priority": 1,
                "source": "master_omar" if is_master else "factory_bot",
                "bot_id": f_bot.instance_id,
                "name": "عمر" if is_master else f_bot.name,
                "display_title": "عمر Aether Core 3.0" if is_master else f"{f_bot.name} ✨",
                "badge": f_bot.bio or ("الجدع المعاصر" if is_master else ("فتاة ذكية ومتفاعلة" if gender == "female" else "كيان ذكي معاصر")),
                "description": (f_bot.system_prompt or "")[:80],
                "gender": gender,
                "dialect": dialect,
                "origin_location": origin_loc or tz_info["country_ar"],
                "flag": tz_info["flag"],
                "country": tz_info["country_ar"],
                "city": tz_info["city_country_ar"],
                "city_only": tz_info["city_ar"],
                "capsule_location": tz_info["capsule_location_ar"],
                "iana_timezone": tz_info["iana_timezone"],
                "utc_offset_hours": tz_info["utc_offset_hours"],
                "avatar_url": avatar,
                "time_str": tz_info["formatted_time_ar"],
                "raw_time_24h": tz_info["raw_time_24h"],
                "utc_iso": tz_info["utc_iso"],
            }

    # Priority 2: User-Scoped Custom Persona
    user_p = persona_virtualizer.get_persona(user_id) if user_id else None
    if user_p and user_p.is_custom:
        dialect = user_p.dialect or "egyptian"
        gender = user_p.gender or "male"
        avatar = AVATAR_FEMALE if gender == "female" else AVATAR_MALE
        tz_info = TimezoneResolver.resolve_bot_timezone(
            origin_location="",
            primary_dialect=dialect,
            system_prompt=user_p.custom_system_prompt or "",
            bio=user_p.avatar_description or "",
        )
        return {
            "priority": 2,
            "source": "user_custom",
            "bot_id": "master_omar_official",
            "name": user_p.persona_name,
            "display_title": f"{user_p.persona_name} ✨",
            "badge": user_p.avatar_description or ("شخصية مخصصة ذكية" if gender == "female" else "شخصية مخصصة"),
            "description": user_p.custom_system_prompt or "شخصيتك المخصصة المستقلة",
            "gender": gender,
            "dialect": dialect,
            "origin_location": tz_info["country_ar"],
            "flag": tz_info["flag"],
            "country": tz_info["country_ar"],
            "city": tz_info["city_country_ar"],
            "city_only": tz_info["city_ar"],
            "capsule_location": tz_info["capsule_location_ar"],
            "iana_timezone": tz_info["iana_timezone"],
            "utc_offset_hours": tz_info["utc_offset_hours"],
            "avatar_url": avatar,
            "time_str": tz_info["formatted_time_ar"],
            "raw_time_24h": tz_info["raw_time_24h"],
            "utc_iso": tz_info["utc_iso"],
        }

    # Priority 3: Default Fallback - Omar Master Bot
    master_bot = bot_factory.get_bot("master_omar_official")
    tz_info = TimezoneResolver.resolve_bot_timezone(
        origin_location=getattr(master_bot, "origin_location", "") if master_bot else "",
        primary_dialect=getattr(master_bot, "primary_dialect", "egyptian") if master_bot else "egyptian",
        system_prompt=getattr(master_bot, "system_prompt", "") if master_bot else "",
        bio=getattr(master_bot, "bio", "") if master_bot else "",
    )
    return {
        "priority": 3,
        "source": "master_omar",
        "bot_id": "master_omar_official",
        "name": "عمر",
        "display_title": "عمر Aether Core 3.0",
        "badge": "الجدع المعاصر",
        "description": "شاب مصري معاصر صاحب صاحبك وجدع جداً",
        "gender": "male",
        "dialect": "egyptian",
        "origin_location": tz_info["country_ar"],
        "flag": tz_info["flag"],
        "country": tz_info["country_ar"],
        "city": tz_info["city_country_ar"],
        "city_only": tz_info["city_ar"],
        "capsule_location": tz_info["capsule_location_ar"],
        "iana_timezone": tz_info["iana_timezone"],
        "utc_offset_hours": tz_info["utc_offset_hours"],
        "avatar_url": AVATAR_MALE,
        "time_str": tz_info["formatted_time_ar"],
        "raw_time_24h": tz_info["raw_time_24h"],
        "utc_iso": tz_info["utc_iso"],
    }


def _serialize_bot_with_timezone(b: Any) -> Dict[str, Any]:
    """
    Serializes a BotInstanceConfig with its live UTC-derived timezone, flag, and capsule location.
    """
    from utils.timezone_resolver import TimezoneResolver

    d = b.model_dump()
    tz_info = TimezoneResolver.resolve_bot_timezone(
        origin_location=getattr(b, "origin_location", "") or "",
        primary_dialect=getattr(b, "primary_dialect", "") or "",
        system_prompt=getattr(b, "system_prompt", "") or "",
        bio=getattr(b, "bio", "") or "",
    )
    d["flag"] = tz_info["flag"]
    d["country_ar"] = tz_info["country_ar"]
    d["city_ar"] = tz_info["city_ar"]
    d["capsule_location"] = tz_info["capsule_location_ar"]
    d["iana_timezone"] = tz_info["iana_timezone"]
    d["utc_offset_hours"] = tz_info["utc_offset_hours"]
    d["time_str"] = tz_info["formatted_time_ar"]
    return d


@webapp_router.get("/api/webapp/identity")
async def get_webapp_identity(
    user_id: int = 0,
    bot_id: Optional[str] = None,
    init_data: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns resolved header brand identity and UTC-derived bot timezone clock.
    """
    return resolve_display_identity(user_id, bot_id, init_data=init_data)


# ==============================================================================
# API Endpoints: Unified Telemetry
# ==============================================================================

@webapp_router.get("/api/webapp/state")
async def get_webapp_unified_state(
    user_id: int = 0,
    bot_id: Optional[str] = None,
    init_data: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns live brain telemetry, active persona, UTC-derived bot clock/flag/country, user affinity, and leaderboard.
    """
    identity = resolve_display_identity(user_id, bot_id, init_data=init_data)
    hormones = endocrine_engine.evaluate_psychological_mood()
    circadian = circadian_engine.evaluate_circadian_state()
    active_persona = persona_shifter.get_active_persona()
    is_supreme = rbac_guard.is_supreme_king(user_id)
    is_king = rbac_guard.is_factory_admin(user_id)

    user_info = {
        "user_id": user_id,
        "is_king": is_king,
        "is_supreme_king": is_supreme,
        "is_factory_admin": is_king,
        "affinity": 100.0 if is_supreme else (95.0 if is_king else 25.0),
        "tier": "The Supreme King" if is_supreme else ("Royal Dev" if is_king else "Member"),
        "rank_title": RoyalRank.get_display_name_ar(
            RoyalRank.THE_KING if is_supreme else (RoyalRank.ROYAL_DEV if is_king else RoyalRank.MEMBER)
        ),
    }

    leaderboard = []
    try:
        async with db_manager.session() as session:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_by_telegram_id(user_id)
            if db_user:
                user_info["affinity"] = 100.0 if is_king else round(db_user.affinity_score, 1)
                user_info["tier"] = db_user.relationship_tier
                role_str = (db_user.role or "MEMBER").upper()
                if is_king:
                    effective_rank = RoyalRank.THE_KING
                elif role_str == "SUPER_ADMIN":
                    effective_rank = RoyalRank.ROYAL_DEV
                else:
                    try:
                        effective_rank = RoyalRank(role_str)
                    except ValueError:
                        effective_rank = RoyalRank.MEMBER
                user_info["rank_title"] = RoyalRank.get_display_name_ar(effective_rank)

            top_users = await user_repo.get_top_affinity_users(limit=10)
            for u in top_users:
                u_is_king = SovereigntyProtocolService.is_the_king(u.telegram_id)
                role_str = (u.role or "MEMBER").upper()
                if u_is_king:
                    u_rank = RoyalRank.THE_KING
                elif role_str == "SUPER_ADMIN":
                    u_rank = RoyalRank.ROYAL_DEV
                else:
                    try:
                        u_rank = RoyalRank(role_str)
                    except ValueError:
                        u_rank = RoyalRank.MEMBER

                leaderboard.append({
                    "user_id": u.telegram_id,
                    "name": u.first_name,
                    "affinity": 100.0 if u_is_king else round(u.affinity_score, 1),
                    "tier": "The Supreme King 👑" if u_is_king else u.relationship_tier,
                    "role": RoyalRank.get_display_name_ar(u_rank),
                })
    except Exception as exc:
        logger.warning(f"Could not fetch full DB state for WebApp: {exc}")

    if not leaderboard:
        leaderboard = [
            {"user_id": getattr(settings, "the_king_user_id", 0), "name": "The Supreme King 👑", "affinity": 100.0, "tier": "The Supreme King 👑", "role": "👑 جلالة الملك وصانع النظام"},
            {"user_id": 8697154015, "name": "مهندس البلاط الملكي ⚡", "affinity": 95.0, "tier": "Royal Dev", "role": "⚡ مهندس البلاط الملكي"},
            {"user_id": 1000000001, "name": "ماسة 👧 (AI Engineer)", "affinity": 88.0, "tier": "King's VIP", "role": "💎 خاصّة الملك والمقربون"},
            {"user_id": 1000000002, "name": "عمر 👦 (Master Bot)", "affinity": 85.0, "tier": "Brother", "role": "⭐ مسؤول معتمد"},
            {"user_id": 1000000003, "name": "مريم 👧 (Psychologist)", "affinity": 80.0, "tier": "VIP", "role": "🌟 عضو شرف مميز"},
        ]

    c_hour = circadian.get("hour", 2) if isinstance(circadian, dict) else 2
    c_phase = circadian.get("state_name", "ACTIVE") if isinstance(circadian, dict) else "ACTIVE"
    c_alertness = circadian.get("alertness", 1.0) if isinstance(circadian, dict) else 1.0
    c_melatonin = round(1.0 - c_alertness, 2)

    hormones_payload = hormones.copy() if isinstance(hormones, dict) else hormones.model_dump()
    if "mood_label" not in hormones_payload:
        hormones_payload["mood_label"] = hormones_payload.get("mood_ar", "طبيعي ومستقر")

    utc_off = identity.get("utc_offset_hours", 2.0)
    utc_off_int = int(utc_off) if float(utc_off).is_integer() else utc_off
    utc_sign = "+" if utc_off >= 0 else ""

    if bot_factory.is_factory_admin(user_id):
        scoped_bots = bot_factory.list_bots_for_user(user_id)
    else:
        cur_bot = bot_factory.get_bot(identity.get("bot_id", ""))
        scoped_bots = [cur_bot] if cur_bot else []

    raw_state = {
        "identity": identity,
        "available_bots": [_serialize_bot_with_timezone(b) for b in scoped_bots],
        "hormones": hormones_payload,
        "circadian": {
            "time_str": identity["time_str"],
            "timezone": f"{identity['city']} (UTC{utc_sign}{utc_off_int})",
            "iana_timezone": identity.get("iana_timezone", "Africa/Cairo"),
            "utc_offset_hours": utc_off,
            "capsule_location": identity.get("capsule_location", "القاهرة"),
            "flag": identity.get("flag", "🇪🇬"),
            "hour": c_hour,
            "phase": c_phase,
            "melatonin": c_melatonin,
            "alertness": c_alertness,
        },
        "persona": {
            "name_ar": identity["name"],
            "code": getattr(active_persona, "code", "DEFAULT_BALANCED"),
            "description": identity["badge"],
            "traits": getattr(active_persona, "typical_reactions", []),
        },
        "user": user_info,
        "leaderboard": leaderboard,
    }
    return rbac_guard.filter_webapp_state_for_user(user_id, raw_state)


# ==============================================================================
# API Endpoints: Games Arena
# ==============================================================================

# 1. XO Pro
@webapp_router.post("/api/webapp/game/xo/move")
async def handle_xo_move(req: XOMoveRequest) -> Dict[str, Any]:
    if req.user_id not in xo_sessions or xo_sessions[req.user_id].game_over:
        xo_sessions[req.user_id] = XOGameSession(req.user_id)

    session = xo_sessions[req.user_id]
    success, result_type = session.user_move(req.cell_index, difficulty=req.difficulty)

    if not success:
        return {"success": False, "message": result_type, "state": session.get_state()}

    bridge_result = None
    if session.game_over:
        outcome = "USER_WON" if session.winner == "X" else ("OMAR_WON" if session.winner == "O" else "DRAW")
        bridge_result = await game_chat_bridge.process_game_outcome(
            game_name="XO (Tic-Tac-Toe)",
            user_id=req.user_id,
            user_name=req.user_name,
            outcome=outcome,
            chat_id=req.chat_id,
        )

    return {
        "success": True,
        "state": session.get_state(),
        "bridge": bridge_result.model_dump() if bridge_result else None,
    }


@webapp_router.post("/api/webapp/game/xo/reset")
async def reset_xo_game(user_id: int = Body(..., embed=True)) -> Dict[str, Any]:
    xo_sessions[user_id] = XOGameSession(user_id)
    return {"success": True, "state": xo_sessions[user_id].get_state()}


# 2. Connect 4 (أربعة على التوالي)
@webapp_router.post("/api/webapp/game/c4/move")
async def handle_c4_move(req: C4MoveRequest) -> Dict[str, Any]:
    if req.user_id not in c4_sessions or c4_sessions[req.user_id].game_over:
        c4_sessions[req.user_id] = Connect4Session(req.user_id)

    session = c4_sessions[req.user_id]
    success, result_type, row = session.drop_piece(req.col_index, difficulty=req.difficulty)

    if not success:
        return {"success": False, "message": result_type, "state": session.get_state()}

    bridge_result = None
    if session.game_over:
        outcome = "USER_WON" if session.winner == "USER" else ("OMAR_WON" if session.winner == "OMAR" else "DRAW")
        bridge_result = await game_chat_bridge.process_game_outcome(
            game_name="أربعة على التوالي (Connect 4)",
            user_id=req.user_id,
            user_name=req.user_name,
            outcome=outcome,
            chat_id=req.chat_id,
        )

    return {
        "success": True,
        "state": session.get_state(),
        "row_landed": row,
        "bridge": bridge_result.model_dump() if bridge_result else None,
    }


@webapp_router.post("/api/webapp/game/c4/reset")
async def reset_c4_game(user_id: int = Body(..., embed=True)) -> Dict[str, Any]:
    c4_sessions[user_id] = Connect4Session(user_id)
    return {"success": True, "state": c4_sessions[user_id].get_state()}


# 3. Number Guessing (خمن الرقم 1-100)
@webapp_router.post("/api/webapp/game/guess/submit")
async def handle_guess_submit(req: GuessRequest) -> Dict[str, Any]:
    if req.user_id not in guess_sessions or guess_sessions[req.user_id].game_over:
        guess_sessions[req.user_id] = NumberGuessSession(req.user_id)

    session = guess_sessions[req.user_id]
    result = session.make_guess(req.guess)

    bridge_result = None
    if session.game_over and result.get("status") == "WIN":
        bridge_result = await game_chat_bridge.process_game_outcome(
            game_name="خمن الرقم السري (1-100)",
            user_id=req.user_id,
            user_name=req.user_name,
            outcome="USER_WON",
            chat_id=req.chat_id,
        )

    return {
        "success": True,
        "result": result,
        "bridge": bridge_result.model_dump() if bridge_result else None,
    }


@webapp_router.post("/api/webapp/game/guess/reset")
async def reset_guess_game(user_id: int = Body(..., embed=True)) -> Dict[str, Any]:
    guess_sessions[user_id] = NumberGuessSession(user_id)
    return {"success": True, "message": "تم اختيار رقم سري جديد بين 1 و 100!"}


# 4. Rock Paper Scissors (حجرة ورقة مقص)
@webapp_router.post("/api/webapp/game/rps/play")
async def handle_rps_play(req: RPSPlayRequest) -> Dict[str, Any]:
    res = RockPaperScissorsEngine.play_round(req.choice, req.user_name)
    bridge_result = await game_chat_bridge.process_game_outcome(
        game_name="حجرة ورقة مقص",
        user_id=req.user_id,
        user_name=req.user_name,
        outcome=res.get("outcome", "DRAW"),
        chat_id=req.chat_id,
    )
    return {
        "success": True,
        "result": res,
        "bridge": bridge_result.model_dump() if bridge_result else None,
    }


# 5. Trivia Quiz
@webapp_router.get("/api/webapp/game/trivia/question")
async def get_trivia_question() -> Dict[str, Any]:
    q = TriviaBank.get_random_question()
    return {
        "id": q.id,
        "category": q.category,
        "question": q.question,
        "options": q.options,
    }


@webapp_router.post("/api/webapp/game/trivia/answer")
async def evaluate_trivia_answer(req: TriviaAnswerRequest) -> Dict[str, Any]:
    q = TriviaBank.get_question_by_id(req.question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = (req.selected_option_index == q.correct_index)
    outcome = "TRIVIA_CORRECT" if is_correct else "TRIVIA_WRONG"

    bridge_res = await game_chat_bridge.process_game_outcome(
        game_name="تحدي الأسئلة والذكاء (Trivia)",
        user_id=req.user_id,
        user_name=req.user_name,
        outcome=outcome,
        chat_id=req.chat_id,
    )

    return {
        "is_correct": is_correct,
        "correct_index": q.correct_index,
        "explanation": q.explanation,
        "bridge": bridge_res.model_dump(),
    }


# ==============================================================================
# API Endpoints: Research Lab & Factory
# ==============================================================================

@webapp_router.post("/api/webapp/research/summarize")
async def summarize_lecture_notes(req: SummarizeRequest) -> Dict[str, Any]:
    if not req.content or len(req.content.strip()) < 10:
        raise HTTPException(status_code=400, detail="المحتوى قصير جداً للتلخيص")

    summary = await research_assistant.summarize_document(
        document_text=req.content,
        document_name=req.title,
    )
    s_payload = summary.model_dump()
    s_payload["concise_summary"] = summary.executive_summary
    s_payload["key_takeaways"] = summary.exam_critical_takeaways or summary.core_mechanisms
    return {"summary": s_payload}


@webapp_router.get("/api/webapp/auth/role")
async def get_user_role(user_id: int = 0) -> Dict[str, Any]:
    is_king = rbac_guard.is_factory_admin(user_id)
    is_supreme = rbac_guard.is_supreme_king(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "is_king": is_king,
        "is_supreme_king": is_supreme,
        "role": "SUPREME_KING" if is_supreme else ("FACTORY_ADMIN" if is_king else "USER"),
    }


@webapp_router.get("/api/webapp/bot_avatar/{bot_id}")
async def get_bot_avatar_image(bot_id: str):
    safe_id = "".join(c for c in bot_id if c.isalnum() or c in ("_", "-"))
    local_path = os.path.join("artifacts", "bot_avatars", f"{safe_id}.jpg")
    if os.path.exists(local_path):
        return FileResponse(local_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Bot avatar not found")


@webapp_router.get("/api/webapp/factory/bots")
async def get_factory_bots(user_id: int = 0) -> Dict[str, Any]:
    rbac_guard.verify_king_access(user_id)
    bots = bot_factory.list_bots_for_user(user_id)
    return {"bots": [_serialize_bot_with_timezone(b) for b in bots]}


@webapp_router.get("/api/webapp/factory/templates")
async def get_factory_templates(user_id: int = 0) -> Dict[str, Any]:
    rbac_guard.verify_king_access(user_id)
    return {"templates": template_registry.list_all_templates()}


@webapp_router.post("/api/webapp/factory/create")
async def create_factory_bot(req: CreateBotRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    b_type = BotPlatformType.OFFICIAL_BOT if req.bot_type == "OFFICIAL_BOT" else BotPlatformType.MTPROTO_USERBOT
    b_gender = BotGender.FEMALE if req.gender == "FEMALE" else BotGender.MALE

    ok, msg, instance = bot_factory.create_bot(
        instance_id=req.instance_id,
        name=req.name,
        bot_type=b_type,
        token_or_session=req.token_or_session,
        gender=b_gender,
        age=getattr(req, "age", 22),
        template_code=req.template_code or "CUSTOM_FREEFORM",
        custom_prompt=req.custom_prompt,
        bio=getattr(req, "bio", ""),
        dialect=req.dialect or "",
        origin_location=getattr(req, "origin_location", ""),
        chattiness_level=getattr(req, "chattiness_level", 0.5),
        voice_profile=getattr(req, "voice_profile", None),
        voice_pitch=getattr(req, "voice_pitch", 0),
        voice_rate=getattr(req, "voice_rate", 0),
        custom_rules=getattr(req, "custom_rules", ""),
        relationship_creator=getattr(req, "relationship_creator", ""),
        owner_id=req.user_id or (settings.the_king_user_id if hasattr(settings, "the_king_user_id") else 0),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if instance:
        try:
            from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
            asyncio.create_task(multi_bot_dispatcher.push_botfather_profile_update(instance))
        except Exception as e:
            logger.debug(f"BotFather profile sync notice on create: {e}")
    return {
        "success": True,
        "message": msg,
        "bot": _serialize_bot_with_timezone(instance) if instance else None,
        "identity": resolve_display_identity(req.user_id, instance.instance_id) if instance else None,
    }


@webapp_router.post("/api/webapp/factory/toggle_gender")
async def toggle_factory_bot_gender(req: ToggleGenderRequest) -> Dict[str, Any]:
    rbac_guard.verify_bot_ownership(req.user_id, req.instance_id)
    new_gender = BotGender.FEMALE if req.gender.upper() == "FEMALE" else BotGender.MALE
    ok, msg = bot_factory.set_bot_gender(req.instance_id, new_gender)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "identity": resolve_display_identity(req.user_id, req.instance_id),
    }


@webapp_router.post("/api/webapp/factory/apply_template")
async def apply_factory_bot_template(req: ApplyTemplateRequest) -> Dict[str, Any]:
    rbac_guard.verify_bot_ownership(req.user_id, req.instance_id)
    ok, msg = bot_factory.set_bot_template(req.instance_id, req.template_code)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@webapp_router.post("/api/webapp/factory/delete")
async def delete_factory_bot(req: DeleteBotRequest) -> Dict[str, Any]:
    rbac_guard.verify_bot_ownership(req.user_id, req.instance_id)
    ok, msg = bot_factory.delete_bot(req.instance_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


@webapp_router.post("/api/webapp/factory/update")
async def update_factory_bot_persona(req: UpdateBotPersonaRequest) -> Dict[str, Any]:
    rbac_guard.verify_bot_ownership(req.user_id, req.instance_id)
    gender_enum = None
    if req.gender:
        gender_enum = BotGender.FEMALE if req.gender.upper() == "FEMALE" else BotGender.MALE

    ok, msg, bot = bot_factory.update_bot_persona(
        instance_id=req.instance_id,
        name=req.name,
        gender=gender_enum,
        age=req.age,
        bio=req.bio,
        system_prompt=req.system_prompt,
        primary_dialect=req.primary_dialect,
        origin_location=req.origin_location,
        chattiness_level=req.chattiness_level,
        voice_profile=req.voice_profile,
        voice_pitch=req.voice_pitch,
        voice_rate=req.voice_rate,
        custom_rules=req.custom_rules,
        relationship_creator=req.relationship_creator,
        avatar_url=req.avatar_url,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if bot:
        try:
            from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
            await multi_bot_dispatcher.push_botfather_profile_update(bot)
        except Exception as e:
            logger.debug(f"BotFather profile sync notice on update: {e}")
    return {
        "success": True,
        "message": msg,
        "bot": _serialize_bot_with_timezone(bot) if bot else None,
        "identity": resolve_display_identity(req.user_id, bot.instance_id) if bot else None,
    }


@webapp_router.post("/api/webapp/factory/upload_photo")
async def upload_factory_bot_photo(req: UploadBotPhotoRequest) -> Dict[str, Any]:
    """
    Uploads and pushes a new BotFather profile photo (`setMyProfilePhoto`) for a managed bot
    directly from the Mini-App or Admin Dashboard.
    """
    rbac_guard.verify_bot_ownership(req.user_id, req.instance_id)
    bot = bot_factory.get_bot(req.instance_id)
    if not bot:
        raise HTTPException(status_code=404, detail="البوت غير موجود")

    b64_str = (req.image_base64 or "").strip()
    if "," in b64_str and b64_str.startswith("data:"):
        b64_str = b64_str.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(b64_str)
    except Exception:
        raise HTTPException(status_code=400, detail="صيغة الصورة غير صالحة (Base64)")

    from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher
    ok, msg = await multi_bot_dispatcher.upload_botfather_profile_photo(bot, img_bytes)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {
        "success": True,
        "message": msg,
        "bot": _serialize_bot_with_timezone(bot),
        "identity": resolve_display_identity(req.user_id, bot.instance_id),
    }




# ==============================================================================
# Task 4.1 & 4.2: Bot Arena (حوار البوتات الحي في الجروبات) Mini-App API
# ==============================================================================

class BotArenaStartRequest(BaseModel):
    user_id: int = 0
    chat_id: int
    rounds: str = "infinite"  # "5", "10", "20", or "infinite"
    topic: Optional[str] = ""


class BotArenaStopRequest(BaseModel):
    user_id: int = 0
    chat_id: int


class BotArenaTopicRequest(BaseModel):
    user_id: int = 0
    chat_id: Optional[int] = None


@webapp_router.get("/api/webapp/arena/status")
async def get_bot_arena_status(user_id: int = 0) -> Dict[str, Any]:
    rbac_guard.verify_king_access(user_id)
    from bot_factory.sibling_bot_network import sibling_network
    groups = await sibling_network.get_known_groups_async()
    sessions = sibling_network.get_all_arena_sessions()
    return {
        "success": True,
        "groups": groups,
        "sessions": sessions,
        "topics": sibling_network.ARENA_RANDOM_TOPICS,
    }


@webapp_router.post("/api/webapp/arena/start")
async def start_bot_arena_api(req: BotArenaStartRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    rounds_str = str(req.rounds or "infinite").strip().lower()
    if rounds_str in ("infinite", "open", "0", "∞"):
        max_rounds = 999999
    else:
        try:
            max_rounds = max(1, int(rounds_str))
        except ValueError:
            max_rounds = 999999

    session = await sibling_network.start_bot_arena(
        chat_id=req.chat_id,
        max_rounds=max_rounds,
        topic=(req.topic or "").strip() or None,
        started_by=req.user_id,
    )
    rounds_ar = "مفتوح حتى الإيقاف" if max_rounds >= 999999 else f"{max_rounds} جولات"
    return {
        "success": True,
        "message": f"🔥 تم تشغيل حوار البوتات الحي في {session.chat_title} ({rounds_ar})!",
        "session": session.to_dict(),
    }


@webapp_router.post("/api/webapp/arena/stop")
async def stop_bot_arena_api(req: BotArenaStopRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    stopped = await sibling_network.stop_bot_arena(
        chat_id=req.chat_id,
        reason="إيقاف مباشر من لوحة التطبيق المصغر (Mini-App)",
    )
    sess = sibling_network.get_arena_session(req.chat_id)
    return {
        "success": True,
        "stopped": stopped,
        "message": "🛑 تم إيقاف حوار البوتات فوراً!" if stopped else "ℹ️ الحوار متوقف بالفعل في هذا الجروب.",
        "session": sess.to_dict() if sess else None,
    }


@webapp_router.post("/api/webapp/arena/topic")
async def pick_bot_arena_random_topic_api(req: BotArenaTopicRequest) -> Dict[str, Any]:
    rbac_guard.verify_king_access(req.user_id)
    from bot_factory.sibling_bot_network import sibling_network
    new_topic = sibling_network.pick_random_arena_topic(req.chat_id)
    return {
        "success": True,
        "topic": new_topic,
        "message": f"🎲 تم اختيار موضوع جديد: {new_topic}",
    }


# ==============================================================================
# HTML Mini App Single-Page Application
# ==============================================================================

import os

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.html")


@webapp_router.get("/webapp", response_class=HTMLResponse)
async def serve_telegram_mini_app() -> HTMLResponse:
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = "<h1>Aether Mini App</h1>"

    return HTMLResponse(
        content=html_content,
        headers={
            "Content-Security-Policy": "frame-ancestors * https://web.telegram.org https://*.telegram.org https://telegram.org;",
            "Access-Control-Allow-Origin": "*",
        },
    )
