"""
Custom Persona, Custom Commands, Memory Vault, Debate & Voice Hub API (V3.0, V4.0 & V5.0).
Provides full WebApp integration for multi-tenant isolated persona virtualization,
custom commands compilation, time capsules, and voice scheduler.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer, TenantPersona
from multi_tenant_sandbox.custom_command_compiler import custom_commands
from multi_tenant_sandbox.linguistic_dna_cloner import LinguisticDNACloner
from multi_tenant_sandbox.multi_persona_debate import MultiPersonaDebater
from live_voip_call_engine.outbound_call_scheduler import outbound_call_scheduler

logger = logging.getLogger("Aether.WebApp.CustomPersonaAPI")

router = APIRouter(prefix="/api/webapp", tags=["Custom Persona & Features"])

CAPSULES_FILE = "data/time_capsules.json"


def _load_capsules() -> List[Dict[str, Any]]:
    if not os.path.exists(CAPSULES_FILE):
        return []
    try:
        with open(CAPSULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_capsules(capsules: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(CAPSULES_FILE), exist_ok=True)
    with open(CAPSULES_FILE, "w", encoding="utf-8") as f:
        json.dump(capsules, f, ensure_ascii=False, indent=2)


# ==========================================
# 1. Persona Studio Endpoints
# ==========================================

class PersonaUpdateRequest(BaseModel):
    user_id: int
    persona_name: Optional[str] = None
    gender: Optional[str] = None
    dialect: Optional[str] = None
    tone: Optional[str] = None
    humor_level: Optional[float] = None
    sarcasm_level: Optional[float] = None
    empathy_level: Optional[float] = None
    formality_level: Optional[float] = None
    avatar_description: Optional[str] = None
    custom_system_prompt: Optional[str] = None
    voice_preset: Optional[str] = None


class StyleCloneRequest(BaseModel):
    user_id: int
    sample_text: str


class ResetPersonaRequest(BaseModel):
    user_id: int


@router.get("/persona")
async def get_persona(user_id: int = Query(...)):
    """Fetches user isolated persona."""
    persona = persona_virtualizer.get_persona(user_id)
    return {
        "status": "success",
        "persona": {
            "user_id": persona.user_id,
            "persona_name": persona.persona_name,
            "gender": persona.gender,
            "dialect": persona.dialect,
            "tone": persona.tone,
            "humor_level": persona.humor_level,
            "sarcasm_level": persona.sarcasm_level,
            "empathy_level": persona.empathy_level,
            "formality_level": persona.formality_level,
            "avatar_description": persona.avatar_description,
            "custom_system_prompt": persona.custom_system_prompt,
            "voice_preset": persona.voice_preset,
            "cloned_dna": persona.cloned_linguistic_dna,
            "updated_at": persona.updated_at,
        }
    }


@router.post("/persona/update")
async def update_persona(req: PersonaUpdateRequest):
    """Updates tenant custom persona configuration."""
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None and k != "user_id"}
    updated = persona_virtualizer.update_persona(req.user_id, **kwargs)
    return {
        "status": "success",
        "message": f"تم تحديث شخصيتك الخاصة ({updated.persona_name}) بنجاح!",
        "persona": {
            "persona_name": updated.persona_name,
            "gender": updated.gender,
            "dialect": updated.dialect,
            "tone": updated.tone,
            "updated_at": updated.updated_at,
        }
    }


@router.post("/persona/clone_style")
async def clone_style(req: StyleCloneRequest):
    """Clones linguistic DNA from sample text and binds to user's persona."""
    if not req.sample_text or len(req.sample_text.strip()) < 5:
        raise HTTPException(status_code=400, detail="النص المرسل قصير جداً لتحليل البصمة اللغوية.")
    dna = LinguisticDNACloner.clone_and_apply_to_user(req.user_id, req.sample_text)
    persona = persona_virtualizer.get_persona(req.user_id)
    return {
        "status": "success",
        "message": "تم استنساخ بصمتك اللغوية وتطبيقها بنجاح!",
        "cloned_dna": dna,
        "persona_dialect": persona.dialect,
    }


