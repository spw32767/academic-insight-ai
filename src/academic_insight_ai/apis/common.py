from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from academic_insight_ai.core.config import AppConfig, load_config
from academic_insight_ai.models.providers.ollama import OllamaProvider
from academic_insight_ai.models.registry import get_model_spec


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = load_config().api_key
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI_API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def build_provider(model_id: str) -> tuple[OllamaProvider, str]:
    config = load_config()
    spec = get_model_spec(model_id)
    if spec.provider != "ollama":
        raise ValueError(f"Unsupported provider: {spec.provider}")
    return OllamaProvider(config.ollama_base_url), spec.provider_model_name


def get_config() -> AppConfig:
    return load_config()
