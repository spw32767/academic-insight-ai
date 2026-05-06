from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    logical_id: str
    provider: str
    provider_model_name: str


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "phi3": ModelSpec(logical_id="phi3", provider="ollama", provider_model_name="phi3"),
    "gemma": ModelSpec(logical_id="gemma", provider="ollama", provider_model_name="gemma:2b"),
    "qwen3-4b": ModelSpec(logical_id="qwen3-4b", provider="ollama", provider_model_name="qwen3:4b"),
}


def get_model_spec(logical_id: str) -> ModelSpec:
    if logical_id not in MODEL_REGISTRY:
        available = ", ".join(sorted(MODEL_REGISTRY.keys()))
        raise ValueError(f"Unknown model '{logical_id}'. Available models: {available}")
    return MODEL_REGISTRY[logical_id]


def list_models() -> list[str]:
    return sorted(MODEL_REGISTRY.keys())
