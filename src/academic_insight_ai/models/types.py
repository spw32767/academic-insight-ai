from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateRequest:
    model_name: str
    prompt: str
    temperature: float = 0.0


@dataclass(frozen=True)
class GenerateResponse:
    text: str
    raw: dict
