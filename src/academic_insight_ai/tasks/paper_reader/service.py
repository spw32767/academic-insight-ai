from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pypdf import PdfReader

from academic_insight_ai.core.validation import extract_json_object
from academic_insight_ai.models.types import GenerateRequest

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
DOI_LABEL_RE = re.compile(r"Digital\s+Object\s+Identifier\s+([^\r\n]+)", re.IGNORECASE)
ABSTRACT_RE = re.compile(r"\bABSTRACT\s+(.+?)\s+INDEX\s+TERMS?\b", re.IGNORECASE | re.DOTALL)
HEADER_AUTHOR_RE = re.compile(r"\b(?:[A-Z]\.\s*){1,4}[A-Z][A-Z'’-]{2,}\b")


class ExtractedPaper(BaseModel):
    title: str | None = None
    doi: str | None = None
    doi_candidates: list[str] = Field(default_factory=list)
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    journal_name: str | None = None
    page_count: int
    ocr_used: bool
    text: str
    warnings: list[str] = Field(default_factory=list)
    model: str


class SummaryRequest(BaseModel):
    abstract: str | None = Field(default=None, max_length=100_000)
    content: str | None = Field(default=None, max_length=500_000)
    model: str | None = None


class SummaryResult(BaseModel):
    summary_th: str
    source_type: str
    model: str


def _read_pdf(path: Path, max_pages: int) -> tuple[str, int, dict[str, Any]]:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ValueError("PDF is password protected")
        except Exception as exc:
            raise ValueError("PDF is password protected") from exc
    count = len(reader.pages)
    if count > max_pages:
        raise ValueError(f"PDF exceeds the {max_pages}-page limit")
    text = "\n\f\n".join((page.extract_text() or "") for page in reader.pages)
    return text, count, dict(reader.metadata or {})


def _needs_ocr(text: str, page_count: int) -> bool:
    compact = re.sub(r"\s+", "", text)
    return len(compact) < max(200, page_count * 80)


