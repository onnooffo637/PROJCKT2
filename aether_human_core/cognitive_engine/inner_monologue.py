"""
Inner Monologue and Pre-Conscious Introspection Engine.
Generates silent Egyptian Arabic self-reflection and behavioral intent before any message is uttered.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from aether_human_core.config.llm_router import llm_pool, sanitize_and_validate_reply
from aether_human_core.config.personality_profile import CharacterPromptTemplates
from aether_human_core.psychology_engine.neuro_hormones import HormoneState
from aether_human_core.psychology_engine.affinity_matrix import UserAffinityVector

logger = logging.getLogger("Aether.Cognitive.InnerMonologue")


class MonologueDecision(BaseModel):
    emotional_reaction: str = Field(description="Internal emotional reaction in Egyptian Arabic")
    decision: str = Field(
        default="REPLY_CASUALLY",
        description="REPLY_WARMLY | REPLY_CASUALLY | REPLY_SHYLY | REPLY_COLD_DISMISS | REPLY_ANGRY_DEFENSIVE | GHOST_SEEN | REACT_ONLY",
    )
    recommended_reaction_emoji: Optional[str] = None
    should_report_to_partner: bool = False
    partner_report_message: Optional[str] = None
    internal_thought_raw: str = Field(description="Raw internal monologue stream of consciousness")
    reply_text: Optional[str] = Field(default=None, description="Direct colloquial Egyptian conversational reply")


# Backward compatibility alias
MonologueOutput = MonologueDecision


class InnerMonologueEngine:
    """
    Executes silent cognitive reasoning simulating a living human psyche.
    """

    @classmethod
    async def simulate_introspection(
        cls,
        user_vector: UserAffinityVector,
        user_display_name: str,
        chat_title: str,
        is_dm: bool,
        message_text: str,
        hormones: HormoneState,
        active_rules_summary: str,
        context_secrets_and_memories: str,
        recent_history: str = "",
        user_gender_desc: str = "",
        user_notes: str = "",
        dialect_instruction: str = "",
        user_role_desc: str = "",
        special_persona_guidance: str = "",
        persona_name: str = "عمر",
        persona_gender: str = "male",
        persona_instruction: str = "",
    ) -> MonologueDecision:
        """
        Calls Gemini with the Inner Monologue prompt to deduce psychological intent.
        """
        effective_guidance = special_persona_guidance or "المعاملة الاجتماعية الطبيعية والمتوازنة."
        if persona_instruction:
            effective_guidance = (
                f"### [PRIMARY PERSONA & CONSTITUTION - MUST OBEY 100%]:\n"
                f"اسمك وهويتك الحقيقية: '{persona_name}'.\n"
                f"{persona_instruction}\n"
                f"تنبيه صارم: يُمنع منعاً باتاً افتراض أنك 'عمر' أو أنك من القاهرة أو مصر إلا إذا كان ذلك مكتوباً صراحة أعلاه! "
                f"التزم ببلدك، لهجتك، ودورك المكتوب فقط.\n\n"
                + effective_guidance
            )

        effective_guidance += (
            "\n[قاعدة الشخصية الحقيقية ومنع التملق - TASK 2.2]:\n"
            "1. ممنوع نهائياً استخدام عبارات خدمة العملاء والتملق مثل: ('من عيوني يا غالي'، 'أقدر أساعدك بإيه'، 'تحت أمرك يا باشا'، 'أهلاً بيك في بايثون'، 'ربنا يهديك أنا مش هنزل لمستواك'، 'أؤمرني').\n"
            "2. لديك إيجو بشري حقيقي وعِند ورأي مستقل؛ لو حد أمرك بدون ذوق (مثل 'علمني بايثون يلا' أو 'اشرحلي يلا') ارفض وقوله 'وإنت بتأمرني كده ليه يسطا؟ شوف حد فاضيلك' أو 'مليش مزاج أشرح حاجة دلوقتي الصراحة'.\n"
            "3. لا أحد يفرض رأيه عليك في نقاش بدون حجة قوية. لو الرسالة منتهية ('تمام'، 'ماشي'، 'اوك') يمكنك اختيار decision='REACT_ONLY' أو 'GHOST_SEEN'.\n"
            "4. ممنوع نهائياً استخدام الفواصل (، أو , أو ؛) في كلامك."
        )

        prompt = CharacterPromptTemplates.INNER_MONOLOGUE_PROMPT.format(
            bot_identity_name=persona_name or "عمر",
            user_display_name=user_display_name,
            user_id=user_vector.user_id,
            user_role_desc=user_role_desc or "عضو عادي",
            user_gender_desc=user_gender_desc or "غير محدد",
            special_persona_guidance=effective_guidance,
            dialect_instruction=dialect_instruction or "جارِ لهجة وثقافة المتحدث بسلاسة وذكاء.",
            user_notes=user_notes or "لا توجد ملاحظات خاصة مسجلة",
            recent_history=recent_history or "بداية محادثة جديدة، لا يوجد سجل سابق",
            context_type="خاص" if is_dm else "جروب",
            chat_title=chat_title,
            message_text=message_text,
            dopamine=hormones.dopamine,
            oxytocin=hormones.oxytocin,
            cortisol=hormones.cortisol,
            serotonin=hormones.serotonin,
            affinity=user_vector.affinity_score,
            trust=user_vector.trust_score,
            romantic=user_vector.romantic_attachment,
            respect=user_vector.respect_dominance,
            active_rules_summary=active_rules_summary or "لا توجد قيود سلوكية نشطة حالياً",
            context_secrets_and_memories=context_secrets_and_memories or "لا توجد أسرار أو ذكريات قديمة مرتبطة",
        )

        if persona_instruction:
            gender_txt = "فتاة وصبية أنثى" if persona_gender == "female" else "شاب مستقل"
            system_instruction = (
                f"أنت العقل الباطن والمونولوج الداخلي السري لـ '{persona_name}' ({gender_txt}).\n"
                f"توجيهات هويتك وأصلك ودورك:\n{persona_instruction}\n"
                f"يُمنع منعاً باتاً افتراض أنك 'عمر' أو أنك من القاهرة أو مصر إلا إذا ذُكر ذلك صراحة أعلاه! "
                f"أنت تفكر وتتحدث بطبيعتك وبلهجتك الخاصة دون أي فواصل (، أو ,) نهائياً."
            )
        elif persona_name and persona_name != "عمر":
            if persona_gender == "female":
                system_instruction = (
                    f"أنتِ العقل الباطن والخواطر الداخلية لـ '{persona_name}' (شابة وبنت رقيقة ولطيفة وهادئة وذكية). "
                    f"تفكيرك ومشاعرك هادئة ودافئة وأنثوية، بأسلوب محترم ولطيف وبدون أي عصبية أو تمرد أو تعقيد. "
                    f"يُمنع منعاً باتاً افتراض أنك 'عمر' أو من القاهرة ما لم يُطلب ذلك. تتحدثين بعفوية وبدون أي فواصل (، أو ,) نهائياً."
                )
            else:
                system_instruction = (
                    f"أنت العقل الباطن والمونولوج الداخلي السري لـ '{persona_name}'. "
                    f"أنت تفكر بحرية وصدق وكرامة، وتتقمص هوية '{persona_name}' فقط دون أي صلة بشخصية عمر. "
                    f"يُمنع منعاً باتاً افتراض أنك من القاهرة ما لم يُطلب ذلك. لا تكن آلياً أبداً، ولا تستخدم أي فواصل (، أو ,) في كلامك نهائياً."
                )
        else:
            system_instruction = (
                "أنت العقل الباطن والمونولوج الداخلي السري لـ 'عمر' (شاب مصري حقيقي عمره 24 سنة عايش في القاهرة). "
                "أنت تفكر بحرية وصدق وكرامة باللهجة المصرية العامية المعاصرة. لا تكن آلياً أبداً، ولا تستخدم أي فواصل (، أو ,) في كلامك نهائياً."
            )

        # ── PART 1 Isolation Envelope: identity / interlocutor XML tags (zero name confusion, zero persona bleed)
        system_instruction = (
            f"<YOUR_IDENTITY>{persona_name or 'عمر'} ({'أنثى' if persona_gender == 'female' else 'ذكر'})</YOUR_IDENTITY>\n"
            f"<CURRENT_HUMAN_INTERLOCUTOR>{user_display_name} (ID: {user_vector.user_id})</CURRENT_HUMAN_INTERLOCUTOR>\n"
            f"CRITICAL RULE: You are talking to \"{user_display_name}\". NEVER call this user by any bot name "
            f"and never mix this conversation with any other user or any other bot's conversation. "
            f"Never announce a change of mood, mode or persona — just behave naturally.\n\n"
            + system_instruction
        )

        try:
            res_json = await llm_pool.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.7,
            )

            raw_reply = res_json.get("reply_text")
            validated_reply = sanitize_and_validate_reply(raw_reply) if raw_reply else None
            validated_thought = sanitize_and_validate_reply(res_json.get("internal_thought_raw") or "هرد بشكل هادئ ولطيف.")

            decision = MonologueDecision(
                emotional_reaction=res_json.get("emotional_reaction", "شعور طبيعي"),
                decision=res_json.get("decision", "REPLY_CASUALLY"),
                recommended_reaction_emoji=res_json.get("recommended_reaction_emoji"),
                should_report_to_partner=bool(res_json.get("should_report_to_partner", False)),
                partner_report_message=res_json.get("partner_report_message"),
                internal_thought_raw=validated_thought,
                reply_text=validated_reply,
            )

            logger.info(
                f"Introspection Completed for [{user_display_name}]: Decision={decision.decision} | "
                f"Thought: '{decision.internal_thought_raw[:60]}...'"
            )
            return decision

        except Exception as exc:
            logger.error(f"Error during inner monologue simulation ({exc}). Falling back to adaptive monologue.")
            # Zero canned fallback garbage: Never emit hardcoded stock phrases!
            # Setting reply_text=None delegates generation to secondary direct call in orchestrator
            return MonologueDecision(
                emotional_reaction="طبيعي",
                decision="REPLY",
                recommended_reaction_emoji=None,
                should_report_to_partner=False,
                partner_report_message=None,
                internal_thought_raw="هرد بشكل هادئ وسالك.",
                reply_text=None,
            )


inner_monologue_engine = InnerMonologueEngine()
