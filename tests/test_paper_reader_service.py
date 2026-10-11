from academic_insight_ai.tasks.paper_reader.service import (
    DOI_RE,
    SummaryRequest,
    SDGSuggestionRequest,
    SDGOption,
    _find_doi_candidates,
    _find_header_authors,
    _find_labeled_abstract,
    _find_trusted_doi,
    _find_page_numbers,
    _find_publication_month,
    _find_volume_issue,
    _content_chunks,
    extract_pdf,
    summarize,
    suggest_sdg,
)
from academic_insight_ai.models.types import GenerateResponse
import pytest


class FakeProvider:
    def generate(self, request):
        return GenerateResponse(text='{"summary_th":"บทความนี้นำเสนอวิธีการใหม่"}', raw={})


def test_doi_pattern_finds_common_doi() -> None:
    assert DOI_RE.findall("DOI: 10.1016/j.example.2024.01.001") == ["10.1016/j.example.2024.01.001"]


def test_doi_detection_repairs_split_publisher_prefix_and_prioritizes_header() -> None:
    text = (
        "Digital Object Identifier 10.1 109/ACCESS.2018.2853669\n"
        "References include 10.5176/2251-2217_SEA39."
    )
    assert _find_doi_candidates(text, {}) == [
        "10.1109/access.2018.2853669",
        "10.5176/2251-2217_sea39",
    ]


def test_doi_detection_uses_pdf_metadata_before_reference_list() -> None:
    text = "References include 10.5176/2251-2217_SEA39."
    metadata = {"/Subject": "IEEE Access;10.1109/ACCESS.2019.2892958"}
    assert _find_doi_candidates(text, metadata)[0] == "10.1109/access.2019.2892958"


def test_trusted_doi_ignores_reference_only_doi() -> None:
    assert _find_trusted_doi("References include 10.1000/reference-only", {}) is None


def test_labeled_abstract_stops_before_index_terms() -> None:
    text = "ABSTRACT  This is the paper abstract.\nIt has two lines.\nINDEX TERMS BPMN, verification"
    assert _find_labeled_abstract(text) == "This is the paper abstract. It has two lines."


def test_header_author_detection_reads_ieee_author_line() -> None:
    text = "Paper title\nC. DECHSUPA, W. VATANAWOOD, AND A. THONGTAK\nDepartment\nABSTRACT text"
    assert _find_header_authors(text) == ["C. DECHSUPA", "W. VATANAWOOD", "A. THONGTAK"]


def test_summary_prefers_abstract() -> None:
    result = summarize(SummaryRequest(abstract="abstract", content="full text"), FakeProvider(), "fake")
    assert result.source_type == "abstract"
    assert result.summary_th.startswith("บทความ")


def test_summary_can_prepare_translation_with_abstract() -> None:
    class TranslationProvider:
        def generate(self, request):
            assert "translation_th" in request.prompt
            return GenerateResponse(text='{"summary_th":"สรุปย่อ","translation_th":"คำแปลเต็ม"}', raw={})

    result = summarize(SummaryRequest(abstract="Original abstract", include_translation=True), TranslationProvider(), "fake")
    assert result.summary_th == "สรุปย่อ"
    assert result.translation_th == "คำแปลเต็ม"


def test_sdg_suggestion_uses_paper_purpose_and_reports_closest_choice() -> None:
    class SDGProvider:
        def generate(self, request):
            assert "Paper content: The study evaluates classroom learning outcomes" in request.prompt
            assert "generic technology terms" in request.prompt
            return GenerateResponse(
                text='{"sdg_number":4,"reason_th":"ศึกษาผลสัมฤทธิ์การเรียนรู้",' \
                     '"relationship":"closest"}', raw={},
            )

    result = suggest_sdg(
        SDGSuggestionRequest(
            title="Learning outcomes", abstract="The study evaluates classroom learning outcomes",
            sdgs=[SDGOption(sdg_number=4, name_th="การศึกษาที่มีคุณภาพ", name_en="Quality Education")],
        ),
        SDGProvider(), "fake",
    )
    assert result.sdg_number == 4
    assert result.relationship == "closest"
    assert result.reason_th == "ศึกษาผลสัมฤทธิ์การเรียนรู้"