def _run_ocr(source: Path, target: Path, command: str) -> None:
    executable = shutil.which(command)
    if not executable:
        raise RuntimeError(f"OCR required but '{command}' is not installed")
    completed = subprocess.run(
        [executable, "--skip-text", "--deskew", "--rotate-pages", "-l", "tha+eng", str(source), str(target)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"OCR failed: {completed.stderr[-500:]}")


def _normalize_doi(value: str) -> str:
    return value.rstrip(".,;:)]}>").lower()


def _find_labeled_abstract(text: str) -> str | None:
    match = ABSTRACT_RE.search(text[:30_000])
    if not match:
        return None
    abstract = re.sub(r"\s+", " ", match.group(1)).strip()
    return abstract or None


def _find_header_authors(text: str) -> list[str]:
    header = text[: text.upper().find("ABSTRACT") if "ABSTRACT" in text.upper() else 4_000]
    return list(dict.fromkeys(re.sub(r"\s+", " ", item).strip() for item in HEADER_AUTHOR_RE.findall(header)))


def _find_trusted_doi(text: str, metadata: dict[str, Any]) -> str | None:
    # PDF text extractors sometimes split the publisher prefix as "10.1 109".
    # The DOI label on the first page is stronger evidence than DOI values in references.
    for labeled_value in DOI_LABEL_RE.findall(text[:20_000]):
        repaired = re.sub(r"(?<=\d)\s+(?=\d)", "", labeled_value)
        matches = DOI_RE.findall(repaired)
        if matches:
            return _normalize_doi(matches[0])

    metadata_text = " ".join(str(value) for value in metadata.values())
    matches = DOI_RE.findall(metadata_text)
    return _normalize_doi(matches[0]) if matches else None


def _find_doi_candidates(text: str, metadata: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    trusted_doi = _find_trusted_doi(text, metadata)
    if trusted_doi:
        candidates.append(trusted_doi)

    metadata_text = " ".join(str(value) for value in metadata.values())
    candidates.extend(DOI_RE.findall(metadata_text))
    candidates.extend(DOI_RE.findall(text[:100_000]))
    return list(dict.fromkeys(_normalize_doi(item) for item in candidates))


def extract_pdf(
    data: bytes,
    provider: Any,
    model_name: str,
    *,
    max_bytes: int,
    max_pages: int,
    ocrmypdf_command: str,
) -> ExtractedPaper:
    if not data.startswith(b"%PDF-"):
        raise ValueError("Uploaded file is not a PDF")
    if len(data) > max_bytes:
        raise ValueError(f"PDF exceeds the {max_bytes}-byte limit")

    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="academic-reader-") as temp_dir:
        source = Path(temp_dir) / "source.pdf"
        source.write_bytes(data)
        text, page_count, metadata = _read_pdf(source, max_pages)
        ocr_used = False
        if _needs_ocr(text, page_count):
            target = Path(temp_dir) / "ocr.pdf"
            _run_ocr(source, target, ocrmypdf_command)
            text, page_count, metadata = _read_pdf(target, max_pages)
            ocr_used = True
        if _needs_ocr(text, page_count):
            warnings.append("Extracted text is sparse; please verify the result")

    trusted_doi = _find_trusted_doi(text, metadata)
    trusted_abstract = _find_labeled_abstract(text)
    doi_candidates = _find_doi_candidates(text, metadata)
    requested_keys = "title, doi, authors, publication_year, journal_name"
    if not trusted_abstract:
        requested_keys += ", abstract"
    prompt = (
        "Extract metadata for the paper represented by this text. Read the paper header and ABSTRACT section. "
        "Include every author shown in the header. Ignore identifiers and author names from the reference list. "
        f"Return one JSON object only with keys {requested_keys}. "
        "Use null or [] when unknown and never invent a value.\n"
        f"PDF metadata: {json.dumps(metadata, ensure_ascii=False, default=str)}\n"
        f"DOI candidates: {json.dumps(doi_candidates)}\nText from opening pages: {text[:8000]}"
    )
    response = provider.generate(GenerateRequest(model_name=model_name, prompt=prompt, json_mode=True, num_predict=1600))
    payload: dict[str, Any] = {}
    try:
        payload = extract_json_object(response.text)
    except (ValueError, TypeError) as exc:
        warnings.append(f"Model metadata was invalid; deterministic PDF fields were used: {exc}")

    model_selected_doi = payload.get("doi")
    selected_doi = trusted_doi
    if not selected_doi and model_selected_doi:
        selected_doi = _normalize_doi(str(model_selected_doi))
        if selected_doi not in doi_candidates:
            warnings.append("Model-selected DOI was not found verbatim in the PDF and was discarded")
            selected_doi = None
    year = payload.get("publication_year")
    try:
        if year is not None:
            year = int(year)
            if year < 1600 or year > 2200:
                year = None
    except (ValueError, TypeError):
        year = None
    model_authors = payload.get("authors") if isinstance(payload.get("authors"), list) else []
    header_authors = _find_header_authors(text)
    authors = header_authors or model_authors
    try:
        return ExtractedPaper(
            title=metadata.get("/Title") or payload.get("title"),
            doi=selected_doi,
            doi_candidates=doi_candidates,
            abstract=trusted_abstract or payload.get("abstract"),
            authors=authors,
            publication_year=year,
            journal_name=payload.get("journal_name"),
            page_count=page_count,
            ocr_used=ocr_used,
            text=text,
            warnings=warnings,
            model=model_name,
        )
    except ValidationError as exc:
        raise ValueError(f"Extracted text but metadata validation failed: {exc}") from exc


def summarize(request: SummaryRequest, provider: Any, model_name: str) -> SummaryResult:
    source = request.abstract or request.content
    if not source or not source.strip():
        raise ValueError("abstract or content is required")
    source_type = "abstract" if request.abstract else "full_text"
    chunks = [source] if source_type == "abstract" else _content_chunks(source)
    partials: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        prompt = (
            "Summarize this part of an academic paper accurately in Thai. Preserve the research goal, method, "
            "data, and findings when present. Do not add facts. Return JSON only with key summary_th.\n"
            f"Part {index} of {len(chunks)}:\n{chunk}"
        )
        response = provider.generate(GenerateRequest(model_name=model_name, prompt=prompt, json_mode=True, num_predict=900))
        payload = extract_json_object(response.text)
        partial = payload.get("summary_th")
        if not isinstance(partial, str) or not partial.strip():
            raise ValueError(f"Model did not return summary_th for part {index}")
        partials.append(partial.strip())
    if len(partials) == 1:
        summary = partials[0]
    else:
        reduction_prompt = (
            "Combine these partial summaries into an accurate Thai summary of the whole paper in 1-2 concise paragraphs. "
            "Remove repetition and do not add facts. Return JSON only with key summary_th.\n"
            + "\n".join(f"Part {index}: {value}" for index, value in enumerate(partials, start=1))
        )
        response = provider.generate(GenerateRequest(model_name=model_name, prompt=reduction_prompt, json_mode=True, num_predict=1200))
        summary = extract_json_object(response.text).get("summary_th")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Model did not return summary_th")
    return SummaryResult(summary_th=summary.strip(), source_type=source_type, model=model_name)


def _content_chunks(content: str, max_chunks: int = 24) -> list[str]:
    content = content.strip()
    if not content:
        return []
    chunk_size = max(12_000, (len(content) + max_chunks - 1) // max_chunks)
    return [content[start : start + chunk_size] for start in range(0, len(content), chunk_size)]
