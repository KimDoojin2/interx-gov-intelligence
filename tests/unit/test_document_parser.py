# tests/unit/test_document_parser.py
"""OCR document_parser 단위 + 실전 추출 테스트. (180건 → 196건+)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from interx_engine.infrastructure.ocr.document_parser import (
    ExtractionResult,
    extract_text,
    extract_pdf_pdfplumber,
    extract_pdf_pypdf,
    extract_docx,
    extract_hwp,
    extract_from_attachments,
    _extract_text_from_hwp_binary,
    SUPPORTED_EXTENSIONS,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


# ═══════════════════════════════════════════════════════════════════════════════
#  ExtractionResult
# ═══════════════════════════════════════════════════════════════════════════════
class TestExtractionResult:
    def test_success_when_long_text(self):
        r = ExtractionResult(text="a" * 30, method="test")
        assert r.success is True

    def test_failure_when_short_text(self):
        r = ExtractionResult(text="hello", method="test")
        assert r.success is False

    def test_failure_when_empty(self):
        r = ExtractionResult(text="", method="test", error="empty")
        assert r.success is False

    def test_tables_default_empty(self):
        r = ExtractionResult(text="x", method="m")
        assert r.tables == []

    def test_repr_contains_method(self):
        r = ExtractionResult(text="abc", method="pdfplumber", pages=3)
        assert "pdfplumber" in repr(r)
        assert "pages=3" in repr(r)


# ═══════════════════════════════════════════════════════════════════════════════
#  extract_text dispatcher
# ═══════════════════════════════════════════════════════════════════════════════
class TestExtractTextDispatcher:
    def test_unknown_extension_returns_error(self):
        result = extract_text(b"data", "file.xyz")
        assert result.success is False
        assert "지원하지 않는" in result.error

    def test_empty_bytes_returns_error(self):
        result = extract_text(b"", "test.pdf")
        assert result.success is False

    def test_pdf_extension_routes_to_pdf(self):
        result = extract_text(b"not a pdf", "test.pdf")
        assert result.success is False
        assert "지원하지 않는" not in (result.error or "")

    def test_doc_extension_unsupported(self):
        result = extract_text(b"data", "old.doc")
        assert result.success is False
        assert ".doc" in (result.error or "")

    def test_supported_extensions_set(self):
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".hwp" in SUPPORTED_EXTENSIONS
        assert ".hwpx" in SUPPORTED_EXTENSIONS
        assert ".doc" in SUPPORTED_EXTENSIONS


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF 에러 핸들링
# ═══════════════════════════════════════════════════════════════════════════════
class TestPdfErrorHandling:
    def test_pdfplumber_invalid_bytes(self):
        result = extract_pdf_pdfplumber(b"not a pdf")
        assert result.success is False

    def test_pypdf_invalid_bytes(self):
        result = extract_pdf_pypdf(b"not a pdf")
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF 실전 추출 (sample_notice.pdf)
# ═══════════════════════════════════════════════════════════════════════════════
class TestPdfRealExtraction:
    @pytest.fixture
    def pdf_bytes(self):
        f = FIXTURES / "sample_notice.pdf"
        if not f.exists():
            pytest.skip("sample_notice.pdf 없음 — tests/fixtures/generate_samples.py 먼저 실행")
        return f.read_bytes()

    def test_pdfplumber_extracts_korean(self, pdf_bytes):
        r = extract_pdf_pdfplumber(pdf_bytes)
        assert r.success is True
        assert r.method == "pdfplumber"
        assert r.pages >= 1
        assert "스마트공장" in r.text
        assert "지원사업" in r.text

    def test_pdfplumber_extracts_details(self, pdf_bytes):
        r = extract_pdf_pdfplumber(pdf_bytes)
        assert "사업목적" in r.text
        assert "지원대상" in r.text
        assert "지원금액" in r.text

    def test_pypdf_extracts_korean(self, pdf_bytes):
        r = extract_pdf_pypdf(pdf_bytes)
        assert r.success is True
        assert r.method == "pypdf"
        assert "스마트공장" in r.text

    def test_dispatcher_uses_pdfplumber_first(self, pdf_bytes):
        r = extract_text(pdf_bytes, "notice.pdf")
        assert r.success is True
        assert r.method == "pdfplumber"

    def test_text_length_within_limit(self, pdf_bytes):
        r = extract_pdf_pdfplumber(pdf_bytes)
        assert len(r.text) <= 8000


# ═══════════════════════════════════════════════════════════════════════════════
#  DOCX 실전 추출 (sample_notice.docx)
# ═══════════════════════════════════════════════════════════════════════════════
class TestDocxRealExtraction:
    @pytest.fixture
    def docx_bytes(self):
        f = FIXTURES / "sample_notice.docx"
        if not f.exists():
            pytest.skip("sample_notice.docx 없음")
        return f.read_bytes()

    def test_docx_extracts_korean(self, docx_bytes):
        r = extract_docx(docx_bytes)
        assert r.success is True
        assert r.method == "docx"
        assert "제조 AI" in r.text or "AI" in r.text

    def test_docx_extracts_paragraphs(self, docx_bytes):
        r = extract_docx(docx_bytes)
        assert "사업목적" in r.text
        assert "지원대상" in r.text
        assert "품질검사" in r.text

    def test_docx_extracts_tables(self, docx_bytes):
        r = extract_docx(docx_bytes)
        # 테이블 셀 텍스트도 추출되어야 함
        assert "MES" in r.text or "ERP" in r.text
        assert "기본형" in r.text or "고도화형" in r.text

    def test_docx_via_dispatcher(self, docx_bytes):
        r = extract_text(docx_bytes, "공고문.docx")
        assert r.success is True
        assert r.method == "docx"

    def test_docx_invalid_bytes(self):
        r = extract_docx(b"not a docx file")
        assert r.success is False


# ═══════════════════════════════════════════════════════════════════════════════
#  HWP 바이너리 파서 실전 추출
# ═══════════════════════════════════════════════════════════════════════════════
class TestHwpBinaryParser:
    @pytest.fixture
    def hwp_section_bytes(self):
        f = FIXTURES / "sample_hwp_section.bin"
        if not f.exists():
            pytest.skip("sample_hwp_section.bin 없음")
        return f.read_bytes()

    def test_extracts_korean_from_records(self, hwp_section_bytes):
        text = _extract_text_from_hwp_binary(hwp_section_bytes)
        assert len(text) > 20
        assert "스마트공장" in text or "스마트팩토리" in text

    def test_extracts_multiple_paragraphs(self, hwp_section_bytes):
        text = _extract_text_from_hwp_binary(hwp_section_bytes)
        assert "사업목적" in text or "지원대상" in text
        assert "지원내용" in text or "MES" in text

    def test_skips_non_text_records(self, hwp_section_bytes):
        """비텍스트 레코드(tag_id != 67)는 건너뛰어야 함."""
        text = _extract_text_from_hwp_binary(hwp_section_bytes)
        # dummy 레코드의 \x00 바이트가 텍스트에 포함되면 안 됨
        assert "\x00" not in text

    def test_empty_data_returns_empty(self):
        text = _extract_text_from_hwp_binary(b"")
        assert text == ""

    def test_truncated_header_handles_gracefully(self):
        text = _extract_text_from_hwp_binary(b"\x01\x02")
        assert text == ""

    def test_hwp_full_extract_invalid(self):
        r = extract_hwp(b"not a hwp file")
        assert r.success is False


# ═══════════════════════════════════════════════════════════════════════════════
#  HWP record 직접 생성 테스트
# ═══════════════════════════════════════════════════════════════════════════════
class TestHwpRecordConstruction:
    def _make_record(self, tag_id, data):
        import struct
        size = len(data)
        if size >= 0xFFF:
            header = (tag_id & 0x3FF) | (0xFFF << 20)
            return struct.pack("<I", header) + struct.pack("<I", size) + data
        else:
            header = (tag_id & 0x3FF) | ((size & 0xFFF) << 20)
            return struct.pack("<I", header) + data

    def test_single_paragraph(self):
        text = "테스트 문장입니다 이것은 단위 테스트입니다."
        record = self._make_record(67, text.encode("utf-16-le"))
        result = _extract_text_from_hwp_binary(record)
        assert "테스트" in result
        assert "단위" in result

    def test_multiple_paragraphs(self):
        texts = ["첫 번째 문단입니다.", "두 번째 문단입니다.", "세 번째 문단입니다."]
        data = b""
        for t in texts:
            data += self._make_record(67, t.encode("utf-16-le"))
        result = _extract_text_from_hwp_binary(data)
        for t in texts:
            assert t[:4] in result

    def test_mixed_records_only_extracts_text(self):
        data = self._make_record(10, b"\x00" * 16)  # 비텍스트
        data += self._make_record(67, "정기공고 탐지 테스트 문장입니다.".encode("utf-16-le"))
        data += self._make_record(20, b"\xff" * 8)   # 비텍스트
        result = _extract_text_from_hwp_binary(data)
        assert "정기공고" in result
        assert len(result.split()) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
#  extract_from_attachments 배치 추출
# ═══════════════════════════════════════════════════════════════════════════════
class TestExtractFromAttachments:
    def test_empty_list(self):
        text, meta = extract_from_attachments([])
        assert text == ""
        assert meta == []

    def test_no_supported_extensions(self):
        items = [
            {"name": "image.png", "url": "https://example.com/image.png"},
            {"name": "photo.jpg", "url": "https://example.com/photo.jpg"},
        ]
        text, meta = extract_from_attachments(items)
        assert text == ""

    def test_missing_url_skipped(self):
        items = [{"name": "doc.pdf", "url": ""}]
        text, meta = extract_from_attachments(items)
        assert text == ""

    def test_max_files_zero(self):
        items = [{"name": "doc.pdf", "url": "https://example.com/doc.pdf"}]
        text, meta = extract_from_attachments(items, max_files=0)
        assert text == ""

    def test_logs_contain_metadata(self):
        """다운로드 실패해도 로그 엔트리가 생성되어야 함."""
        items = [{"name": "bad.pdf", "url": "https://invalid.invalid/bad.pdf"}]
        text, logs = extract_from_attachments(items, max_files=1)
        assert len(logs) == 1
        assert "name" in logs[0]
        assert "success" in logs[0]
        assert logs[0]["success"] is False

    def test_extension_from_url(self):
        """name에 확장자 없어도 URL에서 확장자 추출."""
        items = [{"name": "", "url": "https://invalid.invalid/notice.pdf"}]
        text, logs = extract_from_attachments(items, max_files=1)
        # 다운로드 실패하지만 PDF로 인식되어 처리 시도함
        assert len(logs) == 1
