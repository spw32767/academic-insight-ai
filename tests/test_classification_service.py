import json

from academic_insight_ai.models.types import GenerateResponse
from academic_insight_ai.tasks.article_classification.service import (
    CategoryDefinition,
    ClassificationRequest,
    classify,
)


SOURCE = "We introduce a secure routing protocol for distributed sensor networks."


class FakeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.prompts = []

    def generate(self, request):
        self.prompts.append(request.prompt)
        assert request.json_schema is not None
        return GenerateResponse(text=next(self.responses), raw={})


def decision(category="NETWORK", confidence="High", quote=SOURCE, reason="Routing protocol"):
    return json.dumps({
        "primary_category_code": category,
        "confidence": confidence,
        "primary_contribution": "A secure routing protocol",
        "evidence_quote": quote,
        "reason": reason,
    })


def request():
    return ClassificationRequest(
        paper_id=7,
        title="A useful paper",
        abstract=SOURCE,
        categories=[CategoryDefinition(code="NETWORK", name="Network"),
                    CategoryDefinition(code="OTHER", name="Other")],
        taxonomy_version="2026-01",
        verification_mode="evidence_agreement",
    )


def test_two_independent_agreeing_passes_and_exact_evidence():
    provider = FakeProvider([decision(), decision(confidence="Medium")])
    result = classify(request(), provider, "fake")
    assert result.primary_category_code == "NETWORK"
    assert result.confidence == "Medium"
    assert result.verification_status == "agreed"
    assert result.evidence_quote == SOURCE
    assert result.evidence_source == "abstract"
    assert [item.category_code for item in result.assessments] == ["NETWORK", "NETWORK"]
    assert len(provider.prompts) == 2
    assert provider.prompts[0] != provider.prompts[1]
    assert "previous classification" not in provider.prompts[1].lower() or "do not assume" in provider.prompts[1].lower()


def test_default_api_mode_assigns_after_one_validated_pass():
    req = request().model_copy(update={"verification_mode": "single"})
    provider = FakeProvider([decision()])
    result = classify(req, provider, "fake")
    assert result.primary_category_code == "NETWORK"
    assert result.verification_status == "single_validated"
    assert result.confidence_source == "model_reported_with_validated_quote"
    assert len(provider.prompts) == 1


def test_legacy_mode_remains_default_and_uses_original_json_contract():
    req = request().model_copy(update={"verification_mode": "legacy"})

    class LegacyProvider:
        def generate(self, generate_request):
            assert generate_request.json_mode is True
            assert generate_request.json_schema is None
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"High","reason":"Routing protocol"}',
                raw={},
            )

    result = classify(req, LegacyProvider(), "fake")
    assert result.primary_category_code == "NETWORK"
    assert result.verification_status == "legacy"
    assert result.confidence_source == "model_reported"
    assert ClassificationRequest(title="Paper", categories=req.categories).verification_mode == "legacy"


def test_astra_candidate_is_opt_in_and_has_its_own_version():
    req = request().model_copy(update={"verification_mode": "astra_candidate"})

    class CandidateProvider:
        def generate(self, generate_request):
            assert "reusable method" in generate_request.prompt
            assert generate_request.json_mode is True
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"Medium","reason":"Routing protocol"}',
                raw={},
            )

    result = classify(req, CandidateProvider(), "fake")
    assert result.classifier_version == "astra-boundaries-v1"
    assert result.primary_category_code == "NETWORK"
    assert result.confidence == "Medium"


def test_astra_candidate_clears_inconsistent_review_category():
    req = request().model_copy(update={"verification_mode": "astra_candidate"})

    class InconsistentProvider:
        def generate(self, generate_request):
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"Preface","reason":"Review"}', raw={}
            )

    result = classify(req, InconsistentProvider(), "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
    assert "inconsistent category" in result.reason


def test_fewshot_candidate_contains_examples_and_is_versioned():
    req = request().model_copy(update={"verification_mode": "fewshot_candidate"})

    class FewshotProvider:
        def generate(self, generate_request):
            assert "LLM-guided population-based reinforcement learning" in generate_request.prompt
            assert "CURRENT title: A useful paper" in generate_request.prompt
            assert generate_request.json_mode is True
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"Medium","reason":"Routing protocol"}',
                raw={},
            )

    result = classify(req, FewshotProvider(), "fake")
    assert result.classifier_version == "astra-fewshot-v1"
    assert result.primary_category_code == "NETWORK"


