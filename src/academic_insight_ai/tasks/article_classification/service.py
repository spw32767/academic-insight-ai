from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from academic_insight_ai.core.validation import extract_json_object
from academic_insight_ai.models.types import GenerateRequest
from academic_insight_ai.tasks.article_classification.fewshot_examples import BOUNDARY_EXAMPLES, EXAMPLES

CLASSIFIER_VERSION = "evidence-first-v1"
AGREEMENT_CLASSIFIER_VERSION = "evidence-agreement-v1"
LEGACY_CLASSIFIER_VERSION = "legacy-v1"
ASTRA_CANDIDATE_VERSION = "astra-boundaries-v1"
FEWSHOT_CANDIDATE_VERSION = "astra-fewshot-v1"
BOUNDARY_CANDIDATE_VERSION = "astra-boundary-examples-v2"


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
    verification_mode: Literal["legacy", "single", "evidence_agreement", "astra_candidate", "fewshot_candidate", "boundary_candidate"] = "legacy"
    confidence_policy: Literal["model_reported", "conservative_cap"] = "model_reported"

    @field_validator("categories")
    @classmethod
    def unique_codes(cls, value: list[CategoryDefinition]) -> list[CategoryDefinition]:
        codes = [item.code for item in value]
        if len(codes) != len(set(codes)):
            raise ValueError("category codes must be unique")
        return value


class ClassificationAssessment(BaseModel):
    pass_number: int
    category_code: str | None
    confidence: Literal["High", "Medium", "Low", "Preface"]
    evidence_quote: str
    primary_contribution: str
    reason: str


class ClassificationResult(BaseModel):
    paper_id: str | int | None = None
    primary_category_code: str | None
    confidence: Literal["High", "Medium", "Low", "Preface"]
    confidence_source: str = "evidence_and_independent_agreement"
    model_reported_confidence: Literal["High", "Medium", "Low", "Preface"] | None = None
    reason: str = Field(min_length=1, max_length=2000)
    model: str
    taxonomy_version: str
    classifier_version: str = CLASSIFIER_VERSION
    verification_status: Literal["legacy", "single_validated", "agreed", "needs_review", "rule_based"] = "needs_review"
    primary_contribution: str | None = None
    evidence_quote: str | None = None
    evidence_source: Literal["abstract", "content", "keywords"] | None = None
    candidate_category_codes: list[str] = Field(default_factory=list)
    assessments: list[ClassificationAssessment] = Field(default_factory=list)


class _Decision(BaseModel):
    primary_category_code: str | None
    confidence: Literal["High", "Medium", "Low", "Preface"]
    primary_contribution: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(max_length=500)
    reason: str = Field(min_length=1, max_length=2000)


def _source(request: ClassificationRequest) -> tuple[str, str]:
    if (request.abstract or "").strip():
        return "abstract", request.abstract.strip()[:50000]
    if (request.content or "").strip():
        return "content", request.content.strip()[:50000]
    keywords = request.authkeywords or ""
    if isinstance(keywords, list):
        keywords = "; ".join(str(item) for item in keywords)
    return "keywords", str(keywords).strip()


def _schema(allowed: set[str]) -> dict[str, Any]:
    return {"type": "object", "properties": {
        "primary_category_code": {"type": ["string", "null"], "enum": sorted(allowed) + [None]},
        "confidence": {"type": "string", "enum": ["High", "Medium", "Low", "Preface"]},
        "primary_contribution": {"type": "string"},
        "evidence_quote": {"type": "string"},
        "reason": {"type": "string"},
    }, "required": ["primary_category_code", "confidence", "primary_contribution", "evidence_quote", "reason"],
        "additionalProperties": False}


def _prompt(request: ClassificationRequest, pass_number: int, correction: str | None = None) -> str:
    source_name, source = _source(request)
    categories = request.categories if pass_number == 1 else list(reversed(request.categories))
    taxonomy = json.dumps([item.model_dump(exclude_none=True) for item in categories], ensure_ascii=False)
    task = (
        "First identify the paper's primary contribution from the source and select its category."
        if pass_number == 1 else
        "Independently assess the central contribution and best category. Do not assume any previous classification."
    )
    return (
        f"{task} Return only JSON with primary_category_code, confidence, primary_contribution, evidence_quote, reason. "
        "Copy a short, exact, contiguous evidence_quote from SOURCE, preferably 20-250 characters; "
        "do not paraphrase, add ellipses, or quote the title. Classify by primary contribution, not keyword frequency. "
        "A new AI method is AI Algorithms; established AI deployed in a domain is Applied AI. "
        "Proofs and model checking are Theoretical CS. Quantum Information requires quantum computing, "
        "information, communication, or cryptography; chemical spectroscopy and classical quantum-inspired "
        "methods do not qualify. Distinguish IoT protocol/security work from hardware/device work. "
        "If genuinely outside the taxonomy or too little evidence exists, return null category, Preface, "
        "and an empty evidence_quote. Do not force a category. For a category use High only if clearly "
        "supported, Medium for plausible alternatives, Low for thin evidence.\n"
        f"Taxonomy: {taxonomy}\nTitle: {request.title}\n"
        f"Author keywords: {json.dumps(request.authkeywords or [], ensure_ascii=False)}\n"
        f"SOURCE ({source_name}): {source}\n"
        + (f"Previous output was invalid: {correction[:350]}. Correct it.\n" if correction else "")
    )


