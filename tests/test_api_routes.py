from academic_insight_ai.apis.classification import app as classification_app
from academic_insight_ai.apis.reader import app as reader_app


def test_apis_are_separate_and_expose_expected_routes() -> None:
    classification_routes = {route.path for route in classification_app.routes}
    reader_routes = {route.path for route in reader_app.routes}

    assert "/v1/papers/classify" in classification_routes
    assert "/v1/papers/classify" not in reader_routes
    assert "/v1/papers/extract" in reader_routes
    assert "/v1/papers/summarize" in reader_routes
    assert all(not path.startswith("/v1/papers/doi") for path in reader_routes)
    assert "/v1/papers/extract" not in classification_routes


def test_api_key_is_required(monkeypatch) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        require_api_key(None)
    assert exc.value.status_code == 503

    monkeypatch.setenv("AI_API_KEY", "secret")
    with pytest.raises(HTTPException) as exc:
        require_api_key("wrong")
    assert exc.value.status_code == 401
    assert require_api_key("secret") is None
import pytest
from fastapi import HTTPException

from academic_insight_ai.apis.common import require_api_key
