"""Freeze the Astra reference and a deterministic, duplicate-aware evaluation split."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_REFERENCE = Path("outputs/01a0be9d-d5ee-7f70-8057-84730bdaa853-astra-reference/scopus_astra_medium_reference.json")
DEFAULT_RECORDS = Path("outputs/01a0be9d-d5ee-7f70-8057-84730bdaa853-astra-reference/source_records.json")
DEFAULT_DESTINATION = Path("evaluation/reference/astra-v1")
SEED = "astra-v1-2026-09-23"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_rank(value: str) -> str:
    return digest(f"{SEED}:{value}".encode("utf-8"))


def normalized_title(value: object) -> str:
    return re.sub(r"[^\w]+", " ", str(value or "").casefold()).strip()


def make_split(reference: dict, source_records: list[dict]) -> dict:
    labels = reference["results"]
    records = {str(row["scopus_id"]): row for row in source_records}
    assert len(labels) == len(records) == 163
    assert set(labels) == set(records)
    assert len({item["row"] for item in labels.values()}) == 163
    codes = {item["code"] for item in reference["categories"]}
    for key, item in labels.items():
        assert item["category_code"] in codes | {None}, key
        assert (item["category_code"] is None) == (item["confidence"] == "Preface"), key
        assert item["row"] == records[key]["row"], key

    parent = {key: key for key in labels}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        parent[max(a, b)] = min(a, b)

    seen_title: dict[str, str] = {}
    seen_doi: dict[str, str] = {}
    for key, record in records.items():
        title = normalized_title(record.get("title"))
        doi = str(record.get("doi") or "").strip().casefold()
        if title:
            if title in seen_title:
                union(key, seen_title[title])
            else:
                seen_title[title] = key
        if doi:
            if doi in seen_doi:
                union(key, seen_doi[doi])
            else:
                seen_doi[doi] = key

    grouped: dict[str, list[str]] = defaultdict(list)
    for key in labels:
        grouped[find(key)].append(key)
    by_category: dict[str, list[list[str]]] = defaultdict(list)
    for members in grouped.values():
        categories = {labels[key]["category_code"] or "Preface" for key in members}
        if len(categories) != 1:
            raise ValueError(f"Duplicate group has conflicting reference categories: {members}")
        by_category[next(iter(categories))].append(sorted(members))

    development: set[str] = set()
    holdout: set[str] = set()
    distribution: dict[str, dict[str, int]] = {}
    for category, groups in sorted(by_category.items()):
        total = sum(len(group) for group in groups)
        target = max(1, round(total * 0.30)) if total <= 2 else round(total * 0.30)
        target = min(total - 1, target) if total > 1 else 1
        # Find the closest target without splitting a duplicate group.
        possible: dict[int, tuple[str, ...]] = {0: ()}
        ordered = sorted(groups, key=lambda group: stable_rank(group[0]))
        for group in ordered:
            next_possible = dict(possible)
            for count, selection in possible.items():
                new_count = count + len(group)
                candidate = selection + (group[0],)
                if new_count not in next_possible or candidate < next_possible[new_count]:
                    next_possible[new_count] = candidate
            possible = next_possible
        selected_count = min(possible, key=lambda count: (abs(count - target), count > target, count))
        selected = set(possible[selected_count])
        for group in ordered:
            (holdout if group[0] in selected else development).update(group)
        distribution[category] = {"all": total, "development": total - selected_count, "holdout": selected_count}

    assert not development & holdout
    assert development | holdout == set(labels)
    return {
        "schema_version": "astra-split-v1", "seed": SEED, "source_sha256": reference["source_sha256"],
        "reference_sha256": digest(json.dumps(reference, ensure_ascii=False, sort_keys=True).encode("utf-8")),
        "grouping": "Same normalized title or DOI stays in one split; no article is split.",
        "development_ids": sorted(development), "holdout_ids": sorted(holdout),
        "counts": {"all": len(labels), "development": len(development), "holdout": len(holdout)},
        "distribution": distribution,
    }


def write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Frozen reference differs: {path}; create a new version")
        return
    path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--source-records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    records = json.loads(args.source_records.read_text(encoding="utf-8"))
    assert reference["model"] == "gpt-6-astra" and reference["reasoning_effort"] == "medium"
    assert reference["human_expert_verified"] is False
    split = make_split(reference, records)
    args.destination.mkdir(parents=True, exist_ok=True)
    write_once(args.destination / "reference.json", args.reference.read_bytes())
    write_once(args.destination / "split.json", (json.dumps(split, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"counts": split["counts"], "distribution": split["distribution"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
