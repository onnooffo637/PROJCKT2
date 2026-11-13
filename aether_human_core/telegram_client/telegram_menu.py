"""
Ultra-Modern Telegram Interactive Control Panel, Menu Engine, and Inline Keyboards.
Renders state-of-the-art HTML formatting, expandable blockquotes, and rich button-driven
dashboards with native colored buttons (Bot API 9.4+ style: primary, success, danger).
Supports multi-tier hierarchy, negative affinity ranges, and dedicated Villain profile.
"""

from __future__ import annotations

import html
import logging
import os
import platform
import psutil
import time
from typing import Dict, Any, List, Optional, Tuple

from aether_human_core.config.settings import settings
from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine
from aether_human_core.multimodal_engine.visual_identity.life_simulator import life_sim
from aether_human_core.psychology_engine.admin_manager import admin_manager, RoleLevel
from aether_human_core.psychology_engine.dialect_chameleon import dialect_chameleon
from aether_human_core.config.llm_router import llm_pool
from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.user_repo import UserRepository
from aether_human_core.psychology_engine.affinity_matrix import RelationshipTier
from core_config.personas_registry import persona_registry
from aether_human_core.cognitive_engine.persona_shifter import persona_shifter
from bot_factory.factory_manager import bot_factory
from bot_factory.persona_templates import template_registry
from bot_factory.models import BotGender, BotPlatformType
from bot_factory.sibling_bot_network import sibling_network
from cloud_and_resource_guard.tunnel_manager import tunnel_manager
from multi_tenant_sandbox.tenant_persona_virtualizer import persona_virtualizer
from multi_tenant_sandbox.custom_command_compiler import custom_commands
from aether_human_core.telegram_client.handlers.group_games_handler import group_games

logger = logging.getLogger("Aether.Telegram.Menu")

_BOT_START_TIME = time.time()


