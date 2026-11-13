"""
OSINT Search & Intelligence Filter Engine (Project Aether-Human - Admin Omni-Observatory)
Provides deep OSINT dossier generation (/u_search), group archive regex searching (/g_search),
and alias/username change telemetry.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.database.neo4j_graph.social_graph import social_graph
from admin_telemetry_and_archiver.passive_omni_archiver import omni_archiver

logger = logging.getLogger("Aether.Observatory.OSINT")


class OSINTSearchEngine:
    """
    Intelligence dossier builder and cross-group forensic search engine.
    """

    def __init__(self, history_file: str = "data/user_alias_history.json"):
        self.history_file = history_file
        self._alias_db: Dict[str, Dict[str, Any]] = {}
        self._ensure_storage()
        self._load()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> None:
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                self._alias_db = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load alias history: {e}")

    def _save(self) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._alias_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alias history: {e}")

    def track_user_identity(
        self,
        user_id: int,
        first_name: str,
        username: Optional[str] = None,
    ) -> None:
        """
        Records username and display name changes.
        """
        uid_str = str(user_id)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        if uid_str not in self._alias_db:
            self._alias_db[uid_str] = {
                "user_id": user_id,
                "current_name": first_name,
                "current_username": username or "",
                "name_history": [{"name": first_name, "date": now_str}],
                "username_history": [{"username": username or "", "date": now_str}],
                "last_seen": now_str,
            }
            self._save()
            return

        rec = self._alias_db[uid_str]
        rec["last_seen"] = now_str

        # Check name change
        if rec.get("current_name") != first_name:
            rec["name_history"].append({"name": first_name, "date": now_str})
            rec["current_name"] = first_name
            self._save()
            logger.info(f"👤 Name change detected for [{user_id}]: -> '{first_name}'")

        # Check username change
        clean_user = username or ""
        if rec.get("current_username") != clean_user:
            rec["username_history"].append({"username": clean_user, "date": now_str})
            rec["current_username"] = clean_user
            self._save()
            logger.info(f"👤 Username change detected for [{user_id}]: -> '@{clean_user}'")

    async def generate_user_dossier(self, target_identifier: str) -> str:
        """
        Builds a comprehensive OSINT dossier for a given user ID or @username.
        """
        target_uid: Optional[int] = None
        target_username = target_identifier.replace("@", "").strip().lower()

        if target_identifier.isdigit():
            target_uid = int(target_identifier)
        else:
            # Look up by username
            for uid_s, info in self._alias_db.items():
                if info.get("current_username", "").lower() == target_username:
                    target_uid = int(uid_s)
                    break

        if not target_uid:
            return f"❌ لم يتم العثور على أي بيانات استخباراتية للمعرف: <code>{target_identifier}</code>"

        uid_str = str(target_uid)
        alias_info = self._alias_db.get(uid_str, {})

        # Fetch SQL Database records
        async with db_manager.session() as session:
            repo = UserRepository(session)
            db_user = await repo.get_by_telegram_id(target_uid)

        # Fetch recent messages from archiver
        recent_messages = omni_archiver.search_user_archive(target_uid, limit=10)

        # Format Dossier
        curr_name = alias_info.get("current_name", "غير مسجل")
        curr_u = alias_info.get("current_username", "بدون يوزر")
        first_seen = alias_info.get("name_history", [{}])[0].get("date", "غير معروف")
        last_seen = alias_info.get("last_seen", "الآن")

        names_list = ", ".join(f"'{h['name']}' ({h['date'][:10]})" for h in alias_info.get("name_history", []))
        usernames_list = ", ".join(f"@{h['username']}" for h in alias_info.get("username_history", []) if h.get("username"))

        affinity = db_user.affinity_score if db_user else 50.0
        trust = db_user.trust_score if db_user else 50.0
        tier = db_user.relationship_tier if db_user else "STRANGER"

        dossier = (
            f"🕵️ <b>الملف الاستخباراتي الشامل (OSINT DOSSIER)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>الاسم الحالي:</b> {html.escape(curr_name)}\n"
            f"🆔 <b>User ID:</b> <code>{target_uid}</code>\n"
            f"🔗 <b>اليوزر:</b> @{curr_u}\n\n"
            f"📅 <b>أول ظهور:</b> {first_seen}\n"
            f"⏱️ <b>آخر نشاط:</b> {last_seen}\n\n"
            f"📜 <b>سجل تغيير الأسماء:</b>\n{html.escape(names_list or 'لا يوجد')}\n\n"
            f"🏷️ <b>سجل اليوزرات السابقة:</b>\n{html.escape(usernames_list or 'لا يوجد')}\n\n"
            f"🧠 <b>التقييم النفسي والولاء:</b>\n"
            f"• الرتبة النفسية: <code>{tier}</code>\n"
            f"• رصيد المعزة: <code>{affinity:.1f}/100</code>\n"
            f"• درجة الثقة: <code>{trust:.1f}/100</code>\n\n"
            f"💬 <b>آخر رسائل مسجلة ({len(recent_messages)}):</b>\n"
        )

        for m in recent_messages[:5]:
            dossier += f"• [{m.get('chat_title', 'خاص')}]: {html.escape(m.get('message_text', '')[:40])}...\n"

        return dossier


osint_engine = OSINTSearchEngine()

