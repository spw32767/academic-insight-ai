"""Freeze development-only examples and a small, disjoint few-shot pilot."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from academic_insight_ai.tasks.article_classification.fewshot_examples import EXAMPLES, EXAMPLE_IDS
from evaluate_against_astra import load_reference
from prepare_astra_reference import write_once


DESTINATION = Path("evaluation/fewshot-v1/manifest.json")
QUOTAS = {
    "AI_ALGORITHMS": 9,
    "APPLIED_AI": 8,
    "NETWORKS_SECURITY_DISTRIBUTED": 8,
    "COMPUTER_ENGINEERING_IOT_EMBEDDED": 2,
    "QUANTUM_INFORMATION": 2,
    "THEORETICAL_CS": 1,
}


def main() -> None:
    reference, split = load_reference(Path("evaluation/reference/astra-v1"))
    development = set(split["development_ids"])
    if not EXAMPLE_IDS <= development:
        raise ValueError("A prompt example is outside the development partition")
    labels = reference["results"]
    for key, _, quote, code, _ in EXAMPLES:
        label = labels[key]
        if label["category_code"] != code or quote not in label["evidence_quote"]:
            raise ValueError(f"Prompt example differs from frozen Astra reference: {key}")
    by_category = defaultdict(list)
    for key in development - EXAMPLE_IDS:
        by_category[labels[key]["category_code"] or "Preface"].append(key)
    selected = []
    for category, quota in QUOTAS.items():
        keys = sorted(by_category[category], key=lambda key: hashlib.sha256(f"fewshot-v1:{key}".encode()).hexdigest())
        if len(keys) < quota:
            raise ValueError(f"Too few development records for {category}")
        selected.extend(keys[:quota])
    if len(selected) != 30 or set(selected) & EXAMPLE_IDS:
        raise ValueError("Pilot is not 30 disjoint records")
    manifest = {
        "schema_version": "fewshot-pilot-v1", "reference_sha256": split["reference_sha256"],
        "source_sha256": split["source_sha256"], "seed": "fewshot-v1",
        "example_ids": sorted(EXAMPLE_IDS), "pilot_ids": sorted(selected), "quotas": QUOTAS,
        "note": "Examples and pilot are disjoint development records; no holdout labels were used.",
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    write_once(DESTINATION, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"examples": len(EXAMPLE_IDS), "pilot": len(selected), "quotas": QUOTAS}))


if __name__ == "__main__":
    main()
