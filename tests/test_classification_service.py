from academic_insight_ai.models.types import GenerateResponse
from academic_insight_ai.tasks.article_classification.service import (
    CategoryDefinition,
    ClassificationRequest,
    classify,
)


class FakeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)

    def generate(self, request):
        return GenerateResponse(text=next(self.responses), raw={})


def test_classification_uses_dynamic_taxonomy() -> None:
    request = ClassificationRequest(
        paper_id=7,
        title="A useful paper",
        abstract="A study of secure networks",
        categories=[
            CategoryDefinition(code="NETWORK", name="Network"),
            CategoryDefinition(code="OTHER", name="Other"),
        ],
        taxonomy_version="2026-01",
    )
    provider = FakeProvider([
        '{"primary_category_code":"NETWORK","confidence":"High","reason":"Network research"}'
    ])

    result = classify(request, provider, "fake-model")

    assert result.primary_category_code == "NETWORK"
    assert result.confidence == "High"
    assert result.taxonomy_version == "2026-01"


def test_classification_retries_invalid_category() -> None:
    request = ClassificationRequest(
        title="A paper",
        abstract="An abstract",
        categories=[CategoryDefinition(code="OTHER", name="Other")],
    )
    provider = FakeProvider([
        '{"primary_category_code":"UNKNOWN","confidence":"High","reason":"bad"}',
        '{"primary_category_code":"OTHER","confidence":"Low","reason":"unclear"}',
    ])

    assert classify(request, provider, "fake").primary_category_code == "OTHER"


def test_classification_retries_numeric_confidence() -> None:
    request = ClassificationRequest(
        title="A paper",
        abstract="A research contribution is described in this abstract.",
        categories=[
            CategoryDefinition(code="OTHER", name="Other"),
        ],
    )
    provider = FakeProvider([
        '{"primary_category_code":"OTHER","confidence":0.5,"reason":"numeric"}',
        '{"primary_category_code":"OTHER","confidence":"Low","reason":"corrected"}',
    ])

    assert classify(request, provider, "fake").confidence == "Low"


def test_preface_without_abstract_does_not_call_model() -> None:
    request = ClassificationRequest(title="Preface", categories=[CategoryDefinition(code="TCS", name="Theory")])
    result = classify(request, FakeProvider([]), "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"


def test_retraction_notice_with_abstract_does_not_call_model() -> None:
    request = ClassificationRequest(
        title="Retraction Notice to An earlier quantum paper",
        abstract="The editors have retracted this article after an investigation.",
        categories=[CategoryDefinition(code="Q", name="Quantum")],
    )
    assert classify(request, FakeProvider([]), "fake").confidence == "Preface"


def test_model_may_request_review_with_null_category() -> None:
    request = ClassificationRequest(title="Unclear article", abstract="Insufficient detail", categories=[CategoryDefinition(code="TCS", name="Theory")])
    provider = FakeProvider(['{"primary_category_code":null,"confidence":"Preface","reason":"Insufficient evidence"}'])
    assert classify(request, provider, "fake").confidence == "Preface"


def test_substantive_abstract_may_be_outside_taxonomy() -> None:
    request = ClassificationRequest(
        title="Chemical sensing with gold nanoparticles",
        abstract="A spectroscopy platform detects a chemical compound using gold nanoparticles. " * 3,
        categories=[CategoryDefinition(code="APPLIED_AI", name="Applied AI in healthcare")],
    )
    provider = FakeProvider(['{"primary_category_code":null,"confidence":"Preface","reason":"Outside taxonomy"}'])
    result = classify(request, provider, "fake")
    assert result.primary_category_code is None
    assert result.confidence == "Preface"
