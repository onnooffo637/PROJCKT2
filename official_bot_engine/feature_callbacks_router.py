"""
Feature Callbacks Router for V3.0, V4.0 & V5.0 Features.
Handles callbacks for Memory Vault, Time Capsule, Multi-Persona Debate, Voice Hub, and King Mod Client.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

from security_and_rbac.rbac_ui_guard import rbac_guard
from official_bot_engine.keyboards_builder import keyboards_builder
from multi_tenant_sandbox.multi_persona_debate import MultiPersonaDebateEngine
from cloud_and_resource_guard.tunnel_manager import tunnel_manager

logger = logging.getLogger("Aether.BotEngine.CallbacksRouter")


class FeatureCallbacksRouter:
    """
    Dispatches specialized menu callbacks.
    """

    @classmethod
    async def handle_feature_callback(
        cls, callback_data: str, user_id: int, user_name: str
    ) -> Optional[Tuple[str, Dict[str, Any], Optional[str], Optional[str]]]:
        """
        Returns (text, markup, toast_alert, trigger) or None if not handled by this router.
        """
        # ==========================================
        # 1. Memory Vault & Time Capsule
        # ==========================================
        if callback_data == "menu:my_vault":
            text = (
                f"🧠 <b>خزنة ذاكرتي المحلية وكبسولة الزمن</b> ⏳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"مرحباً بك يا <b>{user_name}</b> في مساحتك التذكارية الخاصة:\n\n"
                f"• 📦 <b>كبسولة الزمن (Time Capsule):</b> اكتب رسالة أو وعداً لنفسك، وحدد موعداً "
                f"ليقوم عمر بحفظها في كبسولة مشفرة وتذكيرك بها في الوقت المحدد تماماً!\n"
                f"• 🧹 <b>إدارة الذاكرة:</b> يمكنك فحص ومسح ما يتذكره عمر عنك في أي وقت بضغطة واحدة.\n\n"
                f"<i>💡 لإنشاء كبسولة زمن من الشات مباشرة:</i>\n"
                f"<code>/capsule 30d وعد لنفسي هكون اتعلمت تكنولوجيا جديدة</code>"
            )
            return text, keyboards_builder.build_vault_buttons(), None, None

        elif callback_data == "act:capsule_create":
            text = (
                f"💌 <b>إنشاء كبسولة زمن جديدة (Time Capsule)</b> ⏳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"اكتب في الشات الأمر التالي متبوعاً بالمدة ورسالتك:\n\n"
                f"<code>/capsule &lt;المدة&gt; &lt;رسالتك&gt;</code>\n\n"
                f"<b>أمثلة:</b>\n"
                f"• <code>/capsule 7d لا تنسى مراجعة مشروع التخرج يا بطل</code>\n"
                f"• <code>/capsule 30d هدف الشهر: الانتظام في الجيم يومياً</code>\n"
                f"• <code>/capsule 365d رسالة لنفسي بعد سنة كاملة</code>\n\n"
                f"<i>سيقوم عمر بقفل الكبسولة وإرسالها لك في اليوم واللحظة المحددة!</i>"
            )
            return text, {"inline_keyboard": [[{"text": "🔙 العودة للخزنة 🧠", "callback_data": "menu:my_vault"}]]}, None, None

        elif callback_data == "act:capsule_list":
            text = (
                f"📦 <b>كبسولات الزمن الخاصة بك</b> ⏳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ ليس لديك كبسولات زمن قيد الانتظار حالياً.\n"
                f"استخدم الزر لإنشاء كبسولتك الأولى!"
            )
            return text, {"inline_keyboard": [[{"text": "➕ إنشاء كبسولة الآن 💌", "callback_data": "act:capsule_create"}], [{"text": "🔙 الخزنة 🧠", "callback_data": "menu:my_vault"}]]}, None, None

        elif callback_data == "act:vault_clear":
            return (
                "🧹 <b>تم مسح وتنظيف ذاكرة الحوار المؤقتة الخاصة بك بنجاح!</b> 🧼\nعمر الآن يتعامل معك بسجل ذهني نظيف تماماً.",
                {"inline_keyboard": [[{"text": "🔙 العودة للخزنة 🧠", "callback_data": "menu:my_vault"}]]},
                "تم مسح الذاكرة بنجاح!",
                None,
            )

        # ==========================================
        # 2. Multi-Persona Debate Room
        # ==========================================
        elif callback_data == "menu:debate":
            text = (
                f"👥 <b>غرفة النقاش والمناظرة المزدوجة (Multi-Persona Debate)</b> 🎭\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"في هذه الغرفة، يقوم عمر باستدعاء شخصيتين في نفس الوقت ليتحاورا أمامك بموضوعية ومرح:\n\n"
                f"• 🧑‍💼 <b>عمر التحليلي (السوري الهادئ):</b> يتحدث بالأرقام والمنطق والهدوء.\n"
                f"• 🤠 <b>عمر المشاغب (المصري الساخر):</b> يطرح أمثلة الشارع والواقع بخفة دم.\n\n"
                f"<i>💡 لبدء مناظرة حول أي موضوع من الشات مباشرة:</i>\n"
                f"<code>/debate الذكاء الاصطناعي ومستقبل المبرمجين</code>\n\n"
                f"👇 <i>أو اختر أحد المواضيع الساخنة أدناه:</i>"
            )
            return text, keyboards_builder.build_debate_buttons(), None, None

        elif callback_data in ("act:debate_ai", "act:debate_philosophy", "act:debate_sports"):
            topic_map = {
                "act:debate_ai": "مستقبل الذكاء الاصطناعي وهل سيحل محل البشر؟",
                "act:debate_philosophy": "هل السعادة في راحة البال أم في تحقيق الطموحات الصعبة؟",
                "act:debate_sports": "مقارنة تكتيكية تاريخية بين الكرة الهجومية والدفاعية",
            }
            topic = topic_map.get(callback_data, "النجاح في الحياة")
            turns = await MultiPersonaDebateEngine.generate_debate(topic=topic, turns=3)

            rendered = []
            for t in turns:
                rendered.append(f"<b>{t.get('speaker', 'عمر')}:</b>\n{t.get('text', '')}\n")

            debate_text = (
                f"👥 <b>مناظرة حية: {topic}</b> 🎭\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                + "\n".join(rendered)
                + "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>ما رأيك في وجهات النظر المطروحة يا {user_name}؟</i>"
            )
            return debate_text, keyboards_builder.build_debate_buttons(), "تم توليد المناظرة بنجاح!", None

        # ==========================================
        # 3. Voice & Call Hub
        # ==========================================
        elif callback_data == "menu:voice_calls":
            text = (
                f"📞 <b>مركز الصوتيات والمكالمات الذكية (Voice & Call Hub)</b> 🎙️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• 🎙️ <b>الصوت الطبيعي:</b> تسجيلات صوتية واقعية باللهجة السورية والمصرية بنقاء كامل.\n"
                f"• ⏰ <b>المنبه البشري (Alarm Call):</b> جدول اتصال أو رسالة صوتية لإيقاظك أو تذكيرك بموعد هام.\n\n"
                f"<i>💡 لطلب منبه بشري من الشات:</i>\n"
                f"<code>/alarm 07:30 اصحى يا بطل الامتحان الصبح</code>"
            )
            return text, keyboards_builder.build_voice_calls_buttons(), None, None

        elif callback_data == "act:alarm_request":
            text = (
                f"⏰ <b>طلب منبه بشري ومكالمة صوتية من عمر</b> 📞\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"اكتب في الشات الأمر التالي بالوقت والسبب:\n\n"
                f"<code>/alarm &lt;الوقت بالساعة:الدقيقة&gt; &lt;السبب&gt;</code>\n\n"
                f"<b>مثال:</b>\n"
                f"<code>/alarm 08:00 صباح الخير عندي انترفيو مهم</code>\n\n"
                f"<i>سيقوم عمر بإرسال فويس منبه حماسي ومبهج لعيونك في الموعد المحدد!</i>"
            )
            return text, {"inline_keyboard": [[{"text": "🔙 مركز الصوتيات 📞", "callback_data": "menu:voice_calls"}]]}, None, None

        # ==========================================
        # 4. King Exclusive: AetherGram Mod Client
        # ==========================================
        elif callback_data == "menu:aethergram":
            if not rbac_guard.is_the_king(user_id):
                return "⛔ عذراً يا غالي، هذا التبويب مخصص للملك فقط!", {"inline_keyboard": [[{"text": "🔙 الرئيسية 🏠", "callback_data": "menu:main"}]]}, "⛔ وصول مرفوض", None

            mod_url = f"{tunnel_manager.get_webapp_url()}#aethergram"
            text = (
                f"📱 <b>تطبيق تليجرام المعدل الخارق (Embedded AetherGram Mod Client)</b> 🌐\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 <b>واجهة الملك الخاصة:</b>\n"
                f"• 👁️ <b>وضع الشبح الكامل (Ghost Mode):</b> قراءة المحادثات والريكوردات بدون إرسال Seen.\n"
                f"• 🗑️ <b>رصد المحذوفات والمعدلات:</b> مشاهدة الرسائل المحذوفة والمعدلة فورياً داخل الشات.\n"
                f"• 🤖 <b>التبديل بين الحسابات:</b> الدخول في حساب اليوزربوت، أو البوت الأساسي، أو بوتات المصنع.\n"
                f"• ✍️ <b>التحكم الحي والرد اليدوي:</b> إرسال رسائل والتدخل اليدوي أو تفعيل الذكاء الاصطناعي.\n\n"
                f"👇 <i>اضغط على الزر لفتح واجهة تليجرام المعدل داخل التطبيق المصغر:</i>"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "🚀 فتح تليجرام المعدل الخارق (AetherGram) 📱", "web_app": {"url": mod_url}}],
                    [{"text": "🔙 العودة للرئيسية 🏠", "callback_data": "menu:main"}],
                ]
            }
            return text, markup, None, None

        return None


feature_router = FeatureCallbacksRouter()
feature_callbacks_router = feature_router

__all__ = ["FeatureCallbacksRouter", "feature_router", "feature_callbacks_router"]

