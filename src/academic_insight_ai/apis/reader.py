from __future__ import annotations

import os

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

from academic_insight_ai.apis.common import build_provider, get_config, require_api_key
from academic_insight_ai.tasks.paper_reader.service import (
    ExtractedPaper,
    SummaryRequest,
    SummaryResult,
    SDGSuggestionRequest,
    SDGSuggestionResult,
    extract_pdf,
    summarize,
    suggest_sdg,
)

app = FastAPI(title="Paper Reader API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "paper-reader"}


@app.post("/v1/papers/extract", response_model=ExtractedPaper, dependencies=[Depends(require_api_key)])
async def extract(file: UploadFile = File(...)) -> ExtractedPaper:
    config = get_config()
    try:
        data = await file.read(config.max_pdf_bytes + 1)
        provider, model_name = build_provider(config.reader_model)
        return extract_pdf(
            data,
            provider,
            model_name,
            max_bytes=config.max_pdf_bytes,
            max_pages=config.max_pdf_pages,
            ocrmypdf_command=config.ocrmypdf_command,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Paper reader failed: {exc}") from exc


@app.post("/v1/papers/summarize", response_model=SummaryResult, dependencies=[Depends(require_api_key)])
def summarize_paper(request: SummaryRequest) -> SummaryResult:
    config = get_config()
    try:
        provider, model_name = build_provider(request.model or config.reader_model)
        return summarize(request, provider, model_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model provider failed: {exc}") from exc


@app.post("/v1/papers/suggest-sdg", response_model=SDGSuggestionResult, dependencies=[Depends(require_api_key)])
def suggest_paper_sdg(request: SDGSuggestionRequest) -> SDGSuggestionResult:
    config = get_config()
    try:
        provider, model_name = build_provider(config.reader_model)
        return suggest_sdg(request, provider, model_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model provider failed: {exc}") from exc


def run() -> None:
    config = get_config()
    uvicorn.run(app, host=os.getenv("READER_API_HOST", "127.0.0.1"), port=int(os.getenv("READER_API_PORT", "8102")))
