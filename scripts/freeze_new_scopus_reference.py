"""Validate and freeze the independent Astra labels for new Scopus papers."""

import hashlib
import json
from pathlib import Path

from prepare_astra_reference import write_once


def main() -> None:
    folder = Path("evaluation/new-scopus-v1")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    source = json.loads(Path("outputs/new-scopus-v1/source_records.json").read_text(encoding="utf-8"))
    source_by_id = {row["scopus_id"]: row for row in source}
    path = Path("outputs/new-scopus-v1/astra-reference.json")
    raw = path.read_bytes()
    reference = json.loads(raw)
    labels = reference["results"]
    ids = set(manifest["random_ids"]) | set(manifest["challenge_ids"])
    if (set(source_by_id) != set(labels) or set(labels) != ids or len(ids) != 130
            or reference["source_sha256"] != manifest["source_sha256"]
            or reference["model"] != "gpt-6-astra" or reference["reasoning_effort"] != "medium"
            or reference["human_expert_verified"] is not False):
        raise ValueError("Astra reference provenance or IDs do not match the frozen selection")
    codes = {category["code"] for category in reference["categories"]}
    for key, label in labels.items():
        row = source_by_id[key]
        if label["row"] != row["row"] or label["title"] != row["title"]:
            raise ValueError(f"Row or title mismatch: {key}")
        if label["category_code"] not in codes | {None}:
            raise ValueError(f"Invalid category: {key}")
        if (label["category_code"] is None) != (label["confidence"] == "Preface"):
            raise ValueError(f"Inconsistent review state: {key}")
        quote = label["evidence_quote"]
        if quote and not any(quote in str(row.get(field) or "") for field in ("title", "abstract", "authkeywords")):
            raise ValueError(f"Evidence quote absent from source: {key}")
    write_once(folder / "reference.json", raw)
    digest = hashlib.sha256(raw).hexdigest()
    write_once(folder / "reference.sha256", (digest + "\n").encode("ascii"))
    print(json.dumps({"records": len(ids), "sha256": digest, "categories": reference["category_counts"]}))


if __name__ == "__main__":
    main()
