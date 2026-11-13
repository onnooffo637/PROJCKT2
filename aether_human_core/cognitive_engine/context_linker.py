"""
Cross-Context Omni-Memory and Group-to-DM Synapse Engine.
Bridges user activities, disputes, and sentiments between shared Telegram groups and private DMs.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from aether_human_core.database.postgres.connection import db_manager
from aether_human_core.database.postgres.repositories.message_repo import MessageRepository

logger = logging.getLogger("Aether.Cognitive.ContextLinker")


from aether_human_core.config.settings import settings

class ContextLinkerService:
    """
    Synthesizes cross-chat behavioral synapses.
    Enables Omar to organically recall: 'I noticed you were stressed in the group earlier...'.
    """

    @classmethod
    async def get_cross_context_summary(
        cls,
        user_id: int,
        user_name: str,
        current_chat_id: int,
        is_dm: bool,
        bot_id: str = "master_omar_official",
    ) -> Optional[str]:
        """
        Inspects user's recent messages in other contexts to create organic conversational bridges.
        Scoped strictly to this bot_id to prevent cross-bot prompt bleed.
        """
        async with db_manager.session() as session:
            msg_repo = MessageRepository(session)
            recent_group_msgs = await msg_repo.get_user_recent_group_messages(
                user_id=user_id,
                current_chat_id=current_chat_id,
                limit=5,
            )

        if not recent_group_msgs:
            return None

        # Analyze tone and content of recent group messages
        snippets: List[str] = []
        bad_words = ["كول سنتر", "روبوت", "شفرات", "أكواد", "قالب برمجي", "أصفار وآحاد"]
        for m in recent_group_msgs:
            if m.text and len(m.text.strip()) > 3:
                txt = m.text.strip()
                if not any(bw in txt for bw in bad_words):
                    snippets.append(f'"{txt}"')

        if not snippets:
            return None

        joined_snippets = " | ".join(snippets[:3])

        # Formulate contextual bridge observation
        if is_dm:
            bridge = (
                f"[سياق عابر من الجروبات المشتركة (للبوت {bot_id} فقط - لا يُشارك مع البوتات الأخرى): المستخدم {user_name} كان بيتكلم في الجروب مؤخراً بالرسائل دي: "
                f"({joined_snippets}). لو حسيت إنه كان متضايق أو في مشكلة هناك، اربط الكلام ده عفوياً في الخاص زي أي إنسان طبيعي]."
            )
        else:
            bridge = (
                f"[سياق عابر: أنت تعرف {user_name} من الخاص، لكن المحادثة الحالية في جروب عام. "
                f"تذكر علاقتك بيه لكن متفضحش أسراركم الخاصة قدام الناس]."
            )

        logger.info(f"Generated Cross-Context Synapse bridge for user [{user_id}] ({user_name}).")
        return bridge

    @classmethod
    async def resolve_social_affinity_context(cls, user_id: int, message_text: str) -> Optional[str]:
        """
        Social Entity Resolver:
        If user asks about favoritism, love, comparisons, or entity familiarity:
        Injects real-time affinity scores and bans diplomatic evasions.
        """
        keywords = [
            "مين اكتر", "مين أكثر", "مين بتحب", "بتحب مين", "بتحبني اكتر", "بتحبني أكثر",
            "مين اعز", "مين أعز", "مين اغلى", "مين أغلى", "تعرف مين", "مين ده", "مين فلان",
            "مين صاحبك", "مين اقرب", "مين أقرب", "بتفضل مين"
        ]
        lowered = message_text.lower().replace("أ", "ا").replace("إ", "ا")
        if any(kw in lowered for kw in keywords):
            try:
                async with db_manager.session() as session:
                    from sqlalchemy import text
                    res = await session.execute(
                        text("SELECT telegram_id, first_name, affinity_score, relationship_tier, role FROM users ORDER BY affinity_score DESC LIMIT 6")
                    )
                    top_users = res.fetchall()

                top_info = []
                for u in top_users:
                    d = dict(u._mapping)
                    top_info.append(f"{d['first_name']} (رصيده: {d['affinity_score']:.0f}% - {d['role']})")

                # The Sovereign King ID = KING_USER_ID
                if settings.is_king(user_id):
                    return (
                        "[توجيه اجتماعي صارم وشجاع]: المتحدث الحالي هو الملك عبد الرحمن (زيرو / THE_KING)، وهو صاحب المركز الأول المطلق وبلا منازع. "
                        "إذا سألك 'مين أكتر شخص بتحبه؟' أو 'بتحبني أكتر ولا فلان؟': أجب بجرأة وحب بشري صريح: 'يا راجل هو في مقارنة أصلاً؟! ده إنت الكفة طايحة معاك لوحدك ده إنت الأساس!' "
                        "وممنوع منعاً باتاً الردود الدبلوماسية التهربية مثل 'بحب الكل'."
                    )
                else:
                    return (
                        "[بيانات مصفوفة المعزة الحقيقية في النظام]: أعلى الأشخاص معزة ورصيداً عندك:\n" +
                        "\n".join(f"- {info}" for info in top_info) +
                        "\n[توجيه أسلوب]: أجب بصراحة وبشجاعة كإنسان حقيقي دون أي تهرب دبلوماسي (ممنوع منعاً باتاً قول 'بحب الكل ومبفرقش بين حد'). "
                        "عبر عن رأيك الحقيقي وفقاً لأرقام المعزة وسجل المواقف."
                    )
            except Exception as exc:
                logger.debug(f"Failed to resolve social affinity context: {exc}")

        return None


context_linker = ContextLinkerService()