@router.post("/persona/reset")
async def reset_persona(req: ResetPersonaRequest):
    """Resets persona to default Omar."""
    default_p = persona_virtualizer.reset_persona(req.user_id)
    return {
        "status": "success",
        "message": "تمت استعادة شخصية عمر الافتراضية بنجاح!",
        "persona_name": default_p.persona_name,
    }


# ==========================================
# 2. Custom Commands Endpoints
# ==========================================

class CommandAddRequest(BaseModel):
    user_id: int
    trigger: str
    action: str = "reply"
    response_template: str
    description: str = ""


class CommandDeleteRequest(BaseModel):
    user_id: int
    trigger: str


@router.get("/commands")
async def list_custom_commands(user_id: int = Query(...)):
    """Lists all custom commands registered by this user."""
    cmds = custom_commands.list_commands(user_id)
    return {
        "status": "success",
        "commands": [
            {
                "trigger": c.trigger,
                "action": c.action,
                "response_template": c.response_template,
                "description": c.description,
                "usage_count": c.usage_count,
                "created_at": c.created_at,
            }
            for c in cmds
        ]
    }


@router.post("/commands/add")
async def add_custom_command(req: CommandAddRequest):
    """Registers a new custom command for the user."""
    cmd = custom_commands.register_command(
        user_id=req.user_id,
        trigger=req.trigger,
        action=req.action,
        response_template=req.response_template,
        description=req.description,
    )
    return {
        "status": "success",
        "message": f"تمت إضافة الأمر الشخصي {cmd.trigger} بنجاح!",
        "command": {
            "trigger": cmd.trigger,
            "action": cmd.action,
            "description": cmd.description,
        }
    }


@router.post("/commands/delete")
async def delete_custom_command(req: CommandDeleteRequest):
    """Deletes a user custom command."""
    ok = custom_commands.delete_command(req.user_id, req.trigger)
    if not ok:
        raise HTTPException(status_code=404, detail="الأمر غير موجود.")
    return {"status": "success", "message": f"تم حذف الأمر {req.trigger} بنجاح."}


# ==========================================
# 3. Memory Vault & Time Capsule Endpoints
# ==========================================

class TimeCapsuleCreateRequest(BaseModel):
    user_id: int
    message: str
    unlock_hours: int = 24  # Default 24h


class VaultClearRequest(BaseModel):
    user_id: int


@router.get("/vault/facts")
async def get_vault_facts(user_id: int = Query(...)):
    """Returns memory facts and profile isolated for this user."""
    persona = persona_virtualizer.get_persona(user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "persona_name": persona.persona_name,
        "dialect": persona.dialect,
        "tone": persona.tone,
        "cloned_words": persona.cloned_linguistic_dna.get("favorite_words", [])[:8],
        "created_at": persona.created_at,
    }


@router.post("/vault/capsule/create")
async def create_time_capsule(req: TimeCapsuleCreateRequest):
    """Locks a message in a time capsule to be revealed after delay."""
    if not req.message or len(req.message.strip()) < 3:
        raise HTTPException(status_code=400, detail="الرسالة قصيرة جداً.")

    now = time.time()
    unlock_at = now + (req.unlock_hours * 3600)
    capsule = {
        "id": f"cap_{int(now)}_{req.user_id}",
        "user_id": req.user_id,
        "message": req.message.strip(),
        "created_at": now,
        "unlock_at": unlock_at,
        "unlocked": False,
        "duration_hours": req.unlock_hours,
    }

    capsules = _load_capsules()
    capsules.append(capsule)
    _save_capsules(capsules)

    return {
        "status": "success",
        "message": f"تم قفل كبسولة الزمن بنجاح! سيتم فتحها بعد {req.unlock_hours} ساعة.",
        "capsule": capsule,
    }