def _legacy_prompt(request: ClassificationRequest, correction: str | None = None) -> str:
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


def _astra_candidate_prompt(request: ClassificationRequest, correction: str | None = None) -> str:
    """A development-set hypothesis, kept opt-in until held-out evaluation."""
    categories = [item.model_dump(exclude_none=True) for item in request.categories]
    keywords = request.authkeywords or []
    source = request.abstract or request.content or ""
    return (
        "Classify this research record by its MAIN contribution, using the abstract first. "
        "Return JSON only: primary_category_code, confidence, reason. Use a code from the taxonomy or null. "
        "Do not infer a new AI algorithm just because a paper trains, tunes, hybridizes, compares, or names "
        "CNN, Transformer, BERT, LLM, SMOTE, GAN, transfer learning, or an optimizer. If the main result is "
        "performance on a specific real-world task or dataset, prefer APPLIED_AI. Use AI_ALGORITHMS only "
        "when the reusable method, learning mechanism, or general architecture is the main research result. "
        "For network, security, and distributed system papers, classify by the SYSTEM problem even if "
        "ML/AI or optimization solves it: routing, offloading, wireless communication, caching, "
        "blockchain, access control, federated infrastructure, intrusion, latency, or throughput "
        "usually means NETWORKS_SECURITY_DISTRIBUTED. A UAV, IoT, MEC, or sensor setting alone "
        "does not make COMPUTER_ENGINEERING_IOT_EMBEDDED; use that category when hardware, an "
        "embedded device, or physical implementation is central. "
        "QUANTUM_INFORMATION requires actual quantum information, computing, communication, or "
        "cryptography; terms such as NOMA, secrecy, expectation maximization, and vector message "
        "passing are not quantum evidence. THEORETICAL_CS requires a formal mathematical, "
        "algorithmic complexity, proof, or verification result as the primary contribution. "
        "EDTECH_LEARNING_DIGITAL_LIBRARY requires a teaching, learning, or digital-library contribution, "
        "not merely educational documents used in a security system. "
        "Return null/Preface for nonresearch notices, no substantive abstract or keywords, or a paper "
        "truly outside all seven categories. For an assigned category: High only if its primary "
        "contribution and boundary against plausible alternatives are explicit; Medium if the main "
        "category is defensible but another is plausible; Low if evidence is thin. "
        "If category is null confidence must be Preface; otherwise confidence must be High, Medium, or Low. "
        "Do not claim certainty from a model name or domain keyword alone.\n"
        f"Taxonomy: {json.dumps(categories, ensure_ascii=False)}\n"
        f"Title: {request.title}\nAuthor keywords: {json.dumps(keywords, ensure_ascii=False)}\n"
        f"Abstract or content: {source[:50000]}\n"
        + (f"Validation error: {correction[:500]}" if correction else "")
    )


