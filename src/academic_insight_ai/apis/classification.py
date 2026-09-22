from __future__ import annotations

import uvicorn
from fastapi import Depends, FastAPI, HTTPException

from academic_insight_ai.apis.common import build_provider, get_config, require_api_key
from academic_insight_ai.tasks.article_classification.service import (
    ClassificationRequest,
    ClassificationResult,
    classify,
)

app = FastAPI(title="Paper Classification API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "paper-classification"}


@app.post("/v1/papers/classify", response_model=ClassificationResult, dependencies=[Depends(require_api_key)])
def classify_paper(request: ClassificationRequest) -> ClassificationResult:
    model_id = request.model or get_config().classification_model
    try:
        provider, model_name = build_provider(model_id)
        return classify(request, provider, model_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model provider failed: {exc}") from exc


def run() -> None:
    config = get_config()
    import os
    uvicorn.run(app, host=os.getenv("CLASSIFICATION_API_HOST", "127.0.0.1"), port=int(os.getenv("CLASSIFICATION_API_PORT", "8101")))
