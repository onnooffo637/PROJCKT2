"""
Multi-Persona Debate & Collaborative Dialogue Engine (Project Aether-Human V3.0 & V4.0)
Generates back-and-forth intellectual debates between two personas
to explain lectures, dissect philosophical questions, or entertain.
Includes Theatrical Staging and Final Synthesized Verdict.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from aether_human_core.config.llm_router import llm_pool

logger = logging.getLogger("Aether.MultiTenant.PersonaDebate")


class DebateResult(list):
    """
    Subclasses list so existing code treating the result as List[Dict[str, Any]]
    continues to work flawlessly, while also providing .transcript, .verdict, .topic,
    and dict-like access.
    """
    def __init__(self, transcript: List[Dict[str, Any]], verdict: str, topic: str):
        super().__init__(transcript)
        self.transcript = transcript
        self.verdict = verdict
        self.topic = topic

    def get(self, key: str, default: Any = None) -> Any:
        if key == "transcript":
            return self.transcript
        if key == "verdict":
            return self.verdict
        if key == "topic":
            return self.topic
        return default

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item == "transcript":
                return self.transcript
            if item == "verdict":
                return self.verdict
            if item == "topic":
                return self.topic
        return super().__getitem__(item)


class MultiPersonaDebateEngine:
    """
    Simulates a vibrant debate between two complementary personas with theatrical staging.
    """

    @classmethod
    async def generate_debate(
        cls,
        topic: str,
        persona_a_name: str = "عمر (المتفائل العبقري)",
        persona_b_name: str = "سارة (الواقعية الساخرة)",
        turns: int = 4,
        rounds: int = 2,
        **kwargs,
    ) -> DebateResult:
        """
        Generates a structured dialogue debate on the chosen topic with a final verdict.
        Accepts rounds (default 2), persona_a_name, persona_b_name, and kwargs safely.
        """
        effective_turns = kwargs.get("rounds", rounds) if rounds is not None else turns
        if kwargs.get("turns") is not None:
            effective_turns = kwargs["turns"]
        effective_turns = max(1, min(int(effective_turns), 5))

        system_instruction = (
            f"أنت مخرج مسرحي حواري عبقري. المطلوب توليد مناظرة سريعة ومشوقة جداً بين شخصيتين حول الموضوع التالي:\n"
            f"الموضوع: '{topic}'\n\n"
            f"الطرف الأول: {persona_a_name} (متحمس، متفائل، يقدم حجج إيجابية بذكاء، أسلوب عفوي واقعي بدون أي فواصل).\n"
            f"الطرف الثاني: {persona_b_name} (واقعي، ساخر، يناقش بحدة وخفة دم، يطرح أسئلة صعبة بدون أي فواصل).\n\n"
            f"القواعد الصارمة:\n"
            f"1. اكتب {effective_turns} جولات سريعة وممتعة (كل جولة تبدأ برد الطرف الأول ثم تعقيب الطرف الثاني).\n"
            f"2. ممنوع استخدام الفواصل نهائياً (احذف علامة ، و , من الحوار لتكون واقعية كالمحادثة السريعة).\n"
            f"3. في نهاية الحوار تماماً، أضف سطراً منفصلاً يبدأ بـ 'الحكم النهائي:' يحتوي خلاصة عادلة وحكيمة بنبرة ذكية تجمع بين وجهتي النظر.\n"
            f"4. التنسيق الدقيق المطلوب:\n"
            f"{persona_a_name}: [الكلام هنا]\n"
            f"{persona_b_name}: [الكلام هنا]\n"
            f"الحكم النهائي: [الخلاصة هنا]"
        )

        try:
            response = await llm_pool.generate_text(
                system_instruction=system_instruction,
                prompt=f"ابدأ المناظرة الآن بين {persona_a_name} و {persona_b_name} حول: {topic}",
                max_tokens=1200,
                temperature=0.85,
            )

            debate_turns: List[Dict[str, Any]] = []
            verdict = ""
            lines = response.strip().split("\n")
            
            for line in lines:
                line = line.strip().replace("**", "").replace("*", "")
                if not line:
                    continue
                
                # Check for final verdict
                if line.startswith("الحكم النهائي:") or line.startswith("الخلاصة:") or line.startswith("الحكم:"):
                    parts = line.split(":", 1)
                    verdict = parts[1].strip().replace("،", "").replace(",", "").replace("**", "")
                    continue

                if ":" in line or "：" in line:
                    parts = line.split(":", 1) if ":" in line else line.split("：", 1)
                    speaker_raw = parts[0].strip().replace("**", "")
                    text_raw = parts[1].strip().replace("،", "").replace(",", "").replace("**", "")
                    if not text_raw or text_raw == "**":
                        continue

                    # Strict alternating turns: Even = Omar (right), Odd = Sarah (left)
                    is_turn_omar = (len(debate_turns) % 2 == 0)
                    speaker = "عمر" if is_turn_omar else "سارة"
                    side = "right" if is_turn_omar else "left"
                    avatar = "🧔🏻‍♂️" if is_turn_omar else "👩🏻‍💼"

                    debate_turns.append({
                        "speaker": speaker,
                        "text": text_raw,
                        "side": side,
                        "avatar": avatar,
                    })
                else:
                    if debate_turns:
                        cleaned_line = line.replace("،", "").replace(",", "").replace("**", "").strip()
                        if cleaned_line and cleaned_line != "**":
                            debate_turns[-1]["text"] += f" {cleaned_line}"

            if not verdict:
                verdict = f"كلا المنظورين يعكس جانباً هاماً من واقع {topic} والتوازن بين الحماس والواقعية هو مفتاح الحكمة دائماً."

            logger.info(f"Generated {len(debate_turns)} debate turns and verdict for topic: '{topic}'")
            return DebateResult(transcript=debate_turns, verdict=verdict, topic=topic)

        except Exception as exc:
            logger.error(f"Failed to generate persona debate: {exc}")
            fallback_turns = [
                {
                    "speaker": "عمر",
                    "text": f"الموضوع ده محتاج نظرة تفاؤلية ونشوف الفرص الكبيرة في {topic} بدون خوف",
                    "side": "right",
                    "avatar": "🧔🏻‍♂️"
                },
                {
                    "speaker": "سارة",
                    "text": f"فرص إيه يا عم خليك واقعي وشوف التحديات والمشاكل العملية الأول بدل الكلام الوردي ده",
                    "side": "left",
                    "avatar": "👩🏻‍💼"
                },
            ]
            fallback_verdict = f"النجاح في {topic} يتطلب حماس عمر وانتباه سارة للتفاصيل الصعبة."
            return DebateResult(transcript=fallback_turns, verdict=fallback_verdict, topic=topic)


persona_debate_engine = MultiPersonaDebateEngine()
MultiPersonaDebater = MultiPersonaDebateEngine
