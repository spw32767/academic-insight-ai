from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateRequest:
    model_name: str
    prompt: str
    temperature: float = 0.0
    json_mode: bool = False
    num_predict: int = 512


@dataclass(frozen=True)
class GenerateResponse:
    text: str
    raw: dict
