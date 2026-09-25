import pytest

from scripts.evaluate_classification_checkpoint import evaluate


def test_evaluation_counts_agreement_only_when_both_assign_a_category():
    baseline = {"source_sha256": "same", "results": {
        "1": {"category_code": "A", "confidence": "High", "elapsed_seconds": 2},
        "2": {"category_code": "B", "confidence": "High", "elapsed_seconds": 2},
    }}
    candidate = {"source_sha256": "same", "results": {
        "1": {"row": 2, "title": "One", "category_code": "A", "confidence": "Medium",
              "verification_status": "agreed", "evidence_quote": "A valid quote", "elapsed_seconds": 4},
        "2": {"row": 3, "title": "Two", "category_code": None, "confidence": "Preface",
              "verification_status": "needs_review", "candidate_category_codes": ["A", "B"],
              "reason": "Disagreement", "elapsed_seconds": 5},
    }}
    result = evaluate(baseline, candidate)
    assert result["both_assigned_count"] == 1
    assert result["same_category_when_both_assigned"] == 1
    assert result["candidate_review_with_alternatives"] == 1
    assert result["candidate_total_seconds"] == 9


def test_evaluation_rejects_different_workbooks():
    with pytest.raises(ValueError):
        evaluate({"source_sha256": "a", "results": {}}, {"source_sha256": "b", "results": {}})
