from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from academic_insight_ai.core.validation import extract_json_object
from academic_insight_ai.models.types import GenerateRequest


class CategoryDefinition(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ClassificationRequest(BaseModel):
    paper_id: str | int | None = None
    title: str = Field(min_length=1, max_length=2000)
    abstract: str | None = Field(default=None, max_length=100_000)
    authkeywords: str | list[str] | None = None
    content: str | None = Field(default=None, max_length=200_000)
    categories: list[CategoryDefinition] = Field(min_length=1, max_length=200)
    taxonomy_version: str = Field(default="1", max_length=64)
    model: str | None = None

    @field_validator("categories")
    @classmethod
    def unique_codes(cls, value: list[CategoryDefinition]) -> list[CategoryDefinition]:
        codes = [item.code for item in value]
        if len(codes) != len(set(codes)):
            raise ValueError("category codes must be unique")
        return value


class ClassificationResult(BaseModel):
    paper_id: str | int | None = None
    primary_category_code: str | None
    confidence: Literal["High", "Medium", "Low", "Preface"]
    confidence_source: str = "model_reported"
    reason: str = Field(min_length=1, max_length=2000)
    model: str
    taxonomy_version: str


def _prompt(request: ClassificationRequest, correction: str | None = None) -> str:
    categories = [item.model_dump(exclude_none=True) for item in request.categories]
    source = request.abstract or request.content or ""
    keywords = request.authkeywords or []
    prefix = "Reconsider your previous response carefully. " if correction else ""
    return (
        f"{prefix}Classify the academic paper into exactly one primary category using only the supplied taxonomy. "
        "Classify by the paper's primary contribution, not by keyword counting. Use the abstract as primary evidence "
        "and the title and author keywords as supporting evidence. Return one JSON object only with keys "
        "primary_category_code, confidence, reason. Confidence must be exactly High, Medium, Low, or Preface. "
        "Use High when one category is clearly supported, Medium when two or more categories are plausible but a "
        "primary contribution is identifiable, and Low when evidence is limited or the closest category must be used. "
        "If the record is a preface, editorial, correction, erratum, retraction, or lacks enough evidence to "
        "identify a research contribution, return primary_category_code null and confidence Preface. "
        "Preface also applies when a substantive research article is genuinely outside all seven categories; "
        "do not use it merely because the paper combines methods or is domain-specific. Applied AI includes "
        "applications of AI in healthcare, but does not include healthcare papers without AI. Quantum "
        "Information excludes chemical spectroscopy or quantum physics without an information-science contribution. "
        "Do not force a category from a generic title alone. For Preface, explain why review is needed. "
        "Use no category code outside the taxonomy and do not add markdown.\n"
        "Tie-breaking rules, in priority order:\n"
        "1. Genuine quantum information, qubits, circuits, quantum communication, quantum or post-quantum cryptography, or quantum algorithms -> Quantum Information Science.\n"
        "2. Theorems, proofs, formal verification, model checking, computability, or complexity -> Theoretical Computer Science.\n"
        "3. A new AI/ML algorithm, optimization method, model, or learning architecture -> AI Algorithms and Intelligent Systems.\n"
        "4. Established AI applied to healthcare, agriculture, smart cities, geospatial, or operational systems -> Applied AI, GeoAI and Agentic Applications.\n"
        "5. Protocols, routing, cybersecurity, authentication, encryption, blockchain, federated learning, cloud-edge, latency, or throughput -> Networks, Security, and Distributed Systems.\n"
        "6. Hardware, FPGA, embedded platforms, IoT devices, sensors, robotics, firmware, or device implementation -> Computer Engineering, IoT, and Embedded Systems.\n"
        "7. Learning, education, students, teaching, educational analytics, or digital libraries -> Educational Technology, Learning Sciences, and Digital Library Systems.\n"
        "8. Educational work whose primary contribution is a new AI algorithm uses the AI Algorithms category.\n"
        "9. IoT protocol/security/performance work uses Networks; IoT device/sensor/hardware work uses Computer Engineering.\n"
        "10. Quantum-inspired work running entirely on classical hardware uses AI Algorithms rather than Quantum Information.\n"
        f"Taxonomy: {json.dumps(categories, ensure_ascii=False)}\n"
        f"Title: {request.title}\nAuthor keywords: {json.dumps(keywords, ensure_ascii=False)}\n"
        f"Abstract or content: {source[:50000]}\n"
        + (f"Validation error: {correction[:500]}" if correction else "")
    )


def classify(request: ClassificationRequest, provider: Any, model_name: str) -> ClassificationResult:
    allowed = {item.code for item in request.categories}
    title = request.title.strip()
    evidence = (request.abstract or request.content or "").strip()
    keywords = request.authkeywords or []
    if isinstance(keywords, str):
        keywords = keywords.strip()
    if title.lower().startswith(("preface", "editorial", "correction", "erratum", "retraction notice")):
        return ClassificationResult(
            paper_id=request.paper_id, primary_category_code=None, confidence="Preface",
            reason="Non-research publication type; human review required.",
            model=model_name, taxonomy_version=request.taxonomy_version,
        )
    if not evidence and not keywords:
        return ClassificationResult(
            paper_id=request.paper_id, primary_category_code=None, confidence="Preface",
            reason="No abstract or author keywords to establish the primary research contribution.",
            model=model_name, taxonomy_version=request.taxonomy_version,
        )
    error: Exception | None = None
    for correction in (None, "retry"):
        prompt = _prompt(request, str(error) if correction and error else None)
        response = provider.generate(GenerateRequest(model_name=model_name, prompt=prompt, json_mode=True))
        try:
            payload = extract_json_object(response.text)
            primary = payload.get("primary_category_code")
            confidence = payload.get("confidence")
            if confidence == "Preface" and primary is not None:
                raise ValueError("Preface requires a null category")
            if confidence != "Preface" and primary not in allowed:
                raise ValueError("primary_category_code is outside taxonomy")
            result = ClassificationResult(
                paper_id=request.paper_id,
                primary_category_code=primary,
                confidence=confidence,
                reason=payload.get("reason"),
                model=model_name,
                taxonomy_version=request.taxonomy_version,
            )
            return result
        except (ValueError, TypeError, ValidationError) as exc:
            error = exc
    raise ValueError(f"Model output failed validation after retry: {error}")
