from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from academic_insight_ai.core.validation import extract_json_object, validate_model
from academic_insight_ai.models.types import GenerateRequest
from academic_insight_ai.tasks.article_classification.prompt import (
    build_correction_prompt,
    build_prompt,
)
from academic_insight_ai.tasks.article_classification.schema import (
    ArticleClassification,
    ArticleInput,
)
from academic_insight_ai.tasks.article_classification.config import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)


def _detect_error_type(error: Exception) -> str:
    text = str(error).lower()
    if "json" in text:
        return "json_parse_error"
    if "field required" in text or "missing" in text:
        return "missing_required_field"
    if "invalid category" in text or "secondary categories" in text:
        return "invalid_category"
    if "confidence" in text:
        return "invalid_confidence"
    return "schema_validation_error"


def _normalize_model_payload(data: dict[str, Any], article_id: int) -> dict[str, Any]:
    alias_map = {
        "paper_id": "article_id",
        "id": "article_id",
        "main_focus": "primary_category",
        "main_field": "primary_category",
        "category": "primary_category",
        "subfields": "secondary_categories",
        "secondary": "secondary_categories",
        "justification": "reason",
        "rationale": "reason",
    }

    normalized: dict[str, Any] = {}
    for key, value in data.items():
        canonical_key = alias_map.get(key, key)
        normalized[canonical_key] = value

    normalized["article_id"] = article_id

    if not isinstance(normalized.get("secondary_categories"), list):
        normalized["secondary_categories"] = []

    if isinstance(normalized.get("confidence"), str):
        try:
            normalized["confidence"] = float(normalized["confidence"])
        except ValueError:
            normalized["confidence"] = 0.5

    if "confidence" not in normalized:
        normalized["confidence"] = 0.5

    if isinstance(normalized.get("confidence"), (int, float)):
        normalized["confidence"] = max(0.0, min(1.0, float(normalized["confidence"])))
    else:
        normalized["confidence"] = 0.5

    if "reason" not in normalized or not isinstance(normalized.get("reason"), str):
        normalized["reason"] = "Model response required normalization to match output schema."

    primary_category = normalized.get("primary_category")
    if isinstance(primary_category, str) and primary_category not in ALLOWED_CATEGORIES:
        normalized["primary_category"] = "Other"

    secondary = normalized.get("secondary_categories", [])
    if isinstance(secondary, list):
        normalized["secondary_categories"] = [
            item for item in secondary if isinstance(item, str) and item in ALLOWED_CATEGORIES
        ]

    allowed_keys = {
        "article_id",
        "primary_category",
        "secondary_categories",
        "confidence",
        "reason",
    }
    return {key: value for key, value in normalized.items() if key in allowed_keys}


def _classify_one(article: ArticleInput, model_name: str, provider: Any) -> dict[str, Any]:
    initial_prompt = build_prompt(article)
    first_response = provider.generate(
        GenerateRequest(model_name=model_name, prompt=initial_prompt, json_mode=True)
    ).text

    try:
        first_json = extract_json_object(first_response)
        normalized_first_json = _normalize_model_payload(first_json, article.article_id)
        parsed = validate_model(
            {
                **normalized_first_json,
                "model": model_name,
                "confidence_source": "model_reported",
                "debug_initial_prompt": initial_prompt,
                "raw_model_response": first_response,
            },
            ArticleClassification,
        )
        return parsed.model_dump()
    except (ValueError, ValidationError) as first_error:
        first_error_type = _detect_error_type(first_error)
        correction_prompt = build_correction_prompt(article, str(first_error))
        corrected_response = provider.generate(
            GenerateRequest(model_name=model_name, prompt=correction_prompt, json_mode=True)
        ).text
        try:
            corrected_json = extract_json_object(corrected_response)
            normalized_corrected_json = _normalize_model_payload(corrected_json, article.article_id)
            parsed = validate_model(
                {
                    **normalized_corrected_json,
                    "model": model_name,
                    "confidence_source": "model_reported",
                    "validation_error_type": first_error_type,
                    "debug_initial_prompt": initial_prompt,
                    "debug_correction_prompt": correction_prompt,
                    "raw_model_response": corrected_response,
                },
                ArticleClassification,
            )
            return parsed.model_dump()
        except (ValueError, ValidationError) as second_error:
            second_error_type = _detect_error_type(second_error)
            return {
                "article_id": article.article_id,
                "primary_category": "Other",
                "secondary_categories": [],
                "confidence": 0.0,
                "confidence_source": "model_reported",
                "reason": f"Validation failed after retry: {second_error}",
                "model": model_name,
                "validation_error_type": second_error_type,
                "debug_initial_prompt": initial_prompt,
                "debug_correction_prompt": correction_prompt,
                "raw_model_response": corrected_response,
                "status": "failed",
            }


def run_article_classification(
    *,
    input_path: Path,
    model_name: str,
    provider: Any,
    output_path: Path | None = None,
    limit: int | None = None,
) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = [ArticleInput.model_validate(item) for item in payload]
    if limit is not None:
        records = records[:limit]

    results = [_classify_one(article, model_name, provider) for article in records]

    if output_path is None:
        out_dir = Path("outputs/article-classification")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = out_dir / f"{timestamp}_{model_name}.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")
    logger.info("Wrote %s classified articles to %s", len(results), output_path)
    return output_path
