# tests/unit/test_document_parser.py
"""OCR document_parser 단위 테스트."""
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
)


# ---------------------------------------------------------------------------
# ExtractionResult 기본 테스트
# ---------------------------------------------------------------------------
class TestExtractionResult:
    def test_success_when_long_text(self):
        """success는 strip 후 20자 초과일 때 True."""
        r = ExtractionResult(text="a" * 30, method="test")
        assert r.success is True

    def test_failure_when_short_text(self):
        """20자 이하이면 success=False."""
        r = ExtractionResult(text="hello", method="test")
        assert r.success is False

    def test_failure_when_empty(self):
        r = ExtractionResult(text="", method="test", error="empty")
        assert r.success is False

    def test_tables_default_empty(self):
        r = ExtractionResult(text="x", method="m")
        assert r.tables == []

    def test_repr(self):
        r = ExtractionResult(text="abc", method="test", pages=1)
        assert "test" in repr(r)


# ---------------------------------------------------------------------------
# extract_text dispatcher — 확장자 분기
# ---------------------------------------------------------------------------
class TestExtractTextDispatcher:
    def test_unknown_extension_returns_error(self):
        result = extract_text(b"data", "file.xyz")
        assert result.success is False
        assert "지원하지 않는" in result.error

    def test_empty_bytes_returns_error(self):
        result = extract_text(b"", "test.pdf")
        assert result.success is False

    def test_pdf_extension_accepted(self):
        """PDF 확장자는 dispatcher가 PDF 추출기를 호출 (잘못된 바이트면 실패)."""
        result = extract_text(b"not a pdf", "test.pdf")
        assert result.success is False  # 잘못된 바이트이므로 실패하지만 에러 메시지에 '지원하지 않는' 없음
        assert "지원하지 않는" not in (result.error or "")


# ---------------------------------------------------------------------------
# PDF 추출 (pdfplumber)
# ---------------------------------------------------------------------------
class TestPdfExtraction:
    def test_invalid_pdf_bytes(self):
        result = extract_pdf_pdfplumber(b"not a pdf")
        assert result.success is False

    def test_pypdf_fallback_invalid(self):
        result = extract_pdf_pypdf(b"not a pdf")
        assert result.success is False


# ---------------------------------------------------------------------------
# DOCX 추출
# ---------------------------------------------------------------------------
class TestDocxExtraction:
    def test_invalid_docx_bytes(self):
        result = extract_docx(b"not a docx")
        assert result.success is False


# ---------------------------------------------------------------------------
# HWP 추출
# ---------------------------------------------------------------------------
class TestHwpExtraction:
    def test_invalid_hwp_bytes(self):
        result = extract_hwp(b"not a hwp")
        assert result.success is False


# ---------------------------------------------------------------------------
# extract_from_attachments
# ---------------------------------------------------------------------------
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

    def test_max_files_limit(self):
        """max_files=0 이면 아무것도 처리 안 함."""
        items = [{"name": "doc.pdf", "url": "https://example.com/doc.pdf"}]
        text, meta = extract_from_attachments(items, max_files=0)
        assert text == ""