def _fewshot_candidate_prompt(request: ClassificationRequest, correction: str | None = None,
                              *, boundary: bool = False) -> str:
    categories = [item.model_dump(exclude_none=True) for item in request.categories]
    selected_examples = BOUNDARY_EXAMPLES if boundary else EXAMPLES
    examples = "\n".join(
        f"- Title: {title}; evidence: {quote}; category: {code or 'null'}; "
        f"why: {why}"
        for _, title, quote, code, why in selected_examples
    )
    return (
        "Classify the MAIN research contribution using the abstract first, title and author keywords second. "
        "Return one JSON object with only primary_category_code, confidence, reason. "
        "Use one supplied category code, or null with Preface for a nonresearch item, too little evidence, "
        "or genuinely out-of-taxonomy research. A specific task solved with familiar AI is usually APPLIED_AI; "
        "a reusable new learning method is AI_ALGORITHMS. "
        + ("A new architecture, representation, or learning mechanism remains AI_ALGORITHMS even when "
           "tested in healthcare or another application. Tuning or comparing existing models for one task "
           "is APPLIED_AI. " if boundary else "")
        + "In a network paper, classify the network problem "
        "even when AI is used to solve it. Hardware implementation belongs in COMPUTER_ENGINEERING_IOT_EMBEDDED. "
        "High means the primary contribution and its boundary are clear; Medium means a second category remains "
        "plausible; Low means evidence is thin. Do not infer confidence from the examples. "
        "Examples below are from other papers; classify the CURRENT paper independently:\n"
        f"{examples}\n"
        f"Taxonomy: {json.dumps(categories, ensure_ascii=False)}\n"
        f"CURRENT title: {request.title}\n"
        f"CURRENT author keywords: {json.dumps(request.authkeywords or [], ensure_ascii=False)}\n"
        f"CURRENT abstract or content: {(request.abstract or request.content or '')[:50000]}\n"
        + (f"Validation error: {correction[:500]}" if correction else "")
    )


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold().strip()


def _validate(payload: dict[str, Any], allowed: set[str], source: str) -> _Decision:
    decision = _Decision.model_validate(payload)
    code = decision.primary_category_code
    if decision.confidence == "Preface":
        if code is not None:
            raise ValueError("Preface requires a null category")
        return decision
    if code not in allowed:
        raise ValueError("category outside taxonomy")
    quote = _normalized(decision.evidence_quote)
    if len(quote) < 12 or quote not in _normalized(source):
        raise ValueError("evidence_quote is not an exact source excerpt or is too short")
    if code == "QUANTUM_INFORMATION" and not re.search(
        r"\b(qkd|pqc|qubit|qudit|quantum (?:comput|inform|communicat|cryptograph|key|circuit|algorithm|network|machine learning|simulat)|post.quantum)\w*",
        _normalized(source), re.IGNORECASE,
    ):
        raise ValueError("Quantum Information has no explicit quantum-information evidence")
    return decision


def _decide(request: ClassificationRequest, provider: Any, model_name: str, pass_number: int) -> _Decision:
    allowed = {item.code for item in request.categories}
    _, source = _source(request)
    error: Exception | None = None
    for _ in range(2):
        response = provider.generate(GenerateRequest(
            model_name=model_name, prompt=_prompt(request, pass_number, str(error) if error else None),
            json_schema=_schema(allowed), num_predict=600,
        ))
        try:
            return _validate(extract_json_object(response.text), allowed, source)
        except (ValueError, TypeError, ValidationError) as exc:
            error = exc
    raise ValueError(f"Model output failed validation on pass {pass_number}: {error}")


def _review(request: ClassificationRequest, model_name: str, reason: str,
            status: Literal["needs_review", "rule_based"] = "needs_review",
            candidates: list[str] | None = None,
            assessments: list[ClassificationAssessment] | None = None) -> ClassificationResult:
    return ClassificationResult(
        paper_id=request.paper_id, primary_category_code=None, confidence="Preface",
        reason=reason, model=model_name, taxonomy_version=request.taxonomy_version,
        classifier_version=(AGREEMENT_CLASSIFIER_VERSION if request.verification_mode == "evidence_agreement"
                            else LEGACY_CLASSIFIER_VERSION if request.verification_mode == "legacy"
                            else CLASSIFIER_VERSION),
        confidence_source="rule_based" if status == "rule_based" else "model_review",
        verification_status=status, candidate_category_codes=candidates or [],
        assessments=assessments or [],
    )


def _assessment(number: int, decision: _Decision) -> ClassificationAssessment:
    return ClassificationAssessment(
        pass_number=number, category_code=decision.primary_category_code,
        confidence=decision.confidence, evidence_quote=decision.evidence_quote,
        primary_contribution=decision.primary_contribution, reason=decision.reason,
    )


def _classify_legacy(request: ClassificationRequest, provider: Any, model_name: str) -> ClassificationResult:
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
        prompt_builder = ((lambda r, e: _fewshot_candidate_prompt(r, e, boundary=True))
                          if request.verification_mode == "boundary_candidate"
                          else _fewshot_candidate_prompt if request.verification_mode == "fewshot_candidate"
                          else _astra_candidate_prompt if request.verification_mode == "astra_candidate"
                          else _legacy_prompt)
        prompt = prompt_builder(request, str(error) if correction and error else None)
        response = provider.generate(GenerateRequest(model_name=model_name, prompt=prompt, json_mode=True))
        try:
            payload = extract_json_object(response.text)
            primary = payload.get("primary_category_code")
            confidence = payload.get("confidence")
            if confidence == "Preface" and primary is not None:
                if request.verification_mode in ("astra_candidate", "fewshot_candidate", "boundary_candidate"):
                    primary = None
                    payload["reason"] = (
                        "Model requested review with an inconsistent category; category cleared. "
                        + str(payload.get("reason") or "")
                    )
                else:
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


