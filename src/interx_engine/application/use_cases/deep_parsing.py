"""
DeepParsingUseCase — PDF/HWP/HWPX/DOCX 문서에서 예산·KPI 테이블을 추출하고
지원자격(매출·업종) 자동 매칭까지 수행한다.
"""
from __future__ import annotations

import logging
import re
import zipfile
from typing import Dict, List, Optional

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.deep_parsing")

# ── 지원자격 키워드 패턴 ──────────────────────────────────────────────────────
_REVENUE_RE   = re.compile(r"매출[액]?\s*[\d,]+\s*억?|연매출\s*[\d,]+")
_INDUSTRY_RE  = re.compile(r"(제조업|IT|정보통신|소프트웨어|서비스업|바이오|에너지)")
_BUDGET_RE    = re.compile(r"지원금액[:\s]*([0-9,]+)\s*(억|백만|만)\s*원?")
_KPI_KEYWORDS = ["목표", "성과지표", "KPI", "달성기준", "평가항목"]


def _extract_budget_from_text(text: str) -> List[Dict[str, str]]:
    rows = []
    for line in text.splitlines():
        m = _BUDGET_RE.search(line)
        if m:
            rows.append({
                "항목": line.strip()[:80],
                "금액": m.group(1).replace(",", ""),
                "단위": m.group(2),
            })
    return rows


def _extract_kpi_from_text(text: str) -> List[str]:
    results = []
    for line in text.splitlines():
        if any(kw in line for kw in _KPI_KEYWORDS):
            stripped = line.strip()
            if len(stripped) > 5:
                results.append(stripped[:120])
    return results[:10]


def _match_eligibility(text: str) -> Dict[str, List[str]]:
    return {
        "매출조건": _REVENUE_RE.findall(text),
        "대상업종": _INDUSTRY_RE.findall(text),
    }


# ── PDF 파싱 ──────────────────────────────────────────────────────────────────

def _pdf_to_text(path: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(path)
        pages = []
        for p in reader.pages[:20]:
            t = p.extract_text()
            if t:
                pages.append(t)
        return "\n".join(pages)
    except Exception as e:
        log.warning("[DeepParsing] PDF 파싱 실패 %s: %s", path, e)
        return ""


# ── HWP 파싱 (구형 바이너리 OLE 포맷) ────────────────────────────────────────

def _hwp_to_text(path: str) -> str:
    """구형 HWP 바이너리: olefile PrvText 스트림으로 미리보기 텍스트 추출."""
    try:
        import olefile  # type: ignore
        with olefile.OleFileIO(path) as ole:
            if ole.exists("PrvText"):
                raw = ole.openstream("PrvText").read()
                return raw.decode("utf-16-le", errors="ignore")
    except Exception as e:
        log.warning("[DeepParsing] HWP 파싱 실패 %s: %s", path, e)
    return ""


# ── HWPX 파싱 (신형 ZIP+XML 포맷) ────────────────────────────────────────────

def _hwpx_to_text(path: str) -> str:
    """
    HWPX는 ZIP 아카이브. 내부 word/section*.xml 에 본문이 있다.
    XML 태그를 제거해 순수 텍스트를 반환한다.
    """
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            # 본문 섹션 파일 수집 (section0.xml, section1.xml, ...)
            section_files = sorted(
                [n for n in names if re.match(r"word/section\d+\.xml", n)]
                or [n for n in names if "section" in n.lower() and n.endswith(".xml")]
            )
            if not section_files:
                # 모든 xml 파일을 후보로
                section_files = [n for n in names if n.endswith(".xml")]

            texts = []
            for fname in section_files[:5]:  # 최대 5개 섹션만
                try:
                    raw = zf.read(fname).decode("utf-8", errors="ignore")
                    # XML 태그 제거
                    clean = re.sub(r"<[^>]+>", " ", raw)
                    # 연속 공백 정리
                    clean = re.sub(r"\s+", " ", clean).strip()
                    if clean:
                        texts.append(clean)
                except Exception:
                    continue

            return "\n".join(texts)
    except zipfile.BadZipFile:
        # ZIP이 아닌 경우 구형 HWP로 재시도
        return _hwp_to_text(path)
    except Exception as e:
        log.warning("[DeepParsing] HWPX 파싱 실패 %s: %s", path, e)
        return ""


# ── DOCX 파싱 ─────────────────────────────────────────────────────────────────

def _docx_to_text(path: str) -> str:
    """python-docx 사용. 미설치 시 ZIP+XML 방식 fallback."""
    try:
        from docx import Document  # type: ignore
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        # python-docx 없음 → ZIP에서 word/document.xml 직접 파싱
        try:
            with zipfile.ZipFile(path, "r") as zf:
                raw = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", raw)
                return re.sub(r"\s+", " ", clean).strip()
        except Exception:
            return ""
    except Exception as e:
        log.warning("[DeepParsing] DOCX 파싱 실패 %s: %s", path, e)
        return ""


# ── 라우터 ────────────────────────────────────────────────────────────────────

def _read_attachment(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):
        return _pdf_to_text(path)
    if p.endswith(".hwpx"):
        return _hwpx_to_text(path)
    if p.endswith(".hwp"):
        # 확장자는 .hwp지만 실제 HWPX(ZIP) 포맷인 경우 자동 감지
        text = _hwp_to_text(path)
        if not text:
            text = _hwpx_to_text(path)  # fallback
        return text
    if p.endswith((".docx", ".doc")):
        return _docx_to_text(path)
    return ""


# ── Use Case ──────────────────────────────────────────────────────────────────

class DeepParsingUseCase:
    """
    공고 첨부파일(PDF/HWP/HWPX/DOCX)을 정밀 파싱해 예산·KPI·지원자격을 추출한다.
    결과를 notice.structured 딕셔너리에 병합한다.
    """

    def execute(self, notices: List[Notice]) -> List[Notice]:
        for notice in notices:
            if not notice.attachments:
                continue
            full_text = notice.body_text or ""

            for att_path in notice.attachments:
                if not isinstance(att_path, str):
                    continue
                try:
                    text = _read_attachment(att_path)
                    if text:
                        full_text += "\n" + text
                except Exception as e:
                    log.debug("[DeepParsing] 첨부파일 읽기 실패 %s: %s", att_path, e)

            if not full_text:
                # attachment_items에서 URL 기반 로컬 경로 탐색
                for item in getattr(notice, "attachment_items", []):
                    local = item.get("local_path", "")
                    if local:
                        try:
                            text = _read_attachment(local)
                            if text:
                                full_text += "\n" + text
                        except Exception:
                            pass

            if not full_text:
                continue

            budget_rows  = _extract_budget_from_text(full_text)
            kpi_items    = _extract_kpi_from_text(full_text)
            eligibility  = _match_eligibility(full_text)

            notice.structured.update({
                "parsed_budget_rows": budget_rows,
                "parsed_kpi_items":   kpi_items,
                "eligibility":        eligibility,
            })

            if budget_rows and not notice.budget:
                first = budget_rows[0]
                notice.budget = f"{first['금액']}{first['단위']}"

            log.debug(
                "[DeepParsing] %s → 예산%d행 KPI%d건 업종%s",
                notice.notice_id,
                len(budget_rows), len(kpi_items),
                eligibility.get("대상업종", []),
            )

        return notices
