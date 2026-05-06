from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    snippet = text[start : end + 1]
    return json.loads(snippet)


def validate_model(data: dict[str, Any], schema: type[T]) -> T:
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
