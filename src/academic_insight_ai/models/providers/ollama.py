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
            "think": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.num_predict,
            },
        }
        if request.json_mode:
            payload["format"] = "json"

        response = requests.post(url, json=payload, timeout=self._timeout_seconds)
        response.raise_for_status()
        data = response.json()
        response_text = data.get("response", "")
        if not response_text and isinstance(data.get("thinking"), str):
            response_text = data["thinking"]
        return GenerateResponse(text=response_text, raw=data)