def test_sdg_suggestion_rejects_number_outside_active_options() -> None:
    class InvalidProvider:
        def generate(self, request):
            return GenerateResponse(
                text='{"sdg_number":9,"reason_th":"ทั่วไป","relationship":"direct"}', raw={},
            )

    with pytest.raises(ValueError, match="outside the available options"):
        suggest_sdg(
            SDGSuggestionRequest(
                title="Paper", abstract="Study of school learning",
                sdgs=[SDGOption(sdg_number=4, name_th="การศึกษา", name_en="Education")],
            ),
            InvalidProvider(), "fake",
        )


def test_ieee_header_fields_require_explicit_publication_evidence() -> None:
    text = (
        "date of publication July 6, 2018.\nABSTRACT Paper text INDEX TERMS BPMN\n"
        "VOLUME 6, 2018\n38421\n\f\nConclusion\n38422 VOLUME 6, 2018"
    )
    assert _find_publication_month(text) == "07"
    assert _find_volume_issue(text) == "Vol. 6"
    assert _find_page_numbers(text, 2) == "38421-38422"
    assert _find_page_numbers(text.replace("38422", "38430"), 2) is None


def test_non_paper_pdf_is_rejected_before_metadata_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "academic_insight_ai.tasks.paper_reader.service._read_pdf",
        lambda *_: ("Administrative application form. " * 20, 1, {"/Title": "Application form"}),
    )

    class NeverCalledProvider:
        def generate(self, request):
            raise AssertionError("metadata model should not run for an obvious non-paper")

    with pytest.raises(ValueError, match="ไม่พบลักษณะของบทความวิจัย"):
        extract_pdf(
            b"%PDF-1.4\n", NeverCalledProvider(), "fake", max_bytes=1000, max_pages=10,
            ocrmypdf_command="ocrmypdf",
        )


def test_full_text_chunking_keeps_all_content() -> None:
    content = "a" * 50_000
    chunks = _content_chunks(content, max_chunks=3)
    assert "".join(chunks) == content
    assert len(chunks) <= 3


def test_scanned_pdf_ignores_generic_metadata_title(monkeypatch) -> None:
    calls = 0

    def read_pdf(_path, _max_pages):
        nonlocal calls
        calls += 1
        if calls == 1:
            return "", 1, {"/Title": "untitled"}
        return (
            "Digital Object Identifier 10.1109/ACCESS.2018.2853669\n"
            "Transformation of the BPMN Design Model into a Colored Petri Net\n"
            "ABSTRACT This paper proposes a transformation framework for BPMN design models. "
            + "It supports formal verification of large models. " * 4
            + "INDEX TERMS BPMN, verification",
            1,
            {"/Title": "untitled"},
        )

    class MetadataProvider:
        def generate(self, request):
            return GenerateResponse(
                text='{"title":"Transformation of the BPMN Design Model into a Colored Petri Net",'
                     '"doi":"10.1109/ACCESS.2018.2853669","authors":[],"publication_year":2018,'
                     '"journal_name":"IEEE Access"}',
                raw={},
            )

    monkeypatch.setattr("academic_insight_ai.tasks.paper_reader.service._read_pdf", read_pdf)
    monkeypatch.setattr("academic_insight_ai.tasks.paper_reader.service._run_ocr", lambda *_: None)
    result = extract_pdf(
        b"%PDF-1.4\n", MetadataProvider(), "fake", max_bytes=1000, max_pages=10,
        ocrmypdf_command="ocrmypdf",
    )
    assert calls == 2
    assert result.ocr_used is True
    assert result.title == "Transformation of the BPMN Design Model into a Colored Petri Net"
    assert result.doi == "10.1109/access.2018.2853669"
