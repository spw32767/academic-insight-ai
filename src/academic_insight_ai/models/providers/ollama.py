from __future__ import annotations

import requests

from academic_insight_ai.models.providers.base import BaseModelProvider
from academic_insight_ai.models.types import GenerateRequest, GenerateResponse


class OllamaProvider(BaseModelProvider):
    def __init__(self, base_url: str, timeout_seconds: int = 120) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        url = f"{self._base_url}/api/generate"
        payload = {
            "model": request.model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        response = requests.post(url, json=payload, timeout=self._timeout_seconds)
        response.raise_for_status()
        data = response.json()
        return GenerateResponse(text=data.get("response", ""), raw=data)
