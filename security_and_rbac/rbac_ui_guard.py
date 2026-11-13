"""
Role-Based Access Control (RBAC) & UI Cloaking Guard.
Project Aether-Human (V5.0 Architectural Specification).

Enforces strict dual-layer isolation:
1. Keyboard & Button Cloaking: Normal users NEVER see Bot Factory, Userbot Control, or Archive buttons.
2. WebApp API & View Shielding: Verifies Telegram WebApp initData/user_id, rejecting unauthorized calls with 403 Forbidden.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

from aether_human_core.config.settings import settings, CO_ADMIN_ID

logger = logging.getLogger("Aether.Security.RBAC")


class RbacUiGuard:
    """
    Central RBAC policy enforcer for bot keyboards and WebApp endpoints.
    """

    @classmethod
    def is_supreme_king(cls, user_id: int) -> bool:
        """
        Returns True strictly for the Supreme Sovereign Creator (KING_USER_ID).
        """
        uid = int(user_id or 0)
        return (settings.the_king_user_id > 0 and uid == settings.the_king_user_id) or uid == settings.king_id

    @classmethod
    def is_the_king(cls, user_id: int) -> bool:
        """
        Returns True if user is The Sovereign King or explicitly configured Super Admin (e.g. Marselin CO_ADMIN_ID).
        """
        king_id = settings.the_king_user_id
        uid = int(user_id or 0)
        return (
            uid == king_id
            or (settings.the_king_user_id > 0 and uid == settings.the_king_user_id)
            or uid == CO_ADMIN_ID
            or uid == settings.marcel_id
            or uid in settings.super_admin_ids_list
        )

    @classmethod
    def is_factory_admin(cls, user_id: int) -> bool:
        """
        Returns True if user has permission to access the Bot Factory (Supreme King, Marselin, Super Admins, or approved users).
        """
        if cls.is_the_king(user_id):
            return True
        try:
            from bot_factory.factory_manager import bot_factory
            return bot_factory.is_factory_admin(user_id)
        except Exception:
            return False

    @classmethod
    def verify_king_access(cls, user_id: int) -> None:
        """
        FastAPI dependency / route guard. Raises 403 Forbidden if not The King or Factory Admin.
        """
        if not cls.is_factory_admin(user_id):
            logger.warning(f"🚨 Security Alert: Unauthorized access attempt to Admin route by User [{user_id}].")
            raise HTTPException(
                status_code=403,
                detail="⛔ وصول مرفوض: هذه الميزة والواجهة محصورة حصرياً لمالك النظام والأدمنز المعتمدين."
            )

    @classmethod
    def verify_bot_ownership(cls, user_id: int, instance_id: str) -> None:
        """
        Enforces strict multi-admin bot isolation:
        - Supreme King (KING_USER_ID) can manage all bots.
        - Secondary Admin (Marselin CO_ADMIN_ID) can ONLY manage bots where `bot.owner_id == user_id`.
        """
        cls.verify_king_access(user_id)
        if cls.is_supreme_king(user_id):
            return
        from bot_factory.factory_manager import bot_factory
        if not bot_factory.can_user_manage_bot(user_id, instance_id):
            logger.warning(
                f"🚨 Isolation Guard: Admin [{user_id}] attempted to access bot [{instance_id}] owned by another admin."
            )
            raise HTTPException(
                status_code=403,
                detail="⛔ وصول مرفوض: يمكنك فقط عرض وتعديل البوتات الخاصة بك التي قمت بإنشائها."
            )

    @classmethod
    def filter_menu_buttons_for_user(
        cls, user_id: int, buttons: List[List[Dict[str, Any]]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Strips King-only buttons (Bot Factory, Userbot Control, Full Archive, Admin Panels)
        from inline keyboards when rendering for non-King users.
        """
        if cls.is_the_king(user_id):
            return buttons

        sanitized: List[List[Dict[str, Any]]] = []
        forbidden_keywords = (
            "bot_factory", "userbot", "aethergram", "archive", "admins",
            "مصنع البوتات", "اليوزربوت", "أرشيف", "الأدمنز", "قواعد"
        )

        for row in buttons:
            clean_row = []
            for btn in row:
                cb = btn.get("callback_data", "").lower()
                text = btn.get("text", "").lower()

                # If button references any King-exclusive capability, omit it completely
                if any(k in cb for k in ("bot_factory", "userbot", "aethergram", "admin", "archive")):
                    continue
                if any(w in text for w in ("مصنع البوتات", "اليوزربوت", "الأرشيف", "أدمنز")):
                    continue

                clean_row.append(btn)

            if clean_row:
                sanitized.append(clean_row)

        return sanitized

    @classmethod
    def filter_webapp_state_for_user(cls, user_id: int, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strips King-exclusive telemetry and factory instances from public API responses.
        """
        is_factory_adm = cls.is_factory_admin(user_id)
        is_supreme = cls.is_supreme_king(user_id)
        filtered = dict(state)
        filtered["is_king"] = is_factory_adm
        filtered["is_supreme_king"] = is_supreme
        filtered["role"] = "KING" if is_supreme else ("ADMIN" if is_factory_adm else "USER")

        if isinstance(filtered.get("user"), dict):
            filtered["user"]["is_king"] = is_factory_adm
            filtered["user"]["is_supreme_king"] = is_supreme

        if not is_factory_adm:
            filtered.pop("factory_instances", None)
            filtered.pop("available_bots", None)
            filtered.pop("active_userbots", None)
            filtered.pop("server_secret_tokens", None)
            filtered.pop("omni_archive_stats", None)

        return filtered


rbac_guard = RbacUiGuard()

