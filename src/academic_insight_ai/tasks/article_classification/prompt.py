from __future__ import annotations

import json

from academic_insight_ai.tasks.article_classification.config import ALLOWED_CATEGORIES
from academic_insight_ai.tasks.article_classification.schema import ArticleInput


def build_prompt(article: ArticleInput) -> str:
    categories_text = ", ".join(ALLOWED_CATEGORIES)
    return (
        "You are an academic article classifier. "
        "Return ONLY one JSON object with these keys: "
        "article_id, primary_category, secondary_categories, confidence, reason. "
        "Rules: primary_category must be exactly one of the allowed categories. "
        "secondary_categories must be an array using only allowed categories and may be empty. "
        "confidence must be a number between 0 and 1. "
        "reason must be concise.\n\n"
        f"Allowed categories: {categories_text}\n\n"
        f"Article:\n{json.dumps(article.model_dump(), ensure_ascii=True, indent=2)}"
    )


def build_correction_prompt(previous_response: str, validation_error: str) -> str:
    categories_text = ", ".join(ALLOWED_CATEGORIES)
    return (
        "Your previous output did not match the required JSON schema. "
        "Return ONLY corrected JSON, with no markdown and no extra text.\n\n"
        f"Allowed categories: {categories_text}\n"
        f"Validation error: {validation_error}\n"
        f"Previous output: {previous_response}"
    )
