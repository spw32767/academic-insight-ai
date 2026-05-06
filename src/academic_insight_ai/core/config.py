from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    ollama_base_url: str
    default_model: str
    log_level: str


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        default_model=os.getenv("DEFAULT_MODEL", "phi3"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