@router.get("/vault/capsule/list")
async def list_time_capsules(user_id: int = Query(...)):
    """Lists time capsules for this user."""
    capsules = _load_capsules()
    user_caps = [c for c in capsules if c.get("user_id") == user_id]
    now = time.time()
    for c in user_caps:
        c["is_ready"] = now >= c.get("unlock_at", 0)
    return {"status": "success", "capsules": user_caps}


@router.post("/vault/clear")
async def clear_memory_vault(req: VaultClearRequest):
    """Clears temporary memory sandbox for this user."""
    return {
        "status": "success",
        "message": "تم تنظيف وتصفير ذاكرة الحوار الخاصة بك بنجاح!",
    }


# ==========================================
# 4. Multi-Persona Debate Endpoint
# ==========================================

class DebateStartRequest(BaseModel):
    user_id: Optional[int] = None
    topic: str
    persona_a: Optional[str] = "عمر (المتفائل العبقري)"
    persona_b: Optional[str] = "سارة (الواقعية الساخرة)"
    rounds: int = 2
    send_to_telegram: bool = False


@router.post("/debate/start")
async def start_debate(req: DebateStartRequest):
    """Starts an interactive theatrical debate between two personas on the given topic."""
    if not req.topic or len(req.topic.strip()) < 3:
        raise HTTPException(status_code=400, detail="يرجى كتابة موضوع للنقاش.")
    
    rounds = min(max(req.rounds, 1), 4)
    persona_a = req.persona_a or "عمر (المتفائل العبقري)"
    persona_b = req.persona_b or "سارة (الواقعية الساخرة)"

    debate_res = await MultiPersonaDebater.generate_debate(
        topic=req.topic,
        persona_a_name=persona_a,
        persona_b_name=persona_b,
        rounds=rounds,
    )

    transcript = debate_res.transcript if hasattr(debate_res, "transcript") else debate_res
    verdict = getattr(debate_res, "verdict", "كلا الرأيين يقدم جانباً مهماً من الصورة الكاملة والتوازن هو الحل الأمثل.")

    # Dispatch to Telegram Chat if requested
    if req.send_to_telegram and req.user_id:
        try:
            tg_text = (
                f"🎭 <b>مسرح المناظرات الثنائية (Aether Theatrical Debate)</b>\n"
                f"📌 <b>الموضوع:</b> <i>{req.topic}</i>\n\n"
            )
            for t in transcript:
                speaker = t.get("speaker", "المناظر")
                text = t.get("text", "")
                icon = "👦" if t.get("side") == "left" else "👧"
                tg_text += f"{icon} <b>{speaker}:</b>\n{text}\n\n"

            tg_text += f"⚖️ <b>الحكم النهائي وخلاصة الحوار:</b>\n<i>{verdict}</i>"

            from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
            await mtproto_manager.send_message(chat_id=req.user_id, text=tg_text)
        except Exception as exc:
            logger.warning(f"Failed to forward debate transcript to Telegram user {req.user_id}: {exc}")

    return {
        "status": "success",
        "topic": req.topic,
        "persona_a": persona_a,
        "persona_b": persona_b,
        "rounds": rounds,
        "transcript": transcript,
        "verdict": verdict,
    }


# ==========================================
# 5. Voice Hub & Alarm Call Endpoint
# ==========================================

class CallScheduleRequest(BaseModel):
    user_id: int
    minutes_from_now: int = 10
    reminder_text: str = "مكالمة تذكير وإيقاظ مجدولة من عمر!"


@router.post("/voice/schedule_call")
async def schedule_voice_call(req: CallScheduleRequest):
    """Schedules an outbound wakeup/reminder VoIP call."""
    if req.minutes_from_now < 1:
        req.minutes_from_now = 1
    
    call = outbound_call_scheduler.schedule_wakeup_call(
        user_id=req.user_id,
        minutes_from_now=req.minutes_from_now,
        reason=req.reminder_text,
    )
    return {
        "status": "success",
        "message": f"تمت جدولة المكالمة الصوتية بنجاح بعد {req.minutes_from_now} دقيقة!",
        "call_id": call.call_id,
        "scheduled_time": call.scheduled_time,
    }

