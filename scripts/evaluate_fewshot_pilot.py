"""Compare local classifier runs on matching few-shot development IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_against_astra import _metrics, load_reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=Path("evaluation/fewshot-v1/manifest.json"))
    parser.add_argument("--legacy", type=Path, default=Path("outputs/my-local-test/results.json"))
    parser.add_argument("--boundaries", type=Path, default=Path("outputs/astra-evaluation/candidate-development.json"))
    parser.add_argument("--fewshot", type=Path, default=Path("outputs/fewshot-v1/pilot.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/fewshot-v1/evaluation.json"))
    parser.add_argument("--scope", choices=["pilot", "development"], default="pilot")
    args = parser.parse_args()
    reference, split = load_reference(Path("evaluation/reference/astra-v1"))
    pilot = json.loads(args.pilot.read_text(encoding="utf-8"))
    ids = (set(pilot["pilot_ids"]) if args.scope == "pilot"
           else set(split["development_ids"]) - set(pilot["example_ids"]))
    if pilot["reference_sha256"] != split["reference_sha256"] or pilot["source_sha256"] != split["source_sha256"]:
        raise ValueError("Pilot belongs to another reference or workbook")
    if not ids <= set(split["development_ids"]) or ids & set(pilot["example_ids"]):
        raise ValueError("Pilot overlaps examples or holdout")
    reports = {}
    for name, path in (("legacy", args.legacy), ("boundaries", args.boundaries), ("fewshot", args.fewshot)):
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint["source_sha256"] != split["source_sha256"]:
            raise ValueError(f"{name} checkpoint belongs to another workbook")
        if not ids <= set(checkpoint["results"]):
            raise ValueError(f"{name} checkpoint is missing pilot IDs")
        for key in ids:
            if checkpoint["results"][key]["row"] != reference["results"][key]["row"]:
                raise ValueError(f"{name} checkpoint row mismatch: {key}")
        reports[name] = _metrics(reference, checkpoint["results"], ids)
    result = {"note": "Agreement with model-authored Astra labels, not expert-verified accuracy.",
              "scope": args.scope,
              "pilot_count": len(ids), "example_count": len(pilot["example_ids"]), "runs": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {"agreement": run["category_agreement"], "wrong_high": run["wrong_high"],
                             "runtime_seconds": run["runtime_seconds"]["total"]}
                      for name, run in reports.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
