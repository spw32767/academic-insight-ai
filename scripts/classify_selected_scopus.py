"""Classify frozen, unseen Scopus records without reading their Astra labels."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from academic_insight_ai.apis.common import build_provider
from academic_insight_ai.tasks.article_classification.service import ClassificationRequest, classify
from classify_scopus_export import TAXONOMY_VERSION, save_checkpoint
from paper_categories import CATEGORIES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=Path("outputs/new-scopus-v1/source_records.json"))
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/new-scopus-v1/manifest.json"))
    parser.add_argument("--mode", choices=["legacy", "fewshot_candidate", "boundary_candidate"], required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--model", default="qwen3-4b")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = json.loads(args.records.read_text(encoding="utf-8"))
    expected_ids = set(manifest["random_ids"]) | set(manifest["challenge_ids"])
    if len(expected_ids) != manifest["total_selected"] or {row["scopus_id"] for row in records} != expected_ids:
        raise ValueError("Record snapshot does not match the frozen evaluation manifest")
    provider, model_name = build_provider(args.model)
    if args.checkpoint.exists():
        report = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if (report["source_sha256"] != manifest["source_sha256"] or report["verification_mode"] != args.mode
                or report["model"] != args.model or report["taxonomy_version"] != TAXONOMY_VERSION):
            raise ValueError("Checkpoint belongs to another model, mode, taxonomy, or workbook")
    else:
        report = {"source_sha256": manifest["source_sha256"], "source_file": str(args.records.resolve()),
                  "model": args.model, "taxonomy_version": TAXONOMY_VERSION,
                  "verification_mode": args.mode, "total_records": len(records), "results": {}}
    for record in records:
        key = record["scopus_id"]
        if key in report["results"]:
            continue
        request = ClassificationRequest(paper_id=key, title=record["title"], abstract=record["abstract"],
                                        authkeywords=record["authkeywords"], categories=CATEGORIES,
                                        taxonomy_version=TAXONOMY_VERSION, verification_mode=args.mode)
        started = time.perf_counter()
        result = None
        error = None
        for attempt in range(3):
            try:
                result = classify(request, provider, model_name)
                break
            except Exception as exc:
                error = str(exc)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        if result is not None:
            report["classifier_version"] = result.classifier_version
        report["results"][key] = {
            "row": record["row"], "scopus_id": key, "title": record["title"],
            "category_code": result.primary_category_code if result else None,
            "confidence": result.confidence if result else "Preface",
            "model_reported_confidence": result.model_reported_confidence if result else None,
            "confidence_source": result.confidence_source if result else "model_error",
            "reason": result.reason if result else "Classification failed after three attempts.",
            "classification_error": error if result is None else None,
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
        save_checkpoint(args.checkpoint, report)
        print(f"{len(report['results'])}/{len(records)}: "
              f"{result.primary_category_code or 'NULL' if result else 'ERROR'} / "
              f"{result.confidence if result else 'Preface'}", flush=True)
    print(f"Saved {len(report['results'])} rows to {args.checkpoint}")


if __name__ == "__main__":
    main()
