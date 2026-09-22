from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    ollama_base_url: str
    default_model: str
    log_level: str
    database_url: str | None
    classification_model: str
    reader_model: str
    api_key: str | None
    max_pdf_bytes: int
    max_pdf_pages: int
    ocrmypdf_command: str


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        default_model=os.getenv("DEFAULT_MODEL", "phi3"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv("DATABASE_URL"),
        classification_model=os.getenv("CLASSIFICATION_MODEL", os.getenv("DEFAULT_MODEL", "phi3")),
        reader_model=os.getenv("READER_MODEL", os.getenv("DEFAULT_MODEL", "phi3")),
        api_key=os.getenv("AI_API_KEY") or None,
        max_pdf_bytes=int(os.getenv("MAX_PDF_BYTES", str(25 * 1024 * 1024))),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "100")),
        ocrmypdf_command=os.getenv("OCRMY_PDF_COMMAND", "ocrmypdf"),
    )
