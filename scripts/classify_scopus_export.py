"""Classify Scopus export rows locally; save resumable JSON for workbook review.

This script reads the workbook but never edits it. The reviewed JSON is written
back to a *copy* of the workbook in a separate spreadsheet-authoring step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from openpyxl import load_workbook

from academic_insight_ai.apis.common import build_provider
from academic_insight_ai.tasks.article_classification.service import ClassificationRequest, classify
from paper_categories import CATEGORIES


TAXONOMY_VERSION = "2026-09-21-seven-category"


def read_records(path: Path) -> list[dict[str, object]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Documents"]
        rows = sheet.iter_rows(values_only=True)
        headers = next(rows)
        required = {"scopus_id", "scopus_link", "title", "abstract", "authkeywords", "category", "classification_confidence"}
        missing = required - set(headers)
        if missing:
            raise ValueError(f"Missing expected columns: {sorted(missing)}")
        records = []
        for row_number, cells in enumerate(rows, start=2):
            row = dict(zip(headers, cells))
            if not row.get("scopus_id"):
                continue
            if row.get("category") or row.get("classification_confidence"):
                raise ValueError(f"Row {row_number} already has a classification; refusing to overwrite it")
            keywords = row.get("authkeywords")
            if isinstance(keywords, str):
                try:
                    parsed = json.loads(keywords)
                    keywords = parsed if isinstance(parsed, list) else keywords
                except json.JSONDecodeError:
                    pass
            records.append({
                "row": row_number,
                "scopus_id": row["scopus_id"],
                "scopus_link": row["scopus_link"],
                "title": row["title"],
                "abstract": row["abstract"],
                "authkeywords": keywords,
            })
        return records
    finally:
        workbook.close()


def save_checkpoint(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=Path("outputs/scopus-classification/checkpoint.json"))
    parser.add_argument("--model", default="qwen3-4b")
    parser.add_argument("--limit", type=int, help="Classify at most this many new rows for a pilot run")
    parser.add_argument("--review-preface", action="store_true", help="Recheck substantive abstracts marked Preface")
    args = parser.parse_args()

    source_hash = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
    records = read_records(args.workbook)
    if len({str(record["scopus_id"]) for record in records}) != len(records):
        raise ValueError("Duplicate scopus_id values in workbook")
    if args.checkpoint.exists():
        report = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if report["source_sha256"] != source_hash or report["model"] != args.model:
            raise ValueError("Checkpoint belongs to another workbook or model")
    else:
        report = {
            "source_file": str(args.workbook.resolve()),
            "source_sha256": source_hash,
            "model": args.model,
            "taxonomy_version": TAXONOMY_VERSION,
            "total_records": len(records),
            "results": {},
        }

    provider, model_name = build_provider(args.model)
    results = report["results"]
    completed = 0
    for record in records:
        key = str(record["scopus_id"])
        if args.review_preface:
            previous = results.get(key)
            if not previous or previous["confidence"] != "Preface" or previous.get("reviewed_substantive_preface"):
                continue
            if str(record["title"] or "").lower().startswith(("preface", "editorial", "correction", "erratum", "retraction notice")):
                continue
            if len(str(record["abstract"] or "").strip()) <= 100:
                continue
        elif key in results:
            continue
        if args.limit is not None and completed >= args.limit:
            break
        request = ClassificationRequest(
            paper_id=key,
            title=str(record["title"] or ""),
            abstract=record["abstract"],
            authkeywords=record["authkeywords"],
            categories=CATEGORIES,
            taxonomy_version=TAXONOMY_VERSION,
        )
        started = time.perf_counter()
        for attempt in range(3):
            try:
                classification = classify(request, provider, model_name)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        updated = {
            "row": record["row"],
            "scopus_id": key,
            "title": record["title"],
            "scopus_link": record["scopus_link"],
            "category_code": classification.primary_category_code,
            "confidence": classification.confidence,
            "reason": classification.reason,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
        if args.review_preface:
            updated["reviewed_substantive_preface"] = True
            updated["previous_result"] = previous
        results[key] = updated
        save_checkpoint(args.checkpoint, report)
        completed += 1
        print(f"{len(results)}/{len(records)} row {record['row']}: {classification.primary_category_code or 'NULL'} / {classification.confidence}", flush=True)
    print(f"Saved {len(results)}/{len(records)} classifications to {args.checkpoint.resolve()}", flush=True)


if __name__ == "__main__":
    main()
