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
        "- secondary_categories\n"
        "- confidence\n"
        "- reason\n\n"
        "Strict rules:\n"
        "1) primary_category must be exactly one allowed category.\n"
        "2) secondary_categories must be an array and may be empty.\n"
        "3) secondary_categories values must be only allowed categories.\n"
        "4) confidence must be a number between 0 and 1.\n"
        "5) reason must be concise (1-2 sentences).\n"
        "6) Do not include any extra keys.\n\n"
        "Output JSON template:\n"
        '{"article_id": 1, "primary_category": "AI", "secondary_categories": [], '
        '"confidence": 0.75, "reason": "Brief reason."}\n\n'
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
        "Required keys only: article_id, primary_category, secondary_categories, confidence, reason\n"
        "Do not include extra keys.\n"
        "If unsure, set primary_category to Other and secondary_categories to [].\n\n"
        "Target format:\n"
        '{"article_id": 1, "primary_category": "Other", "secondary_categories": [], '
        '"confidence": 0.5, "reason": "Brief reason."}\n\n'
        f"Allowed categories: {categories_text}\n"
        f"Article:\n{json.dumps(article.model_dump(), ensure_ascii=True, indent=2)}\n"
        f"Validation error summary: {compact_error}\n"
        "Now output the corrected JSON object only."
    )
