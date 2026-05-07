from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from academic_insight_ai.tasks.article_classification.config import ALLOWED_CATEGORIES


class ArticleInput(BaseModel):
    article_id: int
    title: str
    abstract: str


class ArticleClassification(BaseModel):
    article_id: int
    title: str
    primary_category: str
    secondary_categories: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_source: Literal["model_reported"] = "model_reported"
    reason: str
    model: str
    validation_error_type: str | None = None
    debug_initial_prompt: str | None = None
    debug_correction_prompt: str | None = None
    raw_model_response: str | None = None

    @field_validator("primary_category")
    @classmethod
    def validate_primary_category(cls, value: str) -> str:
        if value not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category: {value}")
        return value

    @field_validator("secondary_categories")
    @classmethod
    def validate_secondary_categories(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in ALLOWED_CATEGORIES]
        if invalid:
            raise ValueError(f"Invalid secondary categories: {invalid}")
        return value