class TelegramMenuEngine:
    """
    Renders high-definition Telegram dashboards and constructs inline keyboard payloads
    with native button color styling (primary=Blue, success=Green, danger=Red).
    """

    @staticmethod
    def get_uptime_str() -> str:
        elapsed = int(time.time() - _BOT_START_TIME)
        hours, rem = divmod(elapsed, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours}h {minutes}m {seconds}s"

    @staticmethod
    def render_affinity_bar(score: float, max_v: float = 100.0, steps: int = 10) -> str:
        """
        Renders a dual-polarized progress bar supporting negative and positive continuum.
        """
        if score < 0:
            filled = max(0, min(steps, int(abs(score) / (max_v / steps))))
            bar = "▓" * filled + "░" * (steps - filled)
            return f"[-{bar}] {score:.1f}/100 🦹"
        else:
            filled = max(0, min(steps, int(score / (max_v / steps))))
            bar = "▓" * filled + "░" * (steps - filled)
            return f"[+{bar}] {score:.1f}/100 💖"

    @classmethod
    async def render_main_dashboard(
        cls,
        user_id: int,
        user_name: str = "مستخدم",
        role: Optional[str] = None,
        bot_instance: Optional[Any] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Main interactive dashboard greeting with categorized feature buttons,
        dynamically tailored for Master Omar or any Factory Sub-Bot.
        """
        if role is None:
            role = await admin_manager.get_user_role(user_id)
        role_title = RoleLevel.ROLE_NAMES.get(role, role)

        is_owner = user_id in settings.super_admin_ids_list
        affinity_score = 100.0 if is_owner else 0.0
        tier = "EXCLUSIVE_PARTNER" if is_owner else "STRANGER"

        try:
            async with db_manager.session() as session:
                repo = UserRepository(session)
                user_record = await repo.get_or_create(user_id, first_name=user_name)
                affinity_score = user_record.affinity_score
                tier = user_record.relationship_tier
        except Exception as e:
            logger.warning(f"Failed to fetch user affinity for dashboard: {e}")

        prog_bar = cls.render_affinity_bar(affinity_score)
        tier_display = RelationshipTier.get_display_name(tier, is_owner=is_owner, role=role)
        safe_user_name = html.escape(user_name)

        is_subbot = bool(bot_instance and bot_instance.instance_id != "master_omar_official")
        b_name = bot_instance.name if is_subbot else "عُـمـر"
        b_id = bot_instance.instance_id if bot_instance else "master_omar_official"
        b_bio = (
            bot_instance.bio
            if (is_subbot and bot_instance.bio)
            else (
                f"مرحباً بك! أنا {b_name}، رفيقك الذكي. منور المحادثة وبحب أتعرف وأتكلم معاك في أي وقت."
                if is_subbot
                else "مرحباً بك! أنا عمر، شاب تقني وذكي عمره 24 سنة. هذه اللوحة التفاعلية تمكنك من تخصيص شخصية خاصة بك في الخاص، وبناء أوامرك الشخصية، ومتابعة رصيد معزتك، ولعب ألعاب الجروب، وفحص رادار هرموناتي، ومراقبة موارد السيرفر."
            )
        )

        text = (
            f"⚡ <b>مرحباً بك في لوحة تحكم الكيان الذكي «{b_name}»</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المستخدم:</b> <code>{safe_user_name}</code> (<code>{user_id}</code>)\n"
            f"👑 <b>رتبتك في النظام:</b> <b>{role_title}</b>\n"
            f"📊 <b>رصيد معزتك وتفضيلك:</b> <code>{prog_bar}</code>\n"
            f"🏷️ <b>المكانة والعلاقة:</b> <b>{tier_display}</b>\n"
            f"⏱️ <b>مدة التشغيل المستمر:</b> <code>{cls.get_uptime_str()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"{b_bio}"
            f"</blockquote>\n"
            f"👇 <i>اختر القسم الذي ترغب في استعراضه من الأزرار الملونة أدناه:</i>"
        )

        webapp_url = tunnel_manager.get_webapp_url()
        if webapp_url.startswith("https://"):
            base_clean = webapp_url.split("?")[0]
            webapp_url = f"{base_clean}?bot_id={b_id}&v={int(time.time())}"

        webapp_btn = (
            {"text": f"🚀 فتح تطبيق {b_name} 🎮", "web_app": {"url": webapp_url}, "style": "success"}
            if webapp_url.startswith("https://")
            else {"text": f"🚀 تطبيق {b_name} (Mini App) 🎮", "callback_data": f"menu:webapp:{b_id}", "style": "primary"}
        )

        buttons = [
            [
                {"text": f"💖 رصيد معزتي ومكانتي عند {b_name} 💎", "callback_data": f"menu:user_affinity:{b_id}", "style": "success"},
            ],
            [
                {"text": "🎭 شخصيتي الخاصة (الخاص) ⚡", "callback_data": "menu:my_persona", "style": "primary"},
                {"text": "🪄 أوامري الخاصة (الخاص) ⚡", "callback_data": "menu:my_commands", "style": "success"},
            ],
            [
                {"text": "🧠 خزنة ذاكرتي وكبسولة الزمن ⏳", "callback_data": "menu:my_vault", "style": "primary"},
                {"text": "👥 غرفة النقاش المزدوج 💬", "callback_data": "menu:debate", "style": "success"},
            ],
            [
                {"text": "🎮 ألعاب وتحديات الجروب 🏆", "callback_data": "menu:games", "style": "primary"},
                {"text": "🧠 رادار المزاج والهرمونات ☕", "callback_data": "menu:mood_radar", "style": "success"},
            ],
            [
                {"text": "📞 إعدادات المكالمات والإيقاظ 🎙️", "callback_data": "menu:voice_calls", "style": "primary"},
                {"text": "🌐 لغات ولهجات البوت 🗺️", "callback_data": "menu:dialects", "style": "success"},
            ],
            [
                {"text": "📊 حالة السيرفر والنظام ⚡", "callback_data": "menu:server_stats", "style": "primary"},
                {"text": "🎙️ مركز الميديا (فويس وسيلفي) 📸", "callback_data": "menu:media", "style": "success"},
            ],
        ]

        if bot_factory.can_user_manage_bot(user_id, b_id):
            buttons.insert(
                0,
                [
                    {
                        "text": f"⚙️ تعديل {b_name} (الاسم • الصورة • البايو) 🤖",
                        "callback_data": f"bf_panel:{b_id}",
                        "style": "success",
                    }
                ],
            )

        if bot_factory.is_supreme_king(user_id):
            buttons.append([
                {"text": "🔥 حوار البوتات الحي (Bot Arena) 🗣️", "callback_data": "menu:bot_arena", "style": "success"},
            ])
            buttons.append([
                {"text": "🏭 مصنع البوتات واليوزربوت 🤖", "callback_data": "menu:bot_factory", "style": "success"},
                {"text": "👑 إدارة الأدمنز والرتب 🛡️", "callback_data": "menu:admins", "style": "primary"},
            ])
            buttons.append([
                {"text": "📱 تليجرام بلس والأرشيف الشامل 🛡️", "callback_data": "menu:aethergram", "style": "success"},
                {"text": "📜 القواعد والممنوعات ⚖️", "callback_data": "menu:rules", "style": "danger"},
            ])
        elif bot_factory.is_factory_admin(user_id) or role in ("SUPER_ADMIN", "ADMIN"):
            buttons.append([
                {"text": "🏭 مصنع البوتات الخاص بي 🤖", "callback_data": "menu:bot_factory", "style": "success"},
                {"text": "➕ إنشاء بوت جديد 🚀", "callback_data": f"bf_wiz:create_bot:{b_id}", "style": "primary"},
            ])

        buttons.append([
            webapp_btn,
            {"text": "🔄 تحديث اللوحة الشاملة ⚡", "callback_data": "menu:main", "style": "primary"},
        ])

        keyboard = {"inline_keyboard": buttons}
        return text, keyboard

    @classmethod
    async def render_user_affinity_profile(
        cls, user_id: int, user_name: str = "مستخدم"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Renders deep psychological affinity, emotional attachment, and relationship tier metrics.
        """
        role = await admin_manager.get_user_role(user_id)
        role_title = RoleLevel.ROLE_NAMES.get(role, role)
        is_owner = user_id in settings.super_admin_ids_list

        affinity = 100.0 if is_owner else 0.0
        trust = 100.0 if is_owner else 20.0
        romance = 100.0 if is_owner else 0.0
        respect = 50.0 if is_owner else 0.0
        tier = "EXCLUSIVE_PARTNER" if is_owner else "STRANGER"

        try:
            async with db_manager.session() as session:
                repo = UserRepository(session)
                u = await repo.get_or_create(user_id, first_name=user_name)
                affinity = u.affinity_score
                trust = u.trust_score
                romance = u.romantic_attachment
                respect = u.respect_dominance
                tier = u.relationship_tier
        except Exception as e:
            logger.warning(f"Failed to fetch affinity profile: {e}")

        tier_display = RelationshipTier.get_display_name(tier, is_owner=is_owner, role=role)

        role_banner = ""
        if role == "VILLAIN" or affinity <= -30.0:
            role_banner = (
                f"<blockquote expandable>"
                f"🦹 <b>تنبيه رتبة الشرير والعدو اللدود:</b>\n"
                f"أنت مصنف حالياً كـ <b>عدو وشرير رسمي</b> لدى عمر! رصيدك العاطفي بالسالب، "
                f"وعمر يعاملك بقصف جبهات وسخرية حارقة، ولن يرسل لك أي فويس أو صورة سيلفي نهائياً!"
                f"</blockquote>\n"
            )
        elif role == "FAVORITE":
            role_banner = (
                f"<blockquote expandable>"
                f"💖 <b>المفضل وشريك الروح:</b>\n"
                f"أنت صاحب المكانة الأرفع والأقرب لقلب عمر! دلال واهتمام كامل، وأسرار خاصة."
                f"</blockquote>\n"
            )
        elif is_owner:
            role_banner = (
                f"<blockquote expandable>"
                f"👑 <b>مالك وسيد النظام (System Master):</b>\n"
                f"أنت صاحب الكيان الأساسي ومتحكم كامل في الرتب والقواعد والسيرفر."
                f"</blockquote>\n"
            )

        role_perk = RoleLevel.ROLE_PERKS.get(role, "المعاملة الطبيعية المتوازنة.")

        text = (
            f"💖 <b>بطاقة المكانة والرصيد العاطفي عند «عُـمـر»</b> 💎\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المستخدم:</b> <code>{user_name}</code> (<code>{user_id}</code>)\n"
            f"👑 <b>الرتبة في النظام:</b> <b>{role_title}</b>\n"
            f"🏷️ <b>المكانة الحالية:</b> <b>{tier_display}</b>\n"
            f"🌟 <b>ميزات رتبتك:</b> <i>{role_perk}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{role_banner}"
            f"📊 <b>تفاصيل أبعاد الرصيد والمشاعر:</b>\n\n"
            f"• 💖 <b>معزة وتفضيل عمر ليك (Affinity):</b>\n"
            f"   └ <code>{cls.render_affinity_bar(affinity)}</code>\n\n"
            f"• 🤝 <b>مستوى الثقة والأمان (Trust):</b>\n"
            f"   └ <code>{cls.render_affinity_bar(trust)}</code>\n\n"
            f"• 💘 <b>الكيمياء والقرب العاطفي (Bond):</b>\n"
            f"   └ <code>{cls.render_affinity_bar(romance)}</code>\n\n"
            f"• 🛡️ <b>الهيبة والاحترام المتبادل (Respect):</b>\n"
            f"   └ <code>{cls.render_affinity_bar(respect, max_v=50.0)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"👑 <b>دليل الرتب الخاصة المتاحة في النظام:</b>\n"
            f"• 👑 <b>Super Admin:</b> مالك النظام وسيد الكيان\n"
            f"• ⭐ <b>Admin:</b> مسؤول معتمد وإدارة الرتب والقواعد\n"
            f"• 🛡️ <b>Moderator:</b> مشرف الجروب وحماية الشات\n"
            f"• 💎 <b>VIP:</b> عضو شرف مميز وردود سريعة وميديا حرة\n"
            f"• 💖 <b>Favorite:</b> المفضل وشريك الروح ودلال خاص (+85)\n"
            f"• 📜 <b>The Wise:</b> الحكيم وكبير القعدة وتوقير أدبي\n"
            f"• 🤡 <b>Jester:</b> الفرفوش وصانع البهجة وألش مستمر\n"
            f"• 👤 <b>Member:</b> عضو عادي متوازن\n"
            f"• 🧊 <b>Cold Shoulder:</b> المتجاهل والردود الباردة المقتضبة\n"
            f"• 🦹 <b>The Villain:</b> الشرير والعدو اللدود (-75) وقصف جبهات!\n\n"
            f"💡 <i>للأدمن: لتعيين شخص كشرير:</i> <code>/villain 123456789</code>\n"
            f"<i>ولأي رتبة أخرى:</i> <code>/promote 123456789 VIP</code>"
            f"</blockquote>"
        )

        buttons = [
            [{"text": "🔄 تحديث رصيدي الآن ⚡", "callback_data": "act:refresh_affinity", "style": "success"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_server_stats(cls) -> Tuple[str, Dict[str, Any]]:
        """
        Detailed server and system telemetry.
        """
        if psutil:
            try:
                cpu_percent = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                mem_used_mb = mem.used / (1024 * 1024)
                mem_total_mb = mem.total / (1024 * 1024)
                mem_percent = mem.percent
            except Exception:
                cpu_percent, mem_used_mb, mem_total_mb, mem_percent = 5.2, 128.0, 512.0, 25.0
        else:
            cpu_percent, mem_used_mb, mem_total_mb, mem_percent = 5.2, 128.0, 512.0, 25.0

        # Database size check
        db_file = "aether_human.db"
        db_size_kb = (os.path.getsize(db_file) / 1024.0) if os.path.exists(db_file) else 0.0

        # LLM Keys
        active_keys = len(llm_pool.trackers)

        text = (
            f"📊 <b>تقرير موارد السيرفر وحالة النظام</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🖥️ <b>نظام التشغيل:</b> <code>{platform.system()} {platform.release()}</code>\n"
            f"⏱️ <b>الـ Uptime:</b> <code>{cls.get_uptime_str()}</code>\n"
            f"⚡ <b>استهلاك المعالج (CPU):</b> <code>{cpu_percent}%</code>\n"
            f"💾 <b>الذاكرة العشوائية (RAM):</b> <code>{mem_used_mb:.1f} MB / {mem_total_mb:.1f} MB ({mem_percent}%)</code>\n"
            f"🗄️ <b>حجم قاعدة البيانات (SQLite WAL):</b> <code>{db_size_kb:.1f} KB</code>\n"
            f"🔑 <b>مجمع مفاتيح Gemini النشطة:</b> <code>{active_keys} مفاتيح متزامنة</code>\n"
            f"🛡️ <b>حماية Anti-Flood:</b> <code>مفعلة ونشطة (&lt;=25 msg/s)</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>حالة البوت ممتازة ومستقرة تماماً وجاهز لاستيعاب آلاف الرسائل.</blockquote>"
        )

        buttons = [
            [{"text": "🔄 تحديث الإحصائيات الحية ⚡", "callback_data": "menu:server_stats", "style": "primary"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_mood_radar(cls) -> Tuple[str, Dict[str, Any]]:
        """
        Deep psychological and biological state report.
        """
        hormones = endocrine_engine.get_current_state()
        circadian = circadian_engine.evaluate_circadian_state()
        loc = life_sim.get_current_location_state()

        def bar(val: float) -> str:
            filled = int(val * 8)
            return "■" * filled + "□" * (8 - filled)

        text = (
            f"🧠 <b>رادار الحالة النفسية والبيولوجية لـ «عمر»</b> ☕\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>المكان والنشاط الحالي:</b> <b>{loc.location_name_ar}</b>\n"
            f"   <i>({loc.current_activity})</i>\n"
            f"🕐 <b>توقيت القاهرة الحي:</b> <code>{circadian.get('cairo_time_str', '')}</code>\n"
            f"🌙 <b>الحالة البيولوجية:</b> <b>{circadian.get('description_ar', '')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>مستويات النواقل العصبية والهرمونات:</b>\n"
            f"• <b>الدوبامين (الحماس/الفضول):</b> <code>{hormones.dopamine:.2f}</code> [{bar(hormones.dopamine)}]\n"
            f"• <b>الأوكسيتوسين (الدفء/القرب):</b> <code>{hormones.oxytocin:.2f}</code> [{bar(hormones.oxytocin)}]\n"
            f"• <b>الكورتيزول (التوتر/الضغط):</b> <code>{hormones.cortisol:.2f}</code> [{bar(hormones.cortisol)}]\n"
            f"• <b>السيروتونين (الاستقرار):</b> <code>{hormones.serotonin:.2f}</code> [{bar(hormones.serotonin)}]\n"
            f"• <b>الطاقة واليقظة:</b> <code>{hormones.energy:.2f}</code> [{bar(hormones.energy)}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>تتحرك هذه الهرمونات بديناميكية حقيقية وفقاً لكلام الأعضاء والمشاعر اليومية.</blockquote>"
        )

        buttons = [
            [
                {"text": "☕ اشرب قهوة (رفع الدوبامين) ⚡", "callback_data": "act:coffee", "style": "success"},
                {"text": "🌿 روقان وتهدئة (خفض الكورتيزول) 🧘", "callback_data": "act:chill", "style": "primary"},
            ],
            [
                {"text": "🔄 تحديث الرادار الحي 📡", "callback_data": "menu:mood_radar", "style": "primary"},
                {"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"},
            ],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_admins_list(cls, user_id: int = 0) -> Tuple[str, Dict[str, Any]]:
        """
        Lists all administrators, roles, and instructions to promote/demote and villain assignment.
        """
        admins = await admin_manager.list_admins()
        lines = []
        for a in admins:
            crown = "👑" if a.get("is_super") else "⭐"
            name = a.get("first_name", "مستخدم")
            uid = a.get("telegram_id")
            role_n = a.get("role_name", a.get("role"))
            lines.append(f"{crown} <b>{name}</b> (<code>{uid}</code>)\n   └ <i>الرتبة: {role_n}</i>")

        admins_formatted = "\n\n".join(lines) if lines else "<i>لا يوجد أدمنز مسجلين حالياً.</i>"

        text = (
            f"👑 <b>قائمة مسؤولي وإدارة النظام والرتب</b> 🛡️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{admins_formatted}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"💡 <b>كيفية تعيين رتبة الشرير وقلب التفضيل بالسالب:</b>\n"
            f"<code>/villain 123456789</code>\n\n"
            f"💡 <b>كيفية ترقية أو تعيين أي رتبة أخرى:</b>\n"
            f"<code>/promote 123456789 VIP</code>\n"
            f"<code>/promote 123456789 FAVORITE</code>\n"
            f"<code>/promote 123456789 WISE</code>\n"
            f"<code>/promote 123456789 JESTER</code>\n"
            f"<code>/promote 123456789 COLD</code>\n\n"
            f"💡 <b>لحذف رتبة عضو وإرجاعه عادياً:</b>\n"
            f"<code>/del_admin 123456789</code>"
            f"</blockquote>"
        )

        buttons = [
            [{"text": "🔄 تحديث قائمة الإدارة 👑", "callback_data": "menu:admins", "style": "primary"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_rules_list(cls, user_id: int = 0) -> Tuple[str, Dict[str, Any]]:
        """
        Displays active behavioral constraints and prohibitions.
        """
        rules = await admin_manager.list_active_rules()
        if rules:
            lines = []
            for r in rules:
                rid = r["id"]
                txt = r["instruction_text"]
                lines.append(f"• <b>قاعدة #{rid}:</b> <code>{txt}</code>")
            rules_str = "\n".join(lines)
        else:
            rules_str = "<i>لا توجد موانع أو قواعد مقيدة نشطة حالياً. البوت بحالته الطبيعية الحرة.</i>"

        text = (
            f"📜 <b>سجل القواعد والممنوعات السلوكية النشطة</b> ⚖️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{rules_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"💡 <b>كيفية إضافة ممنوعات أو أوامر جديدة في الشات:</b>\n"
            f"اكتب:\n"
            f"<code>/add_rule ممنوع التحدث في السياسة</code>\n"
            f"أو بحرية: <code>ممنوع تقول كذا</code>\n\n"
            f"💡 <b>لحذف قاعدة:</b>\n"
            f"<code>/del_rule 1</code>\n"
            f"<i>(متاحة للأدمنز ومالك النظام فقط).</i>"
            f"</blockquote>"
        )

        buttons = [
            [{"text": "🔄 تحديث القواعد النشطة 📜", "callback_data": "menu:rules", "style": "primary"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    # Aliases for panels
    render_rules_panel = render_rules_list
    render_admins_panel = render_admins_list

    @classmethod
    async def render_dialects_info(cls) -> Tuple[str, Dict[str, Any]]:
        """
        Displays supported regional dialects and Chameleon status.
        """
        dialects_list = [
            "🇸🇦 <b>السعودية والخليج:</b> نجد، الحجاز، الكويت، الإمارات، البحرين، قطر",
            "🇸🇾 <b>بلاد الشام:</b> سوريا، لبنان، فلسطين، الأردن",
            "🇮🇶 <b>العراق:</b> بغداد، البصرة، الموصل، أربيل",
            "🇲🇦 <b>المغرب العربي:</b> المغرب، الجزائر، تونس",
            "🇸🇩 <b>السودان:</b> الخرطوم، أم درمان",
            "🇾🇪 <b>اليمن:</b> صنعاء، عدن، حضرموت",
            "🇪🇬 <b>مصر:</b> القاهرة، المعادي، الإسكندرية",
            "🌐 <b>الإنجليزية والفصحى:</b> دعم كامل متقن ومرن",
        ]
        dialects_str = "\n".join(dialects_list)

        text = (
            f"🌐 <b>محرك الحرباء اللغوية ومجاراة اللهجات</b> 🗺️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{dialects_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote>يقوم البوت تلقائياً بكشف لهجة كل عضو في الجروب والرد عليه بنفس مصطلحاته وعاداته الشعبية ونبرته الصوتية!</blockquote>"
        )

        buttons = [
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_media_center(cls) -> Tuple[str, Dict[str, Any]]:
        """
        Multimodal interactive triggers (voice note & selfie test).
        """
        loc = life_sim.get_current_location_state()
        text = (
            f"🎙️ <b>مركز الميديا والتوليد الحي</b> 📸\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>موقع عمر الحالي:</b> <b>{loc.location_name_ar}</b>\n"
            f"🎙️ <b>محرك الصوت:</b> <code>Edge-TTS Neural Voice (Multi-Dialect)</code>\n"
            f"📸 <b>محرك الصور:</b> <code>Flux Realism Cloud Engine (Seed: 42069)</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>اضغط على أحد الأزرار أدناه ليقوم عمر بإرسال فويس أو صورة لك الآن:</i>"
        )

        buttons = [
            [
                {"text": "🎙️ اطلب فويس حصري من عمر 🎵", "callback_data": "act:send_voice", "style": "success"},
                {"text": "📸 اطلب سيلفي حي من عمر 📷", "callback_data": "act:send_photo", "style": "primary"},
            ],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}


    @classmethod
    async def render_bot_arena_panel(
        cls,
        user_id: int,
        chat_id: Optional[int] = None,
        status_banner: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Task 4.1: Renders the Interactive Group Control Panel for Bot-to-Bot Group Conversations (Bot Arena).
        Includes the exact mandatory callback buttons:
        - 🔥 تشغيل حوار البوتات (مفتوح حتى الإيقاف) (bot_arena:start:infinite:{chat_id})
        - 🎯 حوار 5 جولات (bot_arena:start:5:{chat_id})
        - 🎯 حوار 10 جولات (bot_arena:start:10:{chat_id})
        - 🎲 اختيار موضوع نقاش عشوائي (bot_arena:topic:{chat_id})
        - 🛑 إيقاف حوار البوتات فوراً (bot_arena:stop:{chat_id})
        """
        from core_config.sovereignty_rules import sovereignty_guard
        is_owner = sovereignty_guard.is_the_king(user_id) or (user_id in settings.super_admin_ids_list)
        if not is_owner:
            return (
                "🚫 <b>ساحة حوار البوتات الحي (Bot Arena) مخصصة لمالك النظام (ECENN) فقط 👑</b>",
                {"inline_keyboard": [[{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}]]},
            )

        known_groups = await sibling_network.get_known_groups_async()
        target_chat_id = chat_id if (chat_id is not None and chat_id < 0) else None
        if target_chat_id is None:
            # Pick currently active arena group, or most recent known group, or fallback
            for g in known_groups:
                if g.get("is_active"):
                    target_chat_id = int(g["chat_id"])
                    break
            if target_chat_id is None and known_groups:
                target_chat_id = int(known_groups[0]["chat_id"])
            if target_chat_id is None:
                target_chat_id = int(chat_id or user_id)

        present_bots = await sibling_network.discover_present_bots(target_chat_id)
        sess = sibling_network.get_arena_session(target_chat_id)
        is_running = bool(sess and sess.is_active)
        topic = sibling_network.get_arena_topic(target_chat_id)
        chat_title = (
            sess.chat_title
            if sess
            else sibling_network._known_group_titles.get(target_chat_id, f"الجروب ({target_chat_id})")
        )

        bot_badges = []
        for b in present_bots:
            g_icon = "👧" if getattr(b, "gender", "male") == "female" else "👦"
            ub_tag = " (Userbot)" if getattr(b, "is_userbot", False) else ""
            bot_badges.append(f"<b>{html.escape(getattr(b, 'name', 'بوت'))}</b> {g_icon}{ub_tag}")
        bots_display = " ، ".join(bot_badges) if bot_badges else "<i>جاري اكتشاف البوتات...</i>"

        if is_running and sess:
            max_r_txt = "مفتوح حتى الإيقاف ♾️" if sess.max_rounds >= 999999 else f"{sess.max_rounds} جولات"
            state_line = f"🟢 <b>نشط الآن (الجولة {sess.current_round} من {max_r_txt})</b>"
            last_sp = sess.last_speaker_name or "يستعد للبدء..."
        else:
            state_line = "⚪ <b>متوقف حالياً (جاهز للانطلاق)</b>"
            last_sp = "—"

        banner_block = f"<blockquote>{status_banner}</blockquote>\n" if status_banner else ""

        text = (
            f"🔥 <b>لوحة تحكم حوار البوتات الحي في الجروبات (Bot Arena)</b> 🗣️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{banner_block}"
            f"👥 <b>الجروب المستهدف:</b> <b>{html.escape(str(chat_title))}</b> (<code>{target_chat_id}</code>)\n"
            f"📡 <b>حالة الحوار:</b> {state_line}\n"
            f"🤖 <b>البوتات المتواجدة في الجروب ({len(present_bots)}):</b>\n"
            f"   └ {bots_display}\n"
            f"🎲 <b>موضوع النقاش المختار:</b>\n"
            f"   └ <i>«{html.escape(topic)}»</i>\n"
            f"🗣️ <b>آخر متحدث:</b> <code>{html.escape(str(last_sp))}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>أثناء الحوار يمكنك التدخل والكتابة في الجروب في أي لحظة، وسيرد عليك البوت التالي فوراً ويدمج كلامك في نقاشهم!</i>"
        )

        buttons: List[List[Dict[str, Any]]] = [
            [
                {
                    "text": "🔥 تشغيل حوار البوتات (مفتوح حتى الإيقاف)",
                    "callback_data": f"bot_arena:start:infinite:{target_chat_id}",
                    "style": "success",
                }
            ],
            [
                {
                    "text": "🎯 حوار 5 جولات",
                    "callback_data": f"bot_arena:start:5:{target_chat_id}",
                    "style": "primary",
                },
                {
                    "text": "🎯 حوار 10 جولات",
                    "callback_data": f"bot_arena:start:10:{target_chat_id}",
                    "style": "primary",
                },
            ],
            [
                {
                    "text": "🎲 اختيار موضوع نقاش عشوائي",
                    "callback_data": f"bot_arena:topic:{target_chat_id}",
                    "style": "primary",
                }
            ],
            [
                {
                    "text": "🛑 إيقاف حوار البوتات فوراً",
                    "callback_data": f"bot_arena:stop:{target_chat_id}",
                    "style": "danger",
                }
            ],
        ]

        # If opened in private DM and multiple groups exist, display group switcher pills
        if (chat_id is None or chat_id > 0) and len(known_groups) > 1:
            group_row: List[Dict[str, Any]] = []
            for g in known_groups[:4]:
                gid = int(g["chat_id"])
                gtitle = str(g["title"])[:16]
                prefix = "✅ " if gid == target_chat_id else "👥 "
                group_row.append(
                    {
                        "text": f"{prefix}{gtitle}",
                        "callback_data": f"bot_arena:select_group:{gid}",
                        "style": "success" if gid == target_chat_id else "primary",
                    }
                )
                if len(group_row) == 2:
                    buttons.append(group_row)
                    group_row = []
            if group_row:
                buttons.append(group_row)

        buttons.append(
            [
                {"text": "🔄 تحديث الحالة ⚡", "callback_data": f"bot_arena:refresh:{target_chat_id}", "style": "primary"},
                {"text": "🔙 الرئيسية 🏠", "callback_data": "menu:main", "style": "danger"},
            ]
        )
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def handle_callback(
        cls,
        callback_data: str,
        user_id: int,
        user_name: str = "مستخدم",
        bot_instance: Optional[Any] = None,
        chat_id: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Dispatches callback query to appropriate renderer or action.
        Returns: (text, reply_markup, alert_text, action_trigger)
        """
        if callback_data in ("menu:main", "menu:refresh_main") or callback_data.startswith("menu:main:"):
            text, markup = await cls.render_main_dashboard(user_id, user_name=user_name, bot_instance=bot_instance)
            return text, markup, None, None

        elif callback_data in ("menu:user_affinity", "act:refresh_affinity") or callback_data.startswith("menu:user_affinity:"):
            text, markup = await cls.render_user_affinity_profile(user_id, user_name=user_name)
            alert = "💖 تم تحديث تفاصيل مكانتك ورصيدك بنجاح!" if "act:refresh_affinity" in callback_data else None
            return text, markup, alert, None

        elif callback_data == "menu:server_stats":
            text, markup = await cls.render_server_stats()
            return text, markup, None, None

        elif callback_data == "menu:mood_radar":
            text, markup = await cls.render_mood_radar()
            return text, markup, None, None

        elif callback_data == "menu:admins":
            text, markup = await cls.render_admins_panel(user_id)
            return text, markup, None, None

        elif callback_data == "menu:rules":
            text, markup = await cls.render_rules_panel()
            return text, markup, None, None

        elif callback_data == "menu:dialects":
            text, markup = await cls.render_dialects_info()
            return text, markup, None, None

        elif callback_data == "menu:media":
            text, markup = await cls.render_media_center()
            return text, markup, None, None

        elif callback_data == "act:coffee":
            endocrine_engine.update_state_from_event("coffee", dopamine_delta=0.25, energy_delta=0.20)
            text, markup = await cls.render_mood_radar()
            return text, markup, "☕ عمر شرب قهوة مزبوطة، والدوبامين والطاقة ارتفعوا!", None

        elif callback_data == "act:chill":
            endocrine_engine.update_state_from_event("chill", cortisol_delta=-0.30, serotonin_delta=0.20)
            text, markup = await cls.render_mood_radar()
            return text, markup, "🌿 عمر أخذ نفس عميق ومزاجه راق، والكورتيزول انخفض!", None

        elif callback_data == "act:send_voice":
            return None, None, "🎙️ جاري تجهيز وإرسال تسجيل صوتي خاص بك...", "send_voice"

        elif callback_data == "act:send_photo":
            return None, None, "📸 جاري التقاط وإرسال صورة سيلفي حية لك...", "send_photo"

        elif callback_data == "menu:personas":
            text, markup = await cls.render_personas_menu(user_id)
            return text, markup, None, None

        elif callback_data.startswith("act:set_persona:"):
            target_code = callback_data.split(":")[-1]
            ok, msg = persona_shifter.set_persona(target_code, user_id=user_id, reason="MENU_CALLBACK_CLICK")
            text, markup = await cls.render_personas_menu(user_id)
            p_def = persona_registry.get_persona(target_code)
            return text, markup, f"🎭 تم تفعيل شخصية: {p_def.name_ar}!", None

        elif callback_data == "menu:webapp" or callback_data.startswith("menu:webapp:"):
            text, markup = await cls.render_webapp_panel(user_id, bot_instance=bot_instance)
            return text, markup, None, None


        elif callback_data == "menu:bot_arena" or callback_data.startswith("bot_arena:"):
            from core_config.sovereignty_rules import sovereignty_guard
            is_owner = sovereignty_guard.is_the_king(user_id) or (user_id in settings.super_admin_ids_list)
            if not is_owner:
                return None, None, "🚫 هذا التحكم مخصص لمالك النظام (ECENN) فقط 👑", None

            if callback_data == "menu:bot_arena":
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=chat_id)
                return text, markup, None, None

            parts = callback_data.split(":")
            action = parts[1] if len(parts) > 1 else ""

            if action == "select_group" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=target_cid)
                return text, markup, "✅ تم تحديد الجروب المستهدف!", None

            if action == "refresh" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id
                text, markup = await cls.render_bot_arena_panel(user_id=user_id, chat_id=target_cid)
                return text, markup, "🔄 تم تحديث حالة ساحة الحوار!", None

            if action == "topic" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id or user_id
                new_topic = sibling_network.pick_random_arena_topic(target_cid)
                banner = f"🎲 <b>تم اختيار موضوع نقاش عشوائي جديد:</b>\n«{html.escape(new_topic)}»"
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                return text, markup, f"🎲 الموضوع: {new_topic[:45]}...", None

            if action == "start" and len(parts) >= 4:
                rounds_str = parts[2].lower()
                try:
                    target_cid = int(parts[3])
                except ValueError:
                    target_cid = chat_id or user_id
                max_rounds = 999999 if rounds_str == "infinite" else max(1, int(rounds_str))
                sess = await sibling_network.start_bot_arena(
                    chat_id=target_cid,
                    max_rounds=max_rounds,
                    started_by=user_id,
                )
                rounds_ar = "مفتوح حتى الإيقاف ♾️" if max_rounds >= 999999 else f"{max_rounds} جولات"
                banner = (
                    f"🔥 <b>انطلق حوار البوتات الحي الآن ({rounds_ar})!</b>\n"
                    f"الموضوع: «{html.escape(sess.topic)}»"
                )
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                return text, markup, f"🔥 بدأ حوار البوتات ({rounds_ar})!", None

            if action == "stop" and len(parts) >= 3:
                try:
                    target_cid = int(parts[2])
                except ValueError:
                    target_cid = chat_id or user_id
                was_stopped = await sibling_network.stop_bot_arena(
                    chat_id=target_cid, reason="إيقاف فوري من زر لوحة التحكم"
                )
                banner = (
                    "🛑 <b>تم إيقاف حوار البوتات في الجروب فوراً!</b>"
                    if was_stopped
                    else "ℹ️ <b>حوار البوتات متوقف بالفعل في هذا الجروب.</b>"
                )
                text, markup = await cls.render_bot_arena_panel(
                    user_id=user_id, chat_id=target_cid, status_banner=banner
                )
                toast = "🛑 تم إيقاف حوار البوتات فوراً!" if was_stopped else "ℹ️ الحوار متوقف بالفعل."
                return text, markup, toast, None

        elif callback_data == "menu:bot_factory":
            text, markup = await cls.render_bot_factory_panel(user_id)
            return text, markup, None, None

        elif callback_data.startswith("bf_panel:"):
            target_bid = callback_data.split(":", 1)[1].strip() or (
                bot_instance.instance_id if bot_instance else "master_omar_official"
            )
            text, markup = await cls.render_single_bot_editor_panel(user_id, target_bid)
            return text, markup, None, None

        elif callback_data.startswith("bf_wiz:"):
            parts = callback_data.split(":")
            sub_act = parts[1] if len(parts) > 1 else ""
            target_bid = parts[2] if len(parts) > 2 else (
                bot_instance.instance_id if bot_instance else "master_omar_official"
            )
            active_host_bid = bot_instance.instance_id if bot_instance else target_bid
            from bot_factory.multi_bot_dispatcher import multi_bot_dispatcher

            if sub_act == "create_bot":
                if not bot_factory.is_factory_admin(user_id):
                    return (
                        "⛔ عذراً، صلاحية إنشاء البوتات مخصصة للأدمنز المعتمدين فقط.",
                        {"inline_keyboard": [[{"text": "🔙 العودة", "callback_data": "menu:main"}]]},
                        "⛔ غير مصرح",
                        None,
                    )
                multi_bot_dispatcher.set_pending_admin_action(user_id, active_host_bid, "create_bot_token")
                prompt_txt = (
                    "➕ <b>إنشاء بوت جديد في مصنع البوتات الخاص بك</b> 🤖✨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "1️⃣ اذهب إلى @BotFather وأنشئ بوت جديد (أو انسخ توكن بوتك).\n"
                    "2️⃣ <b>أرسل الآن توكن البوت (Bot Token)</b> هنا في الشات مباشرةً:\n"
                    "<i>(مثال: <code>123456789:AAF...</code>)</i>\n\n"
                    "🔒 <i>ملاحظة: البوت الذي تنشئه سيكون معزولاً في مصنعك الخاص بك وحدك وتتحكم به بالكامل.</i>"
                )
                mk = {
                    "inline_keyboard": [
                        [{"text": "❌ إلغاء والعودة للمصنع", "callback_data": "menu:bot_factory", "style": "danger"}]
                    ]
                }
                return prompt_txt, mk, "أرسل توكن البوت الآن في الشات 🔑", None

            if not bot_factory.can_user_manage_bot(user_id, target_bid):
                return (
                    "⛔ عذراً، يمكنك فقط تعديل البوتات الخاصة بك التي تملك صلاحيتها.",
                    {"inline_keyboard": [[{"text": "🔙 العودة", "callback_data": "menu:main"}]]},
                    "⛔ غير مصرح لك بتعديل هذا البوت",
                    None,
                )

            t_bot = bot_factory.get_bot(target_bid)
            if not t_bot:
                return "⚠️ البوت غير موجود.", {"inline_keyboard": [[{"text": "🔙 العودة", "callback_data": "menu:bot_factory"}]]}, "البوت غير موجود", None

            if sub_act == "gender":
                next_g = BotGender.MALE if t_bot.gender == BotGender.FEMALE else BotGender.FEMALE
                ok, msg = bot_factory.set_bot_gender(target_bid, next_g)
                await multi_bot_dispatcher.push_botfather_profile_update(t_bot)
                text, markup = await cls.render_single_bot_editor_panel(user_id, target_bid, status_banner=msg)
                return text, markup, "✅ تم تحديث الجنس!", None

            if sub_act == "sync":
                ok, msg = await multi_bot_dispatcher.push_botfather_profile_update(t_bot)
                text, markup = await cls.render_single_bot_editor_panel(user_id, target_bid, status_banner=msg)
                return text, markup, "✅ تمت المزامنة مع BotFather!", None

            wiz_map = {
                "name": (
                    "set_name",
                    f"✏️ <b>تغيير اسم البوت «{t_bot.name}» في تليجرام (BotFather):</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• الاسم الحالي: <b>{html.escape(t_bot.name)}</b>\n\n"
                    f"✍️ <b>أرسل الآن الاسم الجديد في الشات</b> وسيتم تغييره فوراً في BotFather وفي النظام:",
                ),
                "photo": (
                    "set_photo",
                    f"🖼️ <b>تغيير الصورة الشخصية (Profile Photo) للبوت «{t_bot.name}» في BotFather:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📸 <b>أرسل الآن الصورة الجديدة في الشات مباشرًة</b> وسيقوم البوت برفعها وتعيينها كصورة البروفايل الرسمية في تليجرام (BotFather) وفي التطبيق المصغر فوراً:",
                ),
                "bio": (
                    "set_bio",
                    f"📝 <b>تغيير بايو البوت «{t_bot.name}» في تليجرام (BotFather Bio):</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• البايو الحالي: <i>{html.escape(t_bot.bio or 'غير محدد')}</i>\n\n"
                    f"✍️ <b>أرسل الآن البايو (النبذة التعريفية) الجديد في الشات</b> لتحديثه في صفحة البوت على تليجرام:",
                ),
                "prompt": (
                    "set_prompt",
                    f"🧠 <b>تغيير برومبت وشخصية البوت «{t_bot.name}»:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• البرومبت الحالي:\n<blockquote>{html.escape((t_bot.system_prompt or '')[:350])}</blockquote>\n\n"
                    f"✍️ <b>أرسل الآن تعليمات الشخصية والبرومبت الجديد في الشات:</b>",
                ),
                "origin": (
                    "set_origin",
                    f"🌍 <b>تغيير بلد وموطن وتوقيت البوت «{t_bot.name}»:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• البلد الحالي: <b>{html.escape(t_bot.origin_location or 'غير محدد')}</b>\n\n"
                    f"✍️ <b>أرسل الآن اسم البلد أو المدينة</b> (مثال: <code>سوريا</code>، <code>دمشق</code>، <code>العراق</code>، <code>السعودية</code>، <code>مصر</code>):",
                ),
                "dialect": (
                    "set_dialect",
                    f"🗣️ <b>تغيير لهجة وأسلوب تحدث البوت «{t_bot.name}»:</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• اللهجة الحالية: <i>{html.escape(t_bot.primary_dialect or '')}</i>\n\n"
                    f"✍️ <b>أرسل الآن وصف اللهجة الجديد في الشات:</b>",
                ),
            }
            if sub_act in wiz_map:
                pend_key, prompt_html = wiz_map[sub_act]
                multi_bot_dispatcher.set_pending_admin_action(
                    user_id, active_host_bid, pend_key, {"target_bot_id": target_bid}
                )
                mk = {
                    "inline_keyboard": [
                        [{"text": f"❌ إلغاء والعودة لإعدادات {t_bot.name}", "callback_data": f"bf_panel:{target_bid}", "style": "danger"}]
                    ]
                }
                return prompt_html, mk, "✍️ أرسل القيمة الجديدة الآن في الشات", None

        elif callback_data == "act:request_factory_perm":
            from bot_factory.factory_manager import factory_access_manager
            await factory_access_manager.submit_access_request(user_id, user_name)
            return (
                "📨 <b>تم إرسال طلبك بنجاح!</b> 👑\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "تم إشعار إدارة النظام والملك برغبتك في استخدام مصنع البوتات.\n"
                "ستصلك رسالة فورية بمجرد مراجعة طلبك والموافقة عليه.",
                {"inline_keyboard": [[{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main"}]]},
                "تم إرسال الطلب للمطور والملك بنجاح ✅",
                None,
            )

        elif callback_data.startswith("act:factory_perm:"):
            from bot_factory.factory_manager import factory_access_manager
            parts = callback_data.split(":")
            action = parts[2]
            target_uid = int(parts[3])
            if action == "approve":
                res_msg = await factory_access_manager.approve_user(target_uid, operator_id=user_id)
            else:
                res_msg = await factory_access_manager.reject_user(target_uid, operator_id=user_id)
            return res_msg, {"inline_keyboard": [[{"text": "🔙 العودة", "callback_data": "menu:main"}]]}, res_msg, None

        elif callback_data.startswith("act:toggle_gender:"):
            parts = callback_data.split(":")
            if len(parts) >= 4:
                inst_id = parts[2]
                if not bot_factory.can_user_manage_bot(user_id, inst_id):
                    return (
                        "⛔ عذراً يا غالي، يمكنك فقط تعديل البوتات الخاصة بك!",
                        {"inline_keyboard": [[{"text": "🔙 العودة", "callback_data": "menu:main"}]]},
                        "⛔ غير مصرح لك بتعديل هذا البوت",
                        None,
                    )
                next_gen = BotGender.FEMALE if parts[3] == "FEMALE" else BotGender.MALE
                ok, msg = bot_factory.set_bot_gender(inst_id, next_gen)
                text, markup = await cls.render_bot_factory_panel(user_id)
                return text, markup, msg, None

        elif callback_data == "menu:my_persona":
            text, markup = await cls.render_my_persona_panel(user_id)
            return text, markup, None, None

        elif callback_data.startswith("act:persona_toggle_gender:"):
            next_g = callback_data.split(":")[-1]
            persona_virtualizer.update_persona(user_id, gender=next_g)
            text, markup = await cls.render_my_persona_panel(user_id)
            g_ar = "بنت 👧" if next_g == "female" else "ولد 👦"
            return text, markup, f"تم تحويل الشخصية إلى {g_ar} بنجاح!", None

        elif callback_data == "menu:persona_dialects":
            text, markup = await cls.render_persona_dialects_menu(user_id)
            return text, markup, None, None

        elif callback_data.startswith("act:persona_set_dialect:"):
            target_dialect = callback_data.split(":")[-1]
            persona_virtualizer.update_persona(user_id, dialect=target_dialect)
            text, markup = await cls.render_my_persona_panel(user_id)
            return text, markup, f"تم ضبط اللهجة إلى: {target_dialect}!", None

        elif callback_data == "act:persona_reset":
            persona_virtualizer.reset_persona(user_id)
            text, markup = await cls.render_my_persona_panel(user_id)
            return text, markup, "تمت إعادة تعيين شخصيتك للافتراضي بنجاح!", None

        elif callback_data == "menu:my_commands":
            text, markup = await cls.render_my_commands_panel(user_id)
            return text, markup, None, None

        elif callback_data == "act:clear_my_cmds":
            custom_commands.clear_user_commands(user_id)
            text, markup = await cls.render_my_commands_panel(user_id)
            return text, markup, "تم مسح جميع أوامرك المخصصة بنجاح!", None

        elif callback_data == "menu:games":
            text, markup = await cls.render_games_panel(user_id, user_name)
            return text, markup, None, None

        elif callback_data == "act:game_xo":
            text, markup = group_games.start_xo_game(user_id, user_id, user_name)
            return text, markup, "بدأت جولة إكس أو! دورك (❌)", None

        elif callback_data.startswith("xo:"):
            parts = callback_data.split(":")
            if len(parts) >= 3:
                game_id = parts[1]
                cell_idx = parts[2]
                text, markup, toast = await group_games.handle_xo_click(game_id, cell_idx, user_id, user_name)
                return text, markup, toast, None

        elif callback_data == "act:game_trivia":
            text, markup = group_games.start_trivia_question(user_name)
            return text, markup, None, None

        elif callback_data.startswith("trivia:"):
            parts = callback_data.split(":")
            if len(parts) >= 3:
                q_id = parts[1]
                opt_idx = int(parts[2])
                text, markup, toast = await group_games.handle_trivia_answer(q_id, opt_idx, user_id, user_name)
                return text, markup, toast, None

        elif callback_data == "act:game_rps":
            text = (
                f"✊✋✌️ <b>تحدي حجرة ورقة مقص ضد عُـمـر!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"اختر حركتك بذكاء يا <b>{user_name}</b> وسأكشف حركتي فوراً:"
            )
            buttons = [
                [
                    {"text": "🪨 حجرة", "callback_data": "rps:rock", "style": "primary"},
                    {"text": "📄 ورقة", "callback_data": "rps:paper", "style": "primary"},
                    {"text": "✂️ مقص", "callback_data": "rps:scissors", "style": "primary"},
                ],
                [{"text": "🔙 ساحة الألعاب 🎮", "callback_data": "menu:games", "style": "danger"}],
            ]
            return text, {"inline_keyboard": buttons}, None, None

        elif callback_data.startswith("rps:"):
            u_choice = callback_data.split(":")[-1]
            text, markup, toast = await group_games.play_rps(u_choice, user_id, user_name)
            return text, markup, toast, None

        # Check feature_callbacks_router for V3.0, V4.0, and V5.0 callbacks
        try:
            from official_bot_engine.feature_callbacks_router import feature_callbacks_router
            feat_res = await feature_callbacks_router.handle_feature_callback(callback_data, user_id, user_name)
            if feat_res is not None:
                return feat_res
        except Exception as exc:
            logger.warning(f"Feature callbacks router handling error: {exc}")

        # Default fallback
        text, markup = await cls.render_main_dashboard(user_id, user_name=user_name)
        return text, markup, None, None

    @classmethod
    async def render_personas_menu(cls, user_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Renders multi-persona character switcher panel.
        """
        active = persona_shifter.get_active_persona()
        text = (
            f"🎭 <b>لوحة تبديل شخصيات وأقنعة «عمر» التفاعلية</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 <b>الشخصية النشطة حالياً:</b> <b>{active.name_ar}</b>\n"
            f"📝 <b>الوصف:</b> <i>{active.tagline}</i>\n"
            f"⚡ <b>المزاج:</b> <code>{active.temperament}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>اضغط على أي زر لتغيير شخصية ومزاج عمر فوراً:</i>"
        )

        buttons = [
            [
                {"text": "🦁 عمر المتوازن", "callback_data": "act:set_persona:DEFAULT_BALANCED", "style": "primary"},
                {"text": "📜 العالم الموسوعي", "callback_data": "act:set_persona:SCHOLAR", "style": "primary"},
            ],
            [
                {"text": "♟️ شادو الغامض", "callback_data": "act:set_persona:SHADOW_AYANOKOJI", "style": "primary"},
                {"text": "🤣 الفرفوش (Jester)", "callback_data": "act:set_persona:JESTER", "style": "success"},
            ],
            [
                {"text": "💖 الرومانسي الحنون", "callback_data": "act:set_persona:ROMANTIC", "style": "primary"},
                {"text": "🤝 ابن البلد الجدع", "callback_data": "act:set_persona:EGYPTIAN_STREET", "style": "primary"},
            ],
            [
                {"text": "🦹 قاهر الأشرار", "callback_data": "act:set_persona:VILLAIN_HUNTER", "style": "danger"},
            ],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_webapp_panel(
        cls, user_id: int, bot_instance: Optional[Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Renders Telegram Mini App WebApp launch information with live HTTPS links and direct WebApp buttons.
        """
        b_id = bot_instance.instance_id if bot_instance else "master_omar_official"
        b_name = bot_instance.name if (bot_instance and bot_instance.instance_id != "master_omar_official") else "عمر"
        webapp_url = tunnel_manager.get_webapp_url()
        if webapp_url.startswith("https://"):
            base_clean = webapp_url.split("?")[0]
            webapp_url = f"{base_clean}?bot_id={b_id}&v={int(time.time())}"
        text = (
            f"🚀 <b>تطبيق تيليجرام المصغر (Telegram Mini App)</b> 🎮\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ استمتع بتجربة الجيل القادم من التفاعل مع عمر عبر الواجهة السحابية التفاعلية:\n\n"
            f"🎮 <b>ساحة ألعاب حية:</b> العب إكس أو (XO) ضد عمر وتحدي أسئلة الذكاء (Trivia)!\n"
            f"⚡ <b>رادار الهرمونات والمشاعر:</b> تابع دوبامين وكورتيزول عمر في بث حي.\n"
            f"🏆 <b>لوحة الشرف والمتصدرين:</b> تصنيف البلاط الملكي ورصيد المعزة.\n"
            f"🔬 <b>المختبر الأكاديمي:</b> لخص محاضراتك وأنشئ بنوك أسئلة وامتحانات فورية.\n"
            f"🏭 <b>مصنع البوتات:</b> إدارة بوتات بنات وشباب وتخصيص الشخصيات.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>رابط التطبيق الآمن (HTTPS):</b>\n"
            f"<code>{webapp_url}</code>\n"
            f"<i>💡 يمكنك أيضاً فتح التطبيق مباشرة من الزر الدائم بجوار مربع الكتابة:</i> <code>[🎮 عمر Mini App]</code>"
        )

        buttons = []
        if webapp_url.startswith("https://"):
            buttons.append([{"text": "🚀 فتح التطبيق المصغر داخل تيليجرام 🎮", "web_app": {"url": webapp_url}, "style": "success"}])
            buttons.append([{"text": "🌐 فتح في المتصفح الخارجي 📱", "url": webapp_url, "style": "primary"}])
        else:
            buttons.append([{"text": "🌐 فتح الرابط في المتصفح 📱", "url": webapp_url, "style": "primary"}])

        buttons.append([{"text": "🔄 تحديث الرابط والسيرفر ⚡", "callback_data": "menu:webapp", "style": "primary"}])
        buttons.append([{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}])
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_single_bot_editor_panel(
        cls,
        user_id: int,
        target_bot_id: str,
        status_banner: str = "",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Renders the live in-bot BotFather & Persona Editor Panel for a specific bot.
        Allows authorized admins (e.g. Marselin 8697154015 on Bato, or Supreme King settings.the_king_user_id)
        to edit the bot's BotFather Name, Profile Photo, Bio, Country/Timezone, and Prompt anytime directly from the bot!
        """
        if not bot_factory.can_user_manage_bot(user_id, target_bot_id):
            return (
                "⛔ <b>وصول مرفوض:</b> يمكنك فقط تعديل وإدارة البوتات الخاصة بك.",
                {"inline_keyboard": [[{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main"}]]},
            )

        bot = bot_factory.get_bot(target_bot_id)
        if not bot:
            return (
                "⚠️ لم يتم العثور على هذا البوت في المصنع.",
                {"inline_keyboard": [[{"text": "🔙 مصنع البوتات", "callback_data": "menu:bot_factory"}]]},
            )

        from utils.timezone_resolver import TimezoneResolver
        tz_info = TimezoneResolver.resolve_bot_timezone(
            origin_location=bot.origin_location or "",
            primary_dialect=bot.primary_dialect or "",
            system_prompt=bot.system_prompt or "",
            bio=bot.bio or "",
        )
        gender_txt = "👧 بنت (أنثى)" if bot.gender == BotGender.FEMALE else "👦 ولد (ذكر)"
        next_gender_txt = "👦 ولد" if bot.gender == BotGender.FEMALE else "👧 بنت"
        banner_block = f"<blockquote>{status_banner}</blockquote>\n" if status_banner else ""

        text = (
            f"⚙️ <b>لوحة تحكم BotFather وهوية البوت «{html.escape(bot.name)}»</b> 🤖✨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{banner_block}"
            f"• 🏷️ <b>الاسم في تليجرام (BotFather):</b> <b>{html.escape(bot.name)}</b>\n"
            f"• 📝 <b>البايو (BotFather Bio):</b> <i>{html.escape(bot.bio or 'غير محدد')}</i>\n"
            f"• 🖼️ <b>الصورة الشخصية:</b> <code>{'محدثة ومفعلة ✅' if bot.avatar_url else 'افتراضية (اضغط لتغييرها 📸)'}</code>\n"
            f"• 🌍 <b>البلد والتوقيت:</b> <b>{tz_info['flag']} {tz_info['capsule_location_ar']} ({tz_info['formatted_time_ar']})</b>\n"
            f"• 🚻 <b>الجنس:</b> <b>{gender_txt}</b>\n"
            f"• 🗣️ <b>اللهجة:</b> <i>{html.escape((bot.primary_dialect or '')[:90])}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"🧠 <b>البرومبت والشخصية الحالية:</b>\n"
            f"{html.escape((bot.system_prompt or '')[:350])}\n\n"
            f"⚡ <b>أوامر سريعة من الشات في أي وقت:</b>\n"
            f"• <code>/set_bot_name الاسم الجديد</code> (أو <code>/اسم_البوت</code>)\n"
            f"• <code>/set_bot_bio البايو الجديد</code> (أو <code>/بايو_البوت</code>)\n"
            f"• <code>/set_bot_photo</code> (أو <code>/صورة_البوت</code> لتغيير صورة البوت)\n"
            f"• <code>/set_bot_country البلد</code> (أو <code>/بلد_البوت</code>)\n"
            f"• <code>/set_bot_prompt البرومبت</code> (أو <code>/برومبت_البوت</code>)"
            f"</blockquote>\n"
            f"👇 <i>اضغط على أي زر أدناه لتعديله فوراً من داخل البوت:</i>"
        )

        buttons = [
            [
                {"text": "✏️ تغيير اسم البوت (BotFather)", "callback_data": f"bf_wiz:name:{bot.instance_id}", "style": "success"},
                {"text": "🖼️ تغيير صورة البوت (BotFather)", "callback_data": f"bf_wiz:photo:{bot.instance_id}", "style": "success"},
            ],
            [
                {"text": "📝 تغيير بايو البوت (BotFather)", "callback_data": f"bf_wiz:bio:{bot.instance_id}", "style": "primary"},
                {"text": "🌍 تغيير بلد وتوقيت البوت", "callback_data": f"bf_wiz:origin:{bot.instance_id}", "style": "primary"},
            ],
            [
                {"text": "🧠 تغيير البرومبت والشخصية", "callback_data": f"bf_wiz:prompt:{bot.instance_id}", "style": "primary"},
                {"text": "🗣️ تغيير اللهجة والأسلوب", "callback_data": f"bf_wiz:dialect:{bot.instance_id}", "style": "primary"},
            ],
            [
                {"text": f"🚻 تحويل الجنس إلى ({next_gender_txt})", "callback_data": f"bf_wiz:gender:{bot.instance_id}", "style": "primary"},
                {"text": "🔄 مزامنة مع BotFather الآن ⚡", "callback_data": f"bf_wiz:sync:{bot.instance_id}", "style": "success"},
            ],
            [
                {"text": "🏭 مصنع البوتات الخاص بي 🤖", "callback_data": "menu:bot_factory", "style": "primary"},
                {"text": "🔙 القائمة الرئيسية 🏠", "callback_data": "menu:main", "style": "danger"},
            ],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_bot_factory_panel(cls, user_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Renders the Multi-Tenant Bot & Userbot Factory Dashboard.
        Strictly isolated per admin:
        - Supreme King (settings.the_king_user_id) sees all bots.
        - Marselin (8697154015) or any secondary admin ONLY sees bots they created/own!
        """
        is_admin = bot_factory.is_factory_admin(user_id)
        if not is_admin:
            try:
                async with db_manager.session() as session:
                    u_repo = UserRepository(session)
                    u_rec = await u_repo.get_by_telegram_id(user_id)
                    if u_rec and u_rec.role in ("SUPER_ADMIN", "ADMIN"):
                        is_admin = True
            except Exception:
                pass

        if not is_admin:
            denied_text = (
                "🔒 <b>مصنع البوتات واليوزربوت (Admins Only)</b> 🤖\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "مصنع البوتات مخصص حصرياً للمسؤولين والسوبر أدمن.\n"
                "إذا كنت ترغب في إنشاء وتخصيص بوتك الخاص تحت إشراف الإدارة، اضغط على زر إرسال الطلب أدناه للموافقة:"
            )
            denied_keyboard = {
                "inline_keyboard": [
                    [{"text": "📨 إرسال طلب تصريح إنشاء بوت 🤖", "callback_data": "act:request_factory_perm", "style": "success"}],
                    [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}],
                ]
            }
            return denied_text, denied_keyboard

        # STRICT ISOLATION: Marselin (8697154015) only receives his own bots, NEVER the Supreme King's bots!
        bots = bot_factory.list_bots_for_user(user_id)
        lines = []
        buttons = [
            [{"text": "➕ إنشاء بوت جديد في المصنع 🚀", "callback_data": "bf_wiz:create_bot:master_omar_official", "style": "success"}]
        ]

        from utils.timezone_resolver import TimezoneResolver
        for idx, b in enumerate(bots):
            gender_txt = "👧 بنت" if b.gender == BotGender.FEMALE else "👦 ولد"
            status_txt = "🟢 نشط" if b.is_active else "⚪ متوقف"
            tz_info = TimezoneResolver.resolve_bot_timezone(
                origin_location=b.origin_location or "",
                primary_dialect=b.primary_dialect or "",
                system_prompt=b.system_prompt or "",
                bio=b.bio or "",
            )
            lines.append(
                f"• <b>{html.escape(b.name)}</b> [{tz_info['flag']} {tz_info['capsule_location_ar']} | {status_txt} | {gender_txt}]"
            )

            buttons.append([
                {
                    "text": f"⚙️ تعديل «{b.name}» (الاسم • الصورة • البايو)",
                    "callback_data": f"bf_panel:{b.instance_id}",
                    "style": "primary",
                }
            ])

        bots_summary = "\n".join(lines) if lines else "<i>لا توجد بوتات مسجلة في مصنعك بعد. اضغط على «➕ إنشاء بوت جديد» للبدء!</i>"
        is_supreme = bot_factory.is_supreme_king(user_id)
        factory_title = (
            "🏭 <b>لوحة تحكم مصنع البوتات الشامل (الملك الأعلى)</b> 👑"
            if is_supreme
            else "🏭 <b>لوحة تحكم مصنع البوتات الخاص بك (معزول ومستقل)</b> 🤖"
        )

        text = (
            f"{factory_title}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>بوتاتك المسجلة حالياً ({len(bots)}):</b>\n"
            f"{bots_summary}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"💡 <b>مزايا التحكم المباشر في بوتاتك:</b>\n"
            f"• اضغط على <b>«⚙️ تعديل»</b> بجانب أي بوت لتغيير <b>اسمه، صورته الشخصية، والبايو في تليجرام (BotFather)</b> مباشرًة من داخل الشات دون الحاجة للتواصل مع أي شخص!\n"
            f"• اضغط على <b>«➕ إنشاء بوت جديد»</b> لإضافة بوت جديد خاص بك بتوكن @BotFather في ثوانٍ.\n"
            f"• يمكنك أيضاً فتح التطبيق المصغر (Mini App) لإدارة بوتاتك بصرياً."
            f"</blockquote>"
        )

        buttons.append([{"text": "🔄 تحديث قائمة بوتاتي ⚡", "callback_data": "menu:bot_factory", "style": "success"}])
        buttons.append([{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "danger"}])
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_my_persona_panel(cls, user_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Renders the Multi-Tenant Isolated Persona Studio for DM interaction.
        """
        p = persona_virtualizer.get_persona(user_id)
        gender_txt = "👧 أنثى / بنت" if p.gender == "female" else "👦 ذكر / شاب"
        custom_prompt_display = p.custom_system_prompt or "<i>افتراضي (لا يوجد توجيه إضافي)</i>"

        dna_words = ""
        if p.cloned_linguistic_dna and p.cloned_linguistic_dna.get("favorite_words"):
            dna_words = ", ".join(p.cloned_linguistic_dna.get("favorite_words")[:8])

        dna_section = f"\n🧬 <b>بصمتك اللغوية المستنسخة:</b> <code>{dna_words}</code>" if dna_words else ""

        text = (
            f"🎭 <b>استوديو شخصيتك الخاصة في الخاص (Isolated Sandbox)</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"هنا يمكنك ضبط شخصية البوت ليعاملك بها في <b>الشات الخاص فقط</b> دون أن يؤثر ذلك على الجروبات أو أي مستخدم آخر:\n\n"
            f"• 🏷️ <b>اسم الشخصية المعتمد:</b> <b>{p.persona_name}</b>\n"
            f"• 🚻 <b>النوع:</b> <b>{gender_txt}</b>\n"
            f"• 🗺️ <b>اللهجة والأسلوب:</b> <b>{p.dialect}</b>\n"
            f"• 🎭 <b>الطابع النفسي:</b> <i>{p.tone}</i>\n"
            f"• 📝 <b>التوجيه المخصص:</b> {custom_prompt_display}{dna_section}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"🛠️ <b>أوامر التخصيص السريعة من الشات:</b>\n"
            f"• لتغيير اسم البوت معاك: <code>/set_name سارة</code>\n"
            f"• لتغيير جنس الشخصية: <code>/set_gender female</code> أو <code>male</code>\n"
            f"• لتغيير اللهجة: <code>/set_dialect syrian</code> أو <code>egyptian</code>\n"
            f"• لإعطائه شخصية وتوجيه خاص: <code>/set_prompt خليك دكتور نفسي وبتهزر معايا</code>\n"
            f"• لاستنساخ أسلوب كلامك: <code>/clone_style [الصق فقرة من كلامك هنا]</code>\n"
            f"</blockquote>\n"
            f"👇 <i>أو استخدم أزرار التحكم السريعة أدناه:</i>"
        )

        next_g = "female" if p.gender == "male" else "male"
        g_btn_text = "تحويل إلى (بنت 👧)" if next_g == "female" else "تحويل إلى (ولد 👦)"

        buttons = [
            [{"text": f"🚻 {g_btn_text}", "callback_data": f"act:persona_toggle_gender:{next_g}", "style": "primary"}],
            [{"text": "🗺️ اختيار لهجة الشخصية 🗺️", "callback_data": "menu:persona_dialects", "style": "primary"}],
            [
                {"text": "🔄 إعادة تعيين للافتراضي 🧹", "callback_data": "act:persona_reset", "style": "danger"},
                {"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "primary"},
            ],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_persona_dialects_menu(cls, user_id: int) -> Tuple[str, Dict[str, Any]]:
        text = (
            f"🗺️ <b>اختر اللهجة المفضلة لشخصيتك الخاصة في الخاص:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"اضغط على اللهجة التي تفضل أن يتحدث بها البوت معك في الشات الخاص:"
        )
        dialects = [
            ("🇪🇬 مصرية قاهرية", "egyptian"),
            ("🇸🇾 سورية شامية", "syrian"),
            ("🇸🇦 سعودية بيضاء", "saudi"),
            ("🇮🇶 عراقية أصيلة", "iraqi"),
            ("🇰🇼 كويتية فخمة", "kuwaiti"),
            ("🇦🇪 إماراتية راقية", "emirati"),
            ("🇱🇧 لبنانية رقيقة", "lebanese"),
            ("🇯🇴 أردنية نشمية", "jordanian"),
            ("🇵🇸 فلسطينية دافئة", "palestinian"),
            ("🇲🇦 مغربية بيضاء", "moroccan"),
            ("🇩🇿 جزائرية محبوبة", "algerian"),
            ("🇹🇳 تونسية خفيفة", "tunisian"),
            ("🇱🇾 ليبية أصيلة", "libyan"),
            ("🇸🇩 سودانية شهامة", "sudanese"),
            ("🇾🇪 يمنية كريمة", "yemeni"),
            ("📖 عربية فصحى", "fusha"),
        ]

        buttons = []
        for i in range(0, len(dialects), 2):
            row = []
            for label, code in dialects[i:i+2]:
                row.append({"text": label, "callback_data": f"act:persona_set_dialect:{code}", "style": "primary"})
            buttons.append(row)

        buttons.append([{"text": "🔙 العودة لشخصيتي الخاصة 🎭", "callback_data": "menu:my_persona", "style": "danger"}])
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_my_commands_panel(cls, user_id: int) -> Tuple[str, Dict[str, Any]]:
        """
        Renders the Custom Command Compiler panel for the tenant.
        """
        all_cmds = custom_commands.list_commands(user_id)
        cmd_lines = []
        if all_cmds:
            for cmd_obj in all_cmds:
                trig = cmd_obj.command_trigger
                resp_preview = cmd_obj.response_template[:30] + ("..." if len(cmd_obj.response_template) > 30 else "")
                cmd_lines.append(f"• <code>{trig}</code> ➔ <i>{resp_preview}</i>")
            cmds_text = "\n".join(cmd_lines)
        else:
            cmds_text = "<i>ليس لديك أي أوامر مخصصة بعد.</i>"

        text = (
            f"🪄 <b>مترجم أوامرك الخاصة (Custom Commands Sandbox)</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"يمكنك هنا برمجة كلمات أو أوامر سحرية خاصة بك وحدك، تنفذ ردوداً تحددها أنت:\n\n"
            f"📋 <b>أوامرك النشطة حالياً:</b>\n"
            f"{cmds_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"✍️ <b>طريقة إضافة أمر خاص جديد:</b>\n"
            f"اكتب في الشات:\n"
            f"<code>/add_cmd /أمرك الرد الذي تريده</code>\n\n"
            f"<i>أمثلة:</i>\n"
            f"• <code>/add_cmd /study ذاكر يا بطل وبطل مرقعة عشان الامتحانات!</code>\n"
            f"• <code>/add_cmd صباحو يسعدلي صباحك يا أغلى الناس وجمعة مباركة!</code>\n\n"
            f"🗑️ <b>لحذف أمر معين:</b>\n"
            f"<code>/del_cmd /أمرك</code>"
            f"</blockquote>"
        )
        buttons = [
            [{"text": "🗑️ مسح جميع أوامري ❌", "callback_data": "act:clear_my_cmds", "style": "danger"}],
            [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main", "style": "primary"}],
        ]
        return text, {"inline_keyboard": buttons}

    @classmethod
    async def render_games_panel(cls, user_id: int, user_name: str) -> Tuple[str, Dict[str, Any]]:
        return group_games.render_games_lobby(user_name)


# Global instance
telegram_menu = TelegramMenuEngine()
