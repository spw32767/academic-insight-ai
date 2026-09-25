import json
from pathlib import Path

import pytest

from scripts.evaluate_against_astra import evaluate, load_reference
from scripts.prepare_astra_reference import write_once


def test_frozen_reference_split_is_complete_and_disjoint():
    reference, split = load_reference(Path("evaluation/reference/astra-v1"))
    development = set(split["development_ids"])
    holdout = set(split["holdout_ids"])
    assert development.isdisjoint(holdout)
    assert development | holdout == set(reference["results"])
    assert len(development) == 112 and len(holdout) == 51


def test_evaluator_counts_high_confidence_errors_and_reviews():
    reference = {"categories": [{"code": "A"}, {"code": "B"}], "source_sha256": "source", "results": {
        "1": {"row": 2, "scopus_id": "1", "title": "A", "category_code": "A", "confidence": "High"},
        "2": {"row": 3, "scopus_id": "2", "title": "B", "category_code": "B", "confidence": "Medium"},
        "3": {"row": 4, "scopus_id": "3", "title": "C", "category_code": None, "confidence": "Preface"},
    }}
    split = {"source_sha256": "source", "reference_sha256": "ref",
             "development_ids": ["1", "2"], "holdout_ids": ["3"]}
    checkpoint = {"source_sha256": "source", "results": {
        "1": {"row": 2, "category_code": "B", "confidence": "High", "elapsed_seconds": 2},
        "2": {"row": 3, "category_code": None, "confidence": "Preface", "elapsed_seconds": 3},
        "3": {"row": 4, "category_code": "A", "confidence": "Low", "elapsed_seconds": 1},
    }}
    report = evaluate(reference, split, checkpoint)
    all_rows = report["partitions"]["all"]
    assert all_rows["wrong_high"] == 1
    assert all_rows["false_review_on_reference_assigned"] == 1
    assert all_rows["false_assignment_on_reference_preface"] == 1
    assert all_rows["runtime_seconds"]["total"] == 6
    assert report["partitions"]["development"]["evaluated"] == 2
    assert report["partitions"]["holdout"]["evaluated"] == 1
    checkpoint["source_sha256"] = "other"
    with pytest.raises(ValueError, match="different source"):
        evaluate(reference, split, checkpoint)


def test_frozen_reference_cannot_be_overwritten(tmp_path):
    path = tmp_path / "reference.json"
    write_once(path, b"first")
    write_once(path, b"first")
    with pytest.raises(ValueError, match="Frozen reference differs"):
        write_once(path, b"second")
    assert path.read_bytes() == b"first"


def test_fewshot_pilot_uses_only_unseen_development_records():
    _, split = load_reference(Path("evaluation/reference/astra-v1"))
    pilot = json.loads(Path("evaluation/fewshot-v1/manifest.json").read_text(encoding="utf-8"))
    examples, pilot_ids = set(pilot["example_ids"]), set(pilot["pilot_ids"])
    assert len(examples) == 8 and len(pilot_ids) == 30
    assert examples.isdisjoint(pilot_ids)
    assert examples | pilot_ids <= set(split["development_ids"])
