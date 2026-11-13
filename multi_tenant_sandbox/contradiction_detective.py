"""
Contradiction Detective & Semantic Discrepancy Radar (Project Aether-Human V3.0)
Compares current user claims with historical memory to playfully catch
and call out contradictions and factual inconsistencies.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from aether_human_core.config.llm_router import llm_pool

logger = logging.getLogger("Aether.MultiTenant.ContradictionDetective")


class ContradictionDetective:
    """
    Scans conversation context for contradictions with long-term episodic facts.
    """

    @classmethod
    async def evaluate_contradiction(
        cls,
        user_name: str,
        current_message: str,
        recent_memory_facts: List[str],
    ) -> Optional[str]:
        """
        Returns a playful teasing callout if a clear contradiction is detected.
        """
        if not recent_memory_facts or len(current_message.strip()) < 8:
            return None

        facts_block = "\n".join(f"- {fact}" for fact in recent_memory_facts[:8])

        system_instruction = (
            "أنت رادار كشف التناقضات في محادثة بشرية. مهمتك قراءة ما قاله المستخدم الآن ومقارنته بما نعرفه عنه من حقائق سابقة.\n"
            "إذا كان كلامه الحالي يناقض تماماً حقيقة سابقة (مثل: قال إنه لا يدخن والآن يقول إنه يدخن، أو قال إنه في مصر والآن يقول إنه لم يسافر إليها أبداً):\n"
            "اكتب تعليقاً ساخراً وعفوياً كصديق يمسك صديقه متلبساً بالتناقض (بلهجة مصرية/سورية ذكية وخفيفة الدم مع إيموجي 😉).\n"
            "إذا لم يكن هناك أي تناقض، اكتب كلمة واحدة فقط: NO_CONTRADICTION"
        )

        prompt = (
            f"حقائق سابقة مسجلة عن {user_name}:\n{facts_block}\n\n"
            f"ما قاله {user_name} الآن: '{current_message}'\n\n"
            f"هل هناك تناقض؟"
        )

        try:
            result = await llm_pool.generate_text(
                system_instruction=system_instruction,
                prompt=prompt,
                max_tokens=150,
                temperature=0.3,
            )
            clean_res = result.strip()
            if "NO_CONTRADICTION" in clean_res:
                return None

            logger.info(f"🕵️ Contradiction caught for [{user_name}]: '{clean_res}'")
            return clean_res

        except Exception as exc:
            logger.debug(f"Contradiction detection check error: {exc}")
            return None


contradiction_detective = ContradictionDetective()

