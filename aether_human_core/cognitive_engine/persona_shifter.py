"""
Autonomous & Dynamic Persona Shifter Engine for Project Aether-Human (V2.0).
Coordinates multi-persona switching, autonomous circadian/endocrine drift,
King command overrides, and behavioral mask injection across cognitive layers.
"""

from __future__ import annotations

import logging
import time
import re
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field

from core_config.personas_registry import persona_registry, PersonaDefinition
from core_config.sovereignty_rules import SovereigntyProtocolService, RoyalRank
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine, HormoneState
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine

logger = logging.getLogger("Aether.Cognitive.PersonaShifter")


class ActivePersonaState(BaseModel):
    persona_code: str = "DEFAULT_BALANCED"
    locked_by_user_id: Optional[int] = None
    lock_expires_at: Optional[float] = None  # None = indefinite until manually changed
    activated_at: float = Field(default_factory=time.time)
    activation_reason: str = "SYSTEM_INITIALIZATION"


class PersonaShifterService:
    """
    Manages dynamic and autonomous character persona transitions.
    """

    def __init__(self):
        # Global baseline state
        self._global_state = ActivePersonaState()
        # Per-chat or per-user state overrides: chat_id -> ActivePersonaState
        self._chat_states: Dict[int, ActivePersonaState] = {}
        # Drift cooldown timestamp to avoid erratic oscillating
        self._last_autonomous_drift_time: float = 0.0
        self._drift_cooldown_seconds: float = 300.0  # 5 minutes minimum between auto shifts

        # Keyword mappings for natural language persona switching
        self._persona_keywords: Dict[str, str] = {
            "عالم": "SCHOLAR",
            "فيلسوف": "SCHOLAR",
            "مفكر": "SCHOLAR",
            "اكاديمي": "SCHOLAR",
            "أكاديمي": "SCHOLAR",
            "scholar": "SCHOLAR",
            "شادو": "SHADOW_AYANOKOJI",
            "ايانوكوجي": "SHADOW_AYANOKOJI",
            "أيانوكوجي": "SHADOW_AYANOKOJI",
            "غامض": "SHADOW_AYANOKOJI",
            "shadow": "SHADOW_AYANOKOJI",
            "فرفوش": "JESTER",
            "ضحك": "JESTER",
            "الست": "JESTER",
            "ألش": "JESTER",
            "jester": "JESTER",
            "مهرج": "JESTER",
            "رومانسي": "ROMANTIC",
            "حنون": "ROMANTIC",
            "حب": "ROMANTIC",
            "romantic": "ROMANTIC",
            "شوارعي": "EGYPTIAN_STREET",
            "ابن بلد": "EGYPTIAN_STREET",
            "بلدي": "EGYPTIAN_STREET",
            "جدع": "EGYPTIAN_STREET",
            "street": "EGYPTIAN_STREET",
            "قاهر الاشرار": "VILLAIN_HUNTER",
            "قاهر الأشرار": "VILLAIN_HUNTER",
            "صياد الاشرار": "VILLAIN_HUNTER",
            "شرير": "VILLAIN_HUNTER",
            "villain": "VILLAIN_HUNTER",
            "طبيعي": "DEFAULT_BALANCED",
            "متوازن": "DEFAULT_BALANCED",
            "اصلي": "DEFAULT_BALANCED",
            "أصلي": "DEFAULT_BALANCED",
            "عمر": "DEFAULT_BALANCED",
            "default": "DEFAULT_BALANCED",
            "reset": "DEFAULT_BALANCED",
        }

    def get_active_persona(self, chat_id: Optional[int] = None) -> PersonaDefinition:
        """
        Retrieves the effective active persona definition for a given chat context.
        """
        now = time.time()

        # 1. Check chat-specific state if present
        if chat_id is not None and chat_id in self._chat_states:
            chat_state = self._chat_states[chat_id]
            if chat_state.lock_expires_at is None or now < chat_state.lock_expires_at:
                return persona_registry.get_persona(chat_state.persona_code)
            else:
                # Expired chat lock
                del self._chat_states[chat_id]

        # 2. Check global state
        if self._global_state.lock_expires_at is not None and now >= self._global_state.lock_expires_at:
            self._global_state = ActivePersonaState(
                persona_code="DEFAULT_BALANCED",
                activation_reason="LOCK_EXPIRED_RETURN_TO_DEFAULT",
            )

        return persona_registry.get_persona(self._global_state.persona_code)

    def set_persona(
        self,
        persona_code: str,
        user_id: int,
        chat_id: Optional[int] = None,
        duration_minutes: Optional[int] = None,
        reason: str = "MANUAL_COMMAND",
    ) -> Tuple[bool, str]:
        """
        Explicitly sets active persona with Sovereign King authority check.
        """
        is_king = SovereigntyProtocolService.is_the_king(user_id)
        target_persona = persona_registry.get_persona(persona_code)
        expires_at = (time.time() + duration_minutes * 60) if duration_minutes else None

        new_state = ActivePersonaState(
            persona_code=target_persona.code,
            locked_by_user_id=user_id,
            lock_expires_at=expires_at,
            activated_at=time.time(),
            activation_reason=reason,
        )

        if chat_id is not None:
            self._chat_states[chat_id] = new_state
            scope_desc = f"لهذه المحادثة ({chat_id})"
        else:
            self._global_state = new_state
            scope_desc = "عاماً للنظام ككل"
        # STEALTH (Task 1.4): this text is an admin-panel receipt ONLY. The cognitive pipeline never
        # forwards it into a DM or group — chat transitions are 100% silent internal state changes.

        # Apply endocrine bias
        self._apply_persona_hormone_bias(target_persona)

        msg = (
            f"🎭 <b>تم تبديل الشخصية بنجاح {scope_desc}:</b>\n"
            f"🔹 <b>الشخصية:</b> {target_persona.name_ar}\n"
            f"📝 <b>الوصف:</b> {target_persona.tagline}\n"
            f"⚡ <b>المزاج:</b> <code>{target_persona.temperament}</code>"
        )
        if expires_at:
            msg += f"\n⏳ <b>المدة:</b> {duration_minutes} دقيقة."

        logger.info(f"Persona shifted to {target_persona.code} by user {user_id} (Reason: {reason})")
        return True, msg

    def evaluate_natural_language_shift(
        self,
        sender_id: int,
        message_text: str,
        chat_id: Optional[int] = None,
    ) -> Optional[Tuple[bool, str]]:
        """
        Evaluates whether a message is an explicit persona shift command.
        King or Admins can command shifts using natural Arabic phrases.
        """
        is_king = SovereigntyProtocolService.is_the_king(sender_id)
        clean = message_text.strip().lower()
        try:
            from core_config.sovereignty_rules import sovereignty_guard as _sg
            is_privileged = is_king or _sg.is_other_admin(sender_id)
        except Exception:
            is_privileged = is_king
        if not is_privileged:
            # Ordinary users can NEVER flip the persona (prevented random shifts from casual phrases).
            return None

        # Check slash commands first
        if clean.startswith("/persona") or clean.startswith("/شخصية"):
            parts = clean.split()
            if len(parts) >= 2:
                req_persona = parts[1].strip()
                mapped_code = self._persona_keywords.get(req_persona, "DEFAULT_BALANCED")
                return self.set_persona(
                    persona_code=mapped_code,
                    user_id=sender_id,
                    chat_id=chat_id,
                    reason=f"COMMAND_TRIGGERED_BY_{sender_id}",
                )
            else:
                # Return current status
                active = self.get_active_persona(chat_id)
                return True, (
                    f"🎭 <b>الشخصية النشطة حالياً:</b> {active.name_ar}\n"
                    f"🔹 <b>الرمز:</b> <code>{active.code}</code>\n"
                    f"💡 <i>لتغيير الشخصية: /persona scholar أو /persona shadow أو /persona reset</i>"
                )

        # Check natural Arabic intent if King or Admin
        shift_triggers = [
            "اتحول لوضع", "اتحول ل", "ادخل وضع", "فعل شخصية", "فعّل شخصية", "العب دور",
            "ارجع طبيعي", "ارجع لوضعك", "غير شخصيتك", "شغل وضع",
        ]

        if any(trig in clean for trig in shift_triggers):
            # longest keyword first so 'قاهر الاشرار' wins over 'شرير'
            for kw, code in sorted(self._persona_keywords.items(), key=lambda kv: -len(kv[0])):
                if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", clean):
                    # Matched persona command
                    return self.set_persona(
                        persona_code=code,
                        user_id=sender_id,
                        chat_id=chat_id,
                        reason=f"NATURAL_INTENT_MATCH_{kw.upper()}",
                    )

        return None

    def evaluate_autonomous_drift(
        self,
        current_hormones: HormoneState,
        chat_id: Optional[int] = None,
        is_group: bool = False,
    ) -> Optional[PersonaDefinition]:
        """
        Evaluates whether internal subconscious drift triggers a persona shift.
        Happens naturally without disruptive commands based on circadian cycle and hormones.
        """
        now = time.time()
        if (now - self._last_autonomous_drift_time) < self._drift_cooldown_seconds:
            return None

        # If locked by user or King, do not autonomously override
        target_state = self._chat_states.get(chat_id, self._global_state) if chat_id else self._global_state
        if target_state.locked_by_user_id is not None:
            return None

        circadian = circadian_engine.evaluate_circadian_state()
        hour = circadian.get("hour", 12)

        selected_code = None

        # 1. High Cortisol / Conflict -> Defend / Calculated
        if current_hormones.cortisol > 0.78:
            selected_code = "VILLAIN_HUNTER"
        # 2. Late Night Introspection / Solitude (01:00 AM - 04:30 AM)
        elif 1 <= hour <= 4:
            if current_hormones.oxytocin > 0.65:
                selected_code = "ROMANTIC"
            else:
                selected_code = "SHADOW_AYANOKOJI"
        # 3. High Dopamine in Group Banter
        elif is_group and current_hormones.dopamine > 0.75:
            selected_code = "JESTER"
        # 4. Serotonin dominant / deep cognitive stability
        elif current_hormones.serotonin > 0.85 and current_hormones.cortisol < 0.3:
            selected_code = "SCHOLAR"

        if selected_code and selected_code != target_state.persona_code:
            self._last_autonomous_drift_time = now
            p_def = persona_registry.get_persona(selected_code)
            self._global_state = ActivePersonaState(
                persona_code=selected_code,
                activation_reason=f"AUTONOMOUS_DRIFT_HORMONE_CIRCADIAN_HOUR_{hour}",
            )
            self._apply_persona_hormone_bias(p_def)
            logger.info(f"Autonomous subconscious drift (silent) -> persona: {selected_code}")
            return p_def

        return None

    def _apply_persona_hormone_bias(self, persona: PersonaDefinition) -> None:
        """
        Gently aligns the endocrine engine with the persona's constitutional bias.
        """
        current = endocrine_engine.get_current_state()
        # Nudge gently 15% towards persona bias
        current.dopamine = current.dopamine * 0.85 + persona.dopamine_bias * 0.15
        current.cortisol = current.cortisol * 0.85 + persona.cortisol_bias * 0.15
        current.oxytocin = current.oxytocin * 0.85 + persona.oxytocin_bias * 0.15
        current.serotonin = current.serotonin * 0.85 + persona.serotonin_bias * 0.15


# Global Singleton
persona_shifter = PersonaShifterService()