def test_boundary_candidate_preserves_model_rating_but_caps_operational_high():
    req = request().model_copy(update={"verification_mode": "boundary_candidate"})

    class BoundaryProvider:
        def generate(self, generate_request):
            assert "LymphAware lymphoma diagnosis" in generate_request.prompt
            assert "new architecture" in generate_request.prompt
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"High","reason":"Routing protocol"}',
                raw={},
            )

    result = classify(req, BoundaryProvider(), "fake")
    assert result.classifier_version == "astra-boundary-examples-v2"
    assert result.confidence == "Medium"
    assert result.model_reported_confidence == "High"
    assert result.confidence_source == "conservative_cap_pending_independent_validation"


def test_confidence_policy_can_cap_fewshot_without_changing_category():
    req = request().model_copy(update={
        "verification_mode": "fewshot_candidate", "confidence_policy": "conservative_cap",
    })

    class FewshotProvider:
        def generate(self, generate_request):
            return GenerateResponse(
                text='{"primary_category_code":"NETWORK","confidence":"High","reason":"Routing protocol"}',
                raw={},
            )

    result = classify(req, FewshotProvider(), "fake")
    assert result.primary_category_code == "NETWORK"
    assert result.confidence == "Medium"
    assert result.model_reported_confidence == "High"
    assert result.confidence_source == "conservative_cap_pending_independent_validation"


def test_disagreement_returns_review_without_forcing_category():
    result = classify(request(), FakeProvider([decision(), decision("OTHER")]), "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
    assert result.verification_status == "needs_review"
    assert result.candidate_category_codes == ["NETWORK", "OTHER"]
    assert [item.category_code for item in result.assessments] == ["NETWORK", "OTHER"]


def test_fabricated_quote_retries_then_returns_review():
    provider = FakeProvider([decision(quote="This sentence was never in the abstract"),
                             decision(quote="Nor was this sentence")])
    result = classify(request(), provider, "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
    assert "evidence" in result.reason.lower()
    assert len(provider.prompts) == 2


def test_invalid_category_retries_then_second_pass():
    provider = FakeProvider([decision("WRONG"), decision(), decision()])
    assert classify(request(), provider, "fake").primary_category_code == "NETWORK"
    assert len(provider.prompts) == 3


def test_preface_without_abstract_does_not_call_model():
    req = ClassificationRequest(title="Preface", categories=[CategoryDefinition(code="TCS", name="Theory")],
                                verification_mode="single")
    result = classify(req, FakeProvider([]), "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
    assert result.verification_status == "rule_based"


def test_retraction_notice_with_abstract_does_not_call_model():
    req = ClassificationRequest(
        title="Retraction Notice to An earlier paper", abstract=SOURCE,
        categories=[CategoryDefinition(code="NETWORK", name="Network")],
    )
    assert classify(req, FakeProvider([]), "fake").confidence == "Preface"


def test_both_passes_outside_taxonomy_request_review():
    req = request()
    provider = FakeProvider([decision(None, "Preface", "", "Outside taxonomy"),
                             decision(None, "Preface", "", "Outside taxonomy")])
    result = classify(req, provider, "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"


def test_quantum_category_needs_quantum_information_evidence():
    req = ClassificationRequest(title="Sensor routing", abstract=SOURCE,
                                categories=[CategoryDefinition(code="QUANTUM_INFORMATION", name="Quantum")],
                                verification_mode="single")
    provider = FakeProvider([decision("QUANTUM_INFORMATION"), decision("QUANTUM_INFORMATION")])
    result = classify(req, provider, "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
