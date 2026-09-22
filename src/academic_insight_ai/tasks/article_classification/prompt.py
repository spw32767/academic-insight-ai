from __future__ import annotations

import json

from academic_insight_ai.tasks.article_classification.config import ALLOWED_CATEGORIES
from academic_insight_ai.tasks.article_classification.schema import ArticleInput


def build_prompt(article: ArticleInput) -> str:
    categories_text = ", ".join(ALLOWED_CATEGORIES)
    return (
        "You are an academic article classifier. "
        "Return EXACTLY ONE JSON object and NOTHING else. "
        "Do not output markdown. Do not output code fences. Do not output explanation text.\n\n"
        "You must use ONLY these keys exactly as written:\n"
        "- article_id\n"
        "- primary_category\n"
        "- confidence\n"
        "- reason\n\n"
        "Strict rules:\n"
        "1) primary_category must be exactly one allowed category.\n"
        "2) confidence must be exactly High, Medium, or Low.\n"
        "3) Classify the primary contribution, using the abstract as primary evidence.\n"
        "4) Formal verification and model checking use Theoretical Computer Science.\n"
        "5) New AI methods use AI Algorithms; applications of established AI use Applied AI.\n"
        "6) IoT protocol/security work uses Networks; device/sensor work uses Computer Engineering.\n"
        "7) reason must be concise (1-2 sentences).\n"
        "8) Do not include any extra keys.\n\n"
        "Output JSON template:\n"
        '{"article_id": 1, "primary_category": "AI Algorithms and Intelligent Systems", '
        '"confidence": "High", "reason": "Brief reason."}\n\n'
        f"Allowed categories: {categories_text}\n\n"
        f"Article:\n{json.dumps(article.model_dump(), ensure_ascii=True, indent=2)}"
    )


def build_correction_prompt(article: ArticleInput, validation_error: str) -> str:
    categories_text = ", ".join(ALLOWED_CATEGORIES)
    compact_error = validation_error.splitlines()[0][:220]
    return (
        "Your previous output is invalid. Correct it now.\n"
        "Return EXACTLY ONE corrected JSON object and NOTHING else.\n"
        "No markdown, no code fences, no explanation.\n\n"
        "Required keys only: article_id, primary_category, confidence, reason\n"
        "Do not include extra keys.\n"
        "If evidence is weak, choose the closest allowed category and set confidence to Low.\n\n"
        "Target format:\n"
        '{"article_id": 1, "primary_category": "Theoretical Computer Science", '
        '"confidence": "Low", "reason": "Brief reason."}\n\n'
        f"Allowed categories: {categories_text}\n"
        f"Article:\n{json.dumps(article.model_dump(), ensure_ascii=True, indent=2)}\n"
        f"Validation error summary: {compact_error}\n"
        "Now output the corrected JSON object only."
    )
