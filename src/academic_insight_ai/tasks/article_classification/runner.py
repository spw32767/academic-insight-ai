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

logger = logging.getLogger(__name__)


def _classify_one(article: ArticleInput, model_name: str, provider: Any) -> dict[str, Any]:
    initial_prompt = build_prompt(article)
    first_response = provider.generate(GenerateRequest(model_name=model_name, prompt=initial_prompt)).text

    try:
        first_json = extract_json_object(first_response)
        parsed = validate_model(
            {
                **first_json,
                "article_id": article.article_id,
                "model": model_name,
                "debug_initial_prompt": initial_prompt,
                "raw_model_response": first_response,
            },
            ArticleClassification,
        )
        return parsed.model_dump()
    except (ValueError, ValidationError) as first_error:
        correction_prompt = build_correction_prompt(first_response, str(first_error))
        corrected_response = provider.generate(
            GenerateRequest(model_name=model_name, prompt=correction_prompt)
        ).text
        try:
            corrected_json = extract_json_object(corrected_response)
            parsed = validate_model(
                {
                    **corrected_json,
                    "article_id": article.article_id,
                    "model": model_name,
                    "debug_initial_prompt": initial_prompt,
                    "debug_correction_prompt": correction_prompt,
                    "raw_model_response": corrected_response,
                },
                ArticleClassification,
            )
            return parsed.model_dump()
        except (ValueError, ValidationError) as second_error:
            return {
                "article_id": article.article_id,
                "primary_category": "Other",
                "secondary_categories": [],
                "confidence": 0.0,
                "reason": f"Validation failed after retry: {second_error}",
                "model": model_name,
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
