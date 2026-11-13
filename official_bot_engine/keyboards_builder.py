"""
Official Bot Engine - Modern Keyboards Builder with Strict RBAC UI Cloaking.
Project Aether-Human (V5.0 Architectural Specification).
"""

from __future__ import annotations

import html
import logging
from typing import Any, Dict, List, Optional, Tuple

from aether_human_core.config.settings import settings
from security_and_rbac.rbac_ui_guard import rbac_guard
from cloud_and_resource_guard.tunnel_manager import tunnel_manager

logger = logging.getLogger("Aether.BotEngine.Keyboards")


class KeyboardsBuilder:
    """
    Renders Telegram keyboards ensuring King-exclusive buttons are strictly cloaked from normal users.
    """

    @classmethod
    def build_main_dashboard_buttons(cls, user_id: int) -> List[List[Dict[str, Any]]]:
        is_king = rbac_guard.is_the_king(user_id)
        webapp_url = tunnel_manager.get_webapp_url()

        webapp_btn = (
            {"text": "🚀 فتح تطبيق Mini App 🎮", "web_app": {"url": webapp_url}, "style": "success"}
            if webapp_url.startswith("https://")
            else {"text": "🚀 تطبيق الويب المصغر (Mini App) 🎮", "callback_data": "menu:webapp", "style": "primary"}
        )

        buttons: List[List[Dict[str, Any]]] = [
            # 1. Emotional Affinity & Profile (All Users)
            [
                {"text": "💖 رصيد معزتي ومكانتي عند عمر 💎", "callback_data": "menu:user_affinity", "style": "success"},
            ],
            # 2. V3.0 Isolated Sandbox (All Users)
            [
                {"text": "🎭 استوديو شخصيتي الخاصة ⚡", "callback_data": "menu:my_persona", "style": "primary"},
                {"text": "🪄 أوامري الخاصة (الخاص) ⚡", "callback_data": "menu:my_commands", "style": "success"},
            ],
            # 3. Memory Vault & Debate Room (All Users)
            [
                {"text": "🧠 خزنة ذاكرتي وكبسولة الزمن ⏳", "callback_data": "menu:my_vault", "style": "primary"},
                {"text": "👥 غرفة النقاش المزدوج 🎭", "callback_data": "menu:debate", "style": "success"},
            ],
            # 4. Games & Audio/Call Hub (All Users)
            [
                {"text": "🎮 ألعاب وتحديات الجروب 🏆", "callback_data": "menu:games", "style": "primary"},
                {"text": "📞 إعدادات الصوت والمنبه 🎙️", "callback_data": "menu:voice_calls", "style": "success"},
            ],
            # 5. Dialects & Mood (All Users)
            [
                {"text": "🌐 لغات ولهجات البوت 🗺️", "callback_data": "menu:dialects", "style": "primary"},
                {"text": "🧠 رادار المزاج والهرمونات ☕", "callback_data": "menu:mood_radar", "style": "success"},
            ],
        ]

        # 6. KING EXCLUSIVE ROW: AetherGram Mod Client & Bot Factory (Cloaked from all normal users)
        if is_king:
            buttons.append([
                {"text": "🤖 مصنع البوتات واليوزربوت 🏭", "callback_data": "menu:bot_factory", "style": "success"},
                {"text": "📱 تليجرام المعدل والأرشيف 🌐", "callback_data": "menu:aethergram", "style": "primary"},
            ])
            buttons.append([
                {"text": "👑 إدارة الأدمنز والرتب 🛡️", "callback_data": "menu:admins", "style": "primary"},
                {"text": "📊 حالة السيرفر والنظام ⚡", "callback_data": "menu:server_stats", "style": "primary"},
            ])
            buttons.append([
                {"text": "📜 القواعد والممنوعات ⚖️", "callback_data": "menu:rules", "style": "danger"},
            ])

        # Bottom row: WebApp Button & Refresh (All Users)
        buttons.append([
            webapp_btn,
            {"text": "🔄 تحديث اللوحة الشاملة ⚡", "callback_data": "menu:main", "style": "primary"},
        ])

        # Extra safety enforcement
        return rbac_guard.filter_menu_buttons_for_user(user_id, buttons)

    @classmethod
    def build_vault_buttons(cls) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "⏳ إنشاء كبسولة زمن جديدة 💌", "callback_data": "act:capsule_create", "style": "success"}],
                [{"text": "📜 استعراض كبسولات الزمن المحفوظة 📦", "callback_data": "act:capsule_list", "style": "primary"}],
                [{"text": "🧹 مسح كل المعلومات المحفوظة عني ❌", "callback_data": "act:vault_clear", "style": "danger"}],
                [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "primary"}],
            ]
        }

    @classmethod
    def build_debate_buttons(cls) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "⚡ نقاش سريع: الذكاء الاصطناعي والإنسان", "callback_data": "act:debate_ai", "style": "primary"},
                ],
                [
                    {"text": "💡 نقاش فلسفي: السعادة والنجاح", "callback_data": "act:debate_philosophy", "style": "primary"},
                ],
                [
                    {"text": "⚽ نقاش كروي ساخن: ريال ومدريد والأهلي", "callback_data": "act:debate_sports", "style": "primary"},
                ],
                [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
            ]
        }

    @classmethod
    def build_voice_calls_buttons(cls) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "🎙️ تجربة تسجيل صوتي من عمر 🎶", "callback_data": "act:send_voice", "style": "success"}],
                [{"text": "⏰ طلب منبه بشري بمكالمة صوتية 📞", "callback_data": "act:alarm_request", "style": "primary"}],
                [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
            ]
        }


keyboards_builder = KeyboardsBuilder()

