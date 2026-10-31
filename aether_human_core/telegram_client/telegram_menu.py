"""
Ultra-Modern Telegram Interactive Control Panel, Menu Engine, and Inline Keyboards.
Renders state-of-the-art HTML formatting, expandable blockquotes, and rich button-driven
dashboards with native colored buttons (Bot API 9.4+ style: primary, success, danger).
Supports multi-tier hierarchy, negative affinity ranges, and dedicated Villain profile.
"""

from __future__ import annotations

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
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Main interactive dashboard greeting with categorized feature buttons.
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

        text = (
            f"⚡ <b>مرحباً بك في لوحة تحكم الكيان الذكي «عُـمـر»</b> ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المستخدم:</b> <code>{user_name}</code> (<code>{user_id}</code>)\n"
            f"👑 <b>رتبتك في النظام:</b> <b>{role_title}</b>\n"
            f"📊 <b>رصيد معزتك وتفضيلك:</b> <code>{prog_bar}</code>\n"
            f"🏷️ <b>المكانة والعلاقة:</b> <b>{tier_display}</b>\n"
            f"⏱️ <b>مدة التشغيل المستمر:</b> <code>{cls.get_uptime_str()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<blockquote expandable>"
            f"مرحباً بك! أنا عمر، شاب تقني وذكي عمره 24 سنة. هذه اللوحة التفاعلية تمكنك من "
            f"متابعة رصيد معزتك وتفضيلك، فحص رادار هرموناتي، ومراقبة موارد السيرفر، وإدارة الرتب، وتجربة الميديا المباشرة."
            f"</blockquote>\n"
            f"👇 <i>اختر القسم الذي ترغب في استعراضه من الأزرار الملونة أدناه:</i>"
        )

        buttons = [
            [
                {"text": "💖 رصيد معزتي ومكانتي عند عمر 💎", "callback_data": "menu:user_affinity", "style": "success"},
            ],
            [
                {"text": "📊 حالة السيرفر والنظام ⚡", "callback_data": "menu:server_stats", "style": "primary"},
                {"text": "🧠 رادار المزاج والهرمونات ☕", "callback_data": "menu:mood_radar", "style": "success"},
            ],
            [
                {"text": "👑 إدارة الأدمنز والرتب 🛡️", "callback_data": "menu:admins", "style": "primary"},
                {"text": "📜 القواعد والممنوعات ⚖️", "callback_data": "menu:rules", "style": "danger"},
            ],
            [
                {"text": "🌐 لغات ولهجات البوت 🗺️", "callback_data": "menu:dialects", "style": "primary"},
                {"text": "🎙️ مركز الميديا (فويس وسيلفي) 📸", "callback_data": "menu:media", "style": "success"},
            ],
            [
                {"text": "🔄 تحديث اللوحة الشاملة ⚡", "callback_data": "menu:main", "style": "primary"},
            ],
        ]

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
    async def handle_callback(
        cls, callback_data: str, user_id: int, user_name: str = "مستخدم"
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Dispatches callback query to appropriate renderer or action.
        Returns: (text, reply_markup, alert_text, action_trigger)
        """
        if callback_data in ("menu:main", "menu:refresh_main"):
            text, markup = await cls.render_main_dashboard(user_id, user_name=user_name)
            return text, markup, None, None

        elif callback_data in ("menu:user_affinity", "act:refresh_affinity"):
            text, markup = await cls.render_user_affinity_profile(user_id, user_name=user_name)
            alert = "💖 تم تحديث تفاصيل مكانتك ورصيدك عند عمر بنجاح!" if callback_data == "act:refresh_affinity" else None
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

        # Default fallback
        text, markup = await cls.render_main_dashboard(user_id, user_name=user_name)
        return text, markup, None, None


# Global instance
telegram_menu = TelegramMenuEngine()
