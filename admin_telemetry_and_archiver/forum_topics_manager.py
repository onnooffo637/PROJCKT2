"""
Forum Topics Manager (Project Aether-Human - Admin Omni-Observatory)
Automatically creates, indexes, and manages the 7 dedicated telemetry forum topics
in the King's Admin Telemetry Supergroup (ADMIN_TELEMETRY_SUPERGROUP_ID).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional
import httpx

from aether_human_core.config.settings import settings

logger = logging.getLogger("Aether.Observatory.ForumManager")


class ForumTopicsManager:
    """
    Ensures the 7 forum topics exist in the telemetry supergroup and caches their thread IDs.
    """

    TOPIC_DEFINITIONS = {
        "DMS": {"name": "📩 الرسايل الخاصة - Direct DMs", "icon_color": 7322096},
        "GROUPS": {"name": "👥 رادار الجروبات والتحركات - Groups Feed", "icon_color": 16766590},
        "ANTI_DELETE": {"name": "🗑️ صائد المحذوفات والتعديلات - Ghost Catcher", "icon_color": 13338331},
        "VOIP": {"name": "📞 غرفة المكالمات والصوتيات - VoIP & Audio", "icon_color": 9367192},
        "COGNITIVE": {"name": "🧠 الذاكرة والمشاعر والقرارات - Cognitive Stream", "icon_color": 16749490},
        "GAMES": {"name": "🎮 صالة الألعاب والتطبيقات - Mini App & Games", "icon_color": 5707519},
        "SECURITY": {"name": "🚨 أمان السيرفر وراصد الأخطاء - Security & Alerts", "icon_color": 16724838},
    }

    def __init__(self, cache_file: str = "data/forum_topics_cache.json"):
        self.cache_file = cache_file
        self.topic_ids: Dict[str, int] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.topic_ids = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load forum topics cache: {e}")

    def _save_cache(self) -> None:
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.topic_ids, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save forum topics cache: {e}")

    def get_thread_id(self, topic_key: str) -> Optional[int]:
        return self.topic_ids.get(topic_key)

    async def initialize_topics(self) -> None:
        """
        Creates any missing forum topics via Telegram Bot API createForumTopic.
        """
        supergroup_id = settings.admin_telemetry_supergroup_id
        token = settings.telegram_bot_token

        if not supergroup_id or supergroup_id == 0 or not token:
            logger.info("Admin Telemetry Supergroup ID not configured in .env. Skipping forum topic creation.")
            return

        api_url = f"https://api.telegram.org/bot{token}/createForumTopic"

        async with httpx.AsyncClient(timeout=10.0) as client:
            for key, meta in self.TOPIC_DEFINITIONS.items():
                if key in self.topic_ids:
                    continue  # Already indexed

                try:
                    res = await client.post(
                        api_url,
                        json={
                            "chat_id": supergroup_id,
                            "name": meta["name"],
                            "icon_color": meta["icon_color"],
                        },
                    )
                    data = res.json()
                    if data.get("ok"):
                        thread_id = data["result"]["message_thread_id"]
                        self.topic_ids[key] = thread_id
                        logger.info(f"✨ Created Forum Topic [{meta['name']}] -> thread_id: {thread_id}")
                    else:
                        logger.warning(f"Could not create forum topic '{meta['name']}': {data.get('description')}")
                except Exception as exc:
                    logger.warning(f"Error creating forum topic '{meta['name']}': {exc}")

        self._save_cache()


forum_topics_manager = ForumTopicsManager()

