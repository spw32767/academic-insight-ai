"""Measure checkpoint agreement with the frozen model-authored Astra reference.

Agreement is not human-verified accuracy. Use development results for iteration;
holdout results are for one final selection check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


DEFAULT_REFERENCE_DIR = Path("evaluation/reference/astra-v1")


def load_reference(directory: Path) -> tuple[dict, dict]:
    reference = json.loads((directory / "reference.json").read_text(encoding="utf-8"))
    split = json.loads((directory / "split.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(json.dumps(reference, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if digest != split["reference_sha256"] or reference["source_sha256"] != split["source_sha256"]:
        raise ValueError("Frozen reference or source hash differs from split manifest")
    labels = set(reference["results"])
    development, holdout = set(split["development_ids"]), set(split["holdout_ids"])
    if development & holdout or development | holdout != labels:
        raise ValueError("Split does not partition the reference IDs")
    return reference, split


def _metrics(reference: dict, predictions: dict, ids: set[str]) -> dict:
    labels = reference["results"]
    ids = ids & set(predictions)
    pairs = [(labels[key], predictions[key]) for key in sorted(ids)]
    categories = [item["code"] for item in reference["categories"]] + ["Preface"]
    actual = [label["category_code"] or "Preface" for label, _ in pairs]
    predicted = [row["category_code"] or "Preface" for _, row in pairs]
    exact = sum(a == p for a, p in zip(actual, predicted))
    assigned = [(a, p) for a, p in zip(actual, predicted) if a != "Preface"]
    predicted_assigned = sum(p != "Preface" for p in predicted)
    durations = sorted(float(row.get("elapsed_seconds") or 0) for _, row in pairs)
    per_category = {}
    for code in categories:
        tp = sum(a == p == code for a, p in zip(actual, predicted))
        support = sum(a == code for a in actual)
        predicted_count = sum(p == code for p in predicted)
        precision = tp / predicted_count if predicted_count else None
        recall = tp / support if support else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
        per_category[code] = {"support": support, "predicted": predicted_count, "correct": tp,
                              "precision": round(precision, 4) if precision is not None else None,
                              "recall": round(recall, 4) if recall is not None else None,
                              "f1": round(f1, 4) if f1 is not None else None}
    disagreements = []
    for (label, row), a, p in zip(pairs, actual, predicted):
        if a != p or label["confidence"] != row["confidence"]:
            disagreements.append({"row": label["row"], "scopus_id": label["scopus_id"],
                                  "reference_category": a, "predicted_category": p,
                                  "reference_confidence": label["confidence"],
                                  "predicted_confidence": row["confidence"],
                                  "title": label["title"]})
    return {
        "evaluated": len(pairs), "category_exact": exact,
        "category_agreement": round(exact / len(pairs), 4) if pairs else None,
        "reference_assigned": len(assigned), "predicted_assigned": predicted_assigned,
        "category_agreement_on_reference_assigned": round(sum(a == p for a, p in assigned) / len(assigned), 4) if assigned else None,
        "false_assignment_on_reference_preface": sum(a == "Preface" and p != "Preface" for a, p in zip(actual, predicted)),
        "false_review_on_reference_assigned": sum(a != "Preface" and p == "Preface" for a, p in zip(actual, predicted)),
        "wrong_high": sum(a != p and row["confidence"] == "High" for (_, row), a, p in zip(pairs, actual, predicted)),
        "confidence_exact": sum(label["confidence"] == row["confidence"] for label, row in pairs),
        "confidence_distribution": dict(Counter(row["confidence"] for _, row in pairs)),
        "per_category": per_category,
        "confusions": [{"reference": a, "predicted": p, "count": n} for (a, p), n in
                       Counter((a, p) for a, p in zip(actual, predicted) if a != p).most_common()],
        "runtime_seconds": {"total": round(sum(durations), 2),
                            "mean": round(statistics.mean(durations), 2) if durations else None,
                            "p95": round(durations[max(0, int(len(durations) * .95) - 1)], 2) if durations else None},
        "disagreements": disagreements,
    }


def evaluate(reference: dict, split: dict, checkpoint: dict) -> dict:
    if checkpoint["source_sha256"] != reference["source_sha256"]:
        raise ValueError("Checkpoint describes a different source workbook")
    labels = reference["results"]
    predictions = checkpoint["results"]
    unknown = set(predictions) - set(labels)
    if unknown:
        raise ValueError(f"Checkpoint has unknown IDs: {sorted(unknown)[:3]}")
    for key, row in predictions.items():
        if row["row"] != labels[key]["row"]:
            raise ValueError(f"Workbook row changed for {key}")
    partitions = {"development": set(split["development_ids"]), "holdout": set(split["holdout_ids"]),
                  "all": set(labels)}
    return {"note": "Agreement with a model-authored reference, not expert-verified accuracy.",
            "reference_sha256": split["reference_sha256"], "source_sha256": split["source_sha256"],
            "model": checkpoint.get("model"), "classifier_version": checkpoint.get("classifier_version"),
            "verification_mode": checkpoint.get("verification_mode"),
            "partitions": {name: {"expected": len(ids), **_metrics(reference, predictions, ids)}
                           for name, ids in partitions.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reference, split = load_reference(args.reference_dir)
    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    report = evaluate(reference, split, checkpoint)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
