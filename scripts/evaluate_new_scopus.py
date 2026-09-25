"""Evaluate frozen new-paper checkpoints against independent Astra judgments."""

import argparse
import hashlib
import json
from pathlib import Path

from evaluate_against_astra import _metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoints", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, default=Path("outputs/new-scopus-v1/evaluation.json"))
    args = parser.parse_args()
    folder = Path("evaluation/new-scopus-v1")
    raw = (folder / "reference.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != (folder / "reference.sha256").read_text(encoding="ascii").strip():
        raise ValueError("Frozen Astra reference hash differs")
    reference = json.loads(raw)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    cohorts = {"random": set(manifest["random_ids"]), "challenge": set(manifest["challenge_ids"])}
    cohorts["all"] = cohorts["random"] | cohorts["challenge"]
    if set(reference["results"]) != cohorts["all"]:
        raise ValueError("Reference IDs differ from frozen selection")
    reports = {}
    for path in args.checkpoints:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        predictions = checkpoint["results"]
        if checkpoint["source_sha256"] != manifest["source_sha256"] or set(predictions) != cohorts["all"]:
            raise ValueError(f"Incomplete or wrong-source checkpoint: {path}")
        for key, row in predictions.items():
            if row["row"] != reference["results"][key]["row"]:
                raise ValueError(f"Row mismatch: {key}")
        mode = checkpoint["verification_mode"]
        reports[mode] = {}
        for cohort, ids in cohorts.items():
            result = _metrics(reference, predictions, ids)
            failed = [key for key in ids if predictions[key].get("classification_error")]
            result["classification_errors"] = len(failed)
            result["category_exact_excluding_error_matches"] = result["category_exact"] - sum(
                reference["results"][key]["category_code"] is None for key in failed)
            raw_high = [key for key in ids if (
                predictions[key].get("model_reported_confidence") or predictions[key]["confidence"]
            ) == "High"]
            result["model_reported_high"] = len(raw_high)
            result["model_reported_high_category_disagreements"] = sum(
                (predictions[key]["category_code"] or "Preface") !=
                (reference["results"][key]["category_code"] or "Preface") for key in raw_high)
            reports[mode][cohort] = result
    output = {"note": "Agreement with independent model-authored Astra labels, not expert-verified accuracy.",
              "reference_sha256": hashlib.sha256(raw).hexdigest(), "cohort_sizes": {k: len(v) for k,v in cohorts.items()},
              "runs": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {cohort: {"exact": metrics["category_exact"],
                                             "wrong_high": metrics["wrong_high"],
                                             "seconds": metrics["runtime_seconds"]["total"]}
                             for cohort, metrics in by_cohort.items()}
                      for name, by_cohort in reports.items()}))


if __name__ == "__main__":
    main()
