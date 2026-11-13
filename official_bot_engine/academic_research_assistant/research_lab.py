"""
Academic Research Assistant & Creative Study Lab for Project Aether-Human (V2.0).
Provides deep document summarization, lecture decomposition, interactive exam generation,
and flashcard creation powered by the load-balanced Gemini model pool.
"""

from __future__ import annotations

import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from aether_human_core.config.llm_router import llm_pool
from cloud_and_resource_guard.file_stream_compressor import file_compressor

logger = logging.getLogger("Aether.ResearchLab")


class LectureSummaryResult(BaseModel):
    title: str
    executive_summary: str
    key_definitions: List[Dict[str, str]]
    core_mechanisms: List[str]
    practical_examples: List[str]
    exam_critical_takeaways: List[str]


class QuizQuestion(BaseModel):
    id: int
    question_text: str
    question_type: str  # MCQ, TRUE_FALSE, ESSAY
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: str


class ExamBankResult(BaseModel):
    exam_title: str
    total_questions: int
    questions: List[QuizQuestion]


class AcademicResearchAssistant:
    """
    Intelligent research, document analysis, and academic study companion.
    """

    async def summarize_document(
        self,
        document_text: str,
        document_name: str = "المحاضرة العلمية",
        detail_level: str = "comprehensive",
    ) -> LectureSummaryResult:
        """
        Decomposes a lengthy academic text or lecture into a structured high-yield study sheet.
        """
        prompt = f"""
أنت مساعد بحثي وأستاذ جامعي موسوعي فائق الذكاء.
المطلوب منك تحليل وتلخيص المحتوى الأكاديمي التالي الخاص بـ: "{document_name}"

نص الوثيقة أو المحاضرة:
{document_text[:35000]}

قم بإنشاء تلخيص أكاديمي احترافي وعميق ومبهر باللغة العربية الفصحى بصيغة JSON حصراً، وفق الهيكل التالي:
{{
  "title": "عنوان موجز وشامل للمحاضرة أو البحث",
  "executive_summary": "ملخص تنفيذي مكثف يشرح الفكرة الجوهرية للبحث بدقة وشمولية",
  "key_definitions": [
    {{"term": "المصطلح 1", "definition": "التعريف العلمي الدقيق والمبسط"}},
    {{"term": "المصطلح 2", "definition": "التعريف العلمي الدقيق والمبسط"}}
  ],
  "core_mechanisms": [
    "شرح الآلية أو النظرية الأولى والخطوات بالتفصيل",
    "شرح الآلية أو النظرية الثانية والخطوات بالتفصيل"
  ],
  "practical_examples": [
    "مثال تطبيقي واقعي أو دراسة حالة تم ذكرها أو يمكن تطبيق الفكرة عليها"
  ],
  "exam_critical_takeaways": [
    "نقاط حرجة ومتوقعة جداً في امتحانات الماجستير والبكالوريوس"
  ]
}}
رد بـ JSON فقط بدون علامات markdown إضافية.
"""
        response_raw = await llm_pool.generate_content(
            prompt=prompt,
            system_instruction="أنت بروفيسور وعالم أكاديمي يقدم مخرجات JSON دقيقة وفائقة الجودة.",
            temperature=0.3,
        )

        try:
            # Clean JSON formatting
            clean_json = response_raw.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            return LectureSummaryResult(
                title=data.get("title", document_name),
                executive_summary=data.get("executive_summary", ""),
                key_definitions=data.get("key_definitions", []),
                core_mechanisms=data.get("core_mechanisms", []),
                practical_examples=data.get("practical_examples", []),
                exam_critical_takeaways=data.get("exam_critical_takeaways", []),
            )
        except Exception as exc:
            logger.error(f"Failed to parse lecture summary JSON: {exc}. Raw: {response_raw[:100]}")
            return LectureSummaryResult(
                title=document_name,
                executive_summary=response_raw[:1500],
                key_definitions=[],
                core_mechanisms=[],
                practical_examples=[],
                exam_critical_takeaways=[],
            )

    async def generate_exam_bank(
        self,
        document_text: str,
        subject_name: str = "المقرر الدراسي",
        num_mcq: int = 5,
        num_true_false: int = 3,
        num_essay: int = 2,
    ) -> ExamBankResult:
        """
        Generates a rigorous exam question bank with multiple-choice, true/false, and conceptual questions.
        """
        prompt = f"""
أنت خبير وضع الاختبارات الجامعية والتقييم الأكاديمي.
بناءً على المحتوى التالي من مقرر: "{subject_name}"

النص الأكاديمي:
{document_text[:35000]}

المطلوب: قم بإنشاء بنك أسئلة متكامل باللغة العربية الفصحى يتضمن:
- {num_mcq} أسئلة اختيار من متعدد (MCQ) مع 4 اختيارات لكل سؤال.
- {num_true_false} أسئلة صح أم خطأ مع بيان السبب.
- {num_essay} أسئلة مقالية عميقة لقياس الفهم التحليلي مع الإجابة النموذجية.

قم بإخراج النتيجة بصيغة JSON صريحة فقط على النحو التالي:
{{
  "exam_title": "اختبار تقييمي شامل في {subject_name}",
  "total_questions": {num_mcq + num_true_false + num_essay},
  "questions": [
    {{
      "id": 1,
      "question_text": "نص السؤال هنا؟",
      "question_type": "MCQ",
      "options": ["أ) الاختيار الأول", "ب) الاختيار الثاني", "ج) الاختيار الثالث", "د) الاختيار الرابع"],
      "correct_answer": "أ) الاختيار الأول",
      "explanation": "شرح علمي مفصل لسبب صحة هذا الاختيار"
    }},
    {{
      "id": 2,
      "question_text": "نص سؤال صح أو خطأ؟",
      "question_type": "TRUE_FALSE",
      "options": ["صح", "خطأ"],
      "correct_answer": "خطأ",
      "explanation": "تصحيح العبارة وبيان العلة العلمية"
    }},
    {{
      "id": 3,
      "question_text": "نص السؤال المقالي العميق؟",
      "question_type": "ESSAY",
      "options": null,
      "correct_answer": "الإجابة النموذجية الكاملة للنقاط الواجب ذكرها",
      "explanation": "معايير التقييم والعمق المطلوب في الإجابة"
    }}
  ]
}}
رد بـ JSON فقط دون أي شروح إضافية.
"""
        response_raw = await llm_pool.generate_content(
            prompt=prompt,
            system_instruction="أنت مستشار أكاديمي خبير في تصميم التقييمات العلمية.",
            temperature=0.4,
        )

        try:
            clean_json = response_raw.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            questions_list = [
                QuizQuestion(
                    id=q.get("id", i + 1),
                    question_text=q.get("question_text", ""),
                    question_type=q.get("question_type", "MCQ"),
                    options=q.get("options"),
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation", ""),
                )
                for i, q in enumerate(data.get("questions", []))
            ]

            return ExamBankResult(
                exam_title=data.get("exam_title", f"اختبار {subject_name}"),
                total_questions=len(questions_list),
                questions=questions_list,
            )
        except Exception as exc:
            logger.error(f"Failed to parse exam bank JSON: {exc}. Raw: {response_raw[:100]}")
            return ExamBankResult(
                exam_title=f"اختبار في {subject_name}",
                total_questions=1,
                questions=[
                    QuizQuestion(
                        id=1,
                        question_text="ما هي أبرز النقاط التي ناقشتها المادة العلمية؟",
                        question_type="ESSAY",
                        correct_answer=response_raw[:1000],
                        explanation="إجابة مستخلصة من المحتوى الأكاديمي.",
                    )
                ],
            )


# Singleton instance
research_assistant = AcademicResearchAssistant()