def _classify_impl(request: ClassificationRequest, provider: Any, model_name: str) -> ClassificationResult:
    if request.verification_mode in ("legacy", "astra_candidate", "fewshot_candidate", "boundary_candidate"):
        result = _classify_legacy(request, provider, model_name)
        if request.verification_mode == "boundary_candidate":
            # This is a deliberately conservative interim cap, not a calibrated probability.
            return result.model_copy(update={
                "confidence": "Medium" if result.confidence == "High" else result.confidence,
                "model_reported_confidence": result.confidence,
                "confidence_source": "conservative_cap_pending_independent_validation",
                "classifier_version": BOUNDARY_CANDIDATE_VERSION,
                "verification_status": "legacy",
            })
        return result.model_copy(update={
            "confidence_source": "model_reported", "classifier_version":
            ASTRA_CANDIDATE_VERSION if request.verification_mode == "astra_candidate" else
            FEWSHOT_CANDIDATE_VERSION if request.verification_mode == "fewshot_candidate" else LEGACY_CLASSIFIER_VERSION,
            "verification_status": "legacy",
        })
    source_name, source = _source(request)
    if request.title.strip().lower().startswith(("preface", "editorial", "correction", "erratum", "retraction notice")):
        return _review(request, model_name, "Non-research publication type; review required.", "rule_based")
    if not source:
        return _review(request, model_name, "No abstract, content, or keywords establish a contribution.", "rule_based")
    try:
        first = _decide(request, provider, model_name, 1)
        second = _decide(request, provider, model_name, 2) if request.verification_mode == "evidence_agreement" else None
    except ValueError as exc:
        return _review(request, model_name, f"Model evidence could not be validated: {exc}")
    if second is None:
        if first.primary_category_code is None:
            return _review(request, model_name, f"Assessment requests review: {first.reason}",
                           assessments=[_assessment(1, first)])
        return ClassificationResult(
            paper_id=request.paper_id, primary_category_code=first.primary_category_code,
            confidence=first.confidence, confidence_source="model_reported_with_validated_quote",
            reason=first.reason, model=model_name, taxonomy_version=request.taxonomy_version,
            classifier_version=CLASSIFIER_VERSION, verification_status="single_validated",
            primary_contribution=first.primary_contribution, evidence_quote=first.evidence_quote,
            evidence_source=source_name, candidate_category_codes=[first.primary_category_code],
            assessments=[_assessment(1, first)],
        )
    assessments = [_assessment(1, first), _assessment(2, second)]
    candidates = list(dict.fromkeys(code for code in (first.primary_category_code, second.primary_category_code) if code))
    if first.primary_category_code != second.primary_category_code:
        return _review(request, model_name,
                       "Independent classifications disagree; review the evidence before assigning a category.",
                       candidates=candidates, assessments=assessments)
    if first.primary_category_code is None:
        return _review(request, model_name, f"Both assessments request review: {first.reason}",
                       assessments=assessments)
    confidence_order = {"Low": 0, "Medium": 1, "High": 2}
    confidence = min((first.confidence, second.confidence), key=confidence_order.__getitem__)
    return ClassificationResult(
        paper_id=request.paper_id, primary_category_code=first.primary_category_code,
        confidence=confidence, reason=f"Agreement across two independent assessments. {first.reason}",
        model=model_name, taxonomy_version=request.taxonomy_version,
        classifier_version=AGREEMENT_CLASSIFIER_VERSION,
        verification_status="agreed", primary_contribution=first.primary_contribution,
        evidence_quote=first.evidence_quote, evidence_source=source_name,
        candidate_category_codes=candidates, assessments=assessments,
    )


def classify(request: ClassificationRequest, provider: Any, model_name: str) -> ClassificationResult:
    result = _classify_impl(request, provider, model_name)
    if request.confidence_policy != "conservative_cap" or result.confidence == "Preface":
        return result
    return result.model_copy(update={
        "model_reported_confidence": result.model_reported_confidence or result.confidence,
        "confidence": "Medium" if result.confidence == "High" else result.confidence,
        "confidence_source": "conservative_cap_pending_independent_validation",
    })
