from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from academic_insight_ai.apis.common import build_provider
from academic_insight_ai.core.config import load_config
from academic_insight_ai.tasks.article_classification.service import (
    ClassificationRequest,
    classify,
)
from academic_insight_ai.tasks.paper_reader.service import SummaryRequest, extract_pdf, summarize
from paper_categories import CATEGORIES


def elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PDF extraction, Thai summarization, and classification without the fund-management apps."
    )
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--model", default="qwen3-4b", help="Logical model ID from the model registry")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/manual-paper-test/results.json"),
    )
    args = parser.parse_args()

    missing = [str(path) for path in args.pdfs if not path.is_file()]
    if missing:
        parser.error(f"PDF file not found: {', '.join(missing)}")

    config = load_config()
    provider, provider_model_name = build_provider(args.model)
    report: dict[str, object] = {
        "logical_model": args.model,
        "provider_model": provider_model_name,
        "papers": [],
    }

    for path in args.pdfs:
        print(f"[{path.name}] extracting metadata...", flush=True)
        started = time.perf_counter()
        extracted = extract_pdf(
            path.read_bytes(),
            provider,
            provider_model_name,
            max_bytes=config.max_pdf_bytes,
            max_pages=config.max_pdf_pages,
            ocrmypdf_command=config.ocrmypdf_command,
        )
        extraction_seconds = elapsed(started)

        print(f"[{path.name}] summarizing abstract...", flush=True)
        started = time.perf_counter()
        summary = summarize(
            SummaryRequest(abstract=extracted.abstract, content=extracted.text),
            provider,
            provider_model_name,
        )
        summary_seconds = elapsed(started)

        print(f"[{path.name}] classifying...", flush=True)
        started = time.perf_counter()
        classification = classify(
            ClassificationRequest(
                title=extracted.title or path.stem,
                abstract=extracted.abstract,
                content=extracted.text,
                categories=CATEGORIES,
                taxonomy_version="2026-09-21-seven-category",
            ),
            provider,
            provider_model_name,
        )
        classification_seconds = elapsed(started)

        paper_result = {
            "source_pdf": str(path.resolve()),
            "timings_seconds": {
                "extract": extraction_seconds,
                "summarize": summary_seconds,
                "classify": classification_seconds,
                "total": round(extraction_seconds + summary_seconds + classification_seconds, 2),
            },
            "extraction": extracted.model_dump(exclude={"text"}),
            "summary": summary.model_dump(),
            "classification": classification.model_dump(),
        }
        report["papers"].append(paper_result)  # type: ignore[union-attr]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{path.name}] complete in {paper_result['timings_seconds']['total']}s", flush=True)

    print(f"Results written to {args.output.resolve()}", flush=True)


if __name__ == "__main__":
    main()
