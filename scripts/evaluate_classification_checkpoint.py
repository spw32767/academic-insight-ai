"""Compare classifier checkpoints without treating either model output as ground truth."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def evaluate(baseline: dict, candidate: dict) -> dict:
    if baseline["source_sha256"] != candidate["source_sha256"]:
        raise ValueError("Checkpoints do not describe the same source workbook")
    old = baseline["results"]
    new = candidate["results"]
    shared = set(old) & set(new)
    new_rows = [new[key] for key in new]
    paired = [(old[key], new[key]) for key in shared]
    comparable = [(a, b) for a, b in paired if a["category_code"] and b["category_code"]]
    durations = [float(row.get("elapsed_seconds", 0)) for row in new_rows]
    old_durations = [float(row.get("elapsed_seconds", 0)) for row in old.values()]
    old_paired_seconds = sum(float(a.get("elapsed_seconds", 0)) for a, _ in paired)
    new_paired_seconds = sum(float(b.get("elapsed_seconds", 0)) for _, b in paired)
    sorted_durations = sorted(durations)
    return {
        "note": "Agreement with a previous model run is a stability measure, not accuracy.",
        "baseline_rows": len(old), "candidate_rows": len(new), "paired_rows": len(shared),
        "candidate_confidence": dict(Counter(row["confidence"] for row in new_rows)),
        "candidate_verification": dict(Counter(row.get("verification_status", "unknown") for row in new_rows)),
        "candidate_review_reasons": dict(Counter(
            "disagreement" if row.get("reason", "").startswith("Independent classifications disagree")
            else "invalid_evidence" if row.get("reason", "").startswith("Model evidence could not be validated")
            else "both_request_review" if row.get("reason", "").startswith("Both assessments request review")
            else "other"
            for row in new_rows if row.get("verification_status") == "needs_review"
        )),
        "candidate_review_with_alternatives": sum(
            row.get("verification_status") == "needs_review" and len(row.get("candidate_category_codes", [])) > 1
            for row in new_rows
        ),
        "candidate_evidence_quotes": sum(bool(row.get("evidence_quote")) for row in new_rows),
        "both_assigned_count": len(comparable),
        "same_category_when_both_assigned": sum(a["category_code"] == b["category_code"] for a, b in comparable),
        "changed_category_when_both_assigned": sum(a["category_code"] != b["category_code"] for a, b in comparable),
        "baseline_total_seconds": round(sum(old_durations), 2),
        "candidate_total_seconds": round(sum(durations), 2),
        "baseline_paired_seconds": round(old_paired_seconds, 2),
        "candidate_paired_seconds": round(new_paired_seconds, 2),
        "paired_runtime_multiplier": round(new_paired_seconds / old_paired_seconds, 2) if old_paired_seconds else None,
        "candidate_mean_seconds": round(statistics.mean(durations), 2) if durations else None,
        "candidate_p95_seconds": round(sorted_durations[max(0, int(len(durations) * .95) - 1)], 2)
        if sorted_durations else None,
        "review_rows": [
            {"row": row["row"], "title": row["title"], "candidates": row.get("candidate_category_codes", []),
             "reason": row["reason"]}
            for row in new_rows if row["confidence"] == "Preface"
            and row.get("verification_status") == "needs_review"
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    report = evaluate(baseline, candidate)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
