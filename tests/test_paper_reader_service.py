from academic_insight_ai.tasks.paper_reader.service import (
    DOI_RE,
    SummaryRequest,
    _find_doi_candidates,
    _find_header_authors,
    _find_labeled_abstract,
    _find_trusted_doi,
    _content_chunks,
    summarize,
)
from academic_insight_ai.models.types import GenerateResponse


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


def test_full_text_chunking_keeps_all_content() -> None:
    content = "a" * 50_000
    chunks = _content_chunks(content, max_chunks=3)
    assert "".join(chunks) == content
    assert len(chunks) <= 3
