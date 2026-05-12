# =============================================================================
# InterX Government Intelligence Engine - main.py (최종 통합본 v4.1)
# =============================================================================
# 변경사항 v4.1:
#   1. COLLECTOR_TIMEOUT 45 → 15 (무한대기 방지)
#   2. make_session retry 6 → 3회, backoff 1.2 → 0.8
#   3. BizinfoCollector parse_list_page: list.do/pageIndex URL 필터링 (루프 차단)
#   4. UipaCollector: ssl_verify=False, URL /board/business, 다중 셀렉터 fallback
#   5. _collect_all: fut.result(timeout=120) 사이트당 120초 강제 종료
# =============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
import zipfile
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

_easyocr_reader = None
def get_ocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None and EASYOCR_AVAILABLE:
        _easyocr_reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    return _easyocr_reader

try:
    import docx as python_docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import olefile
    OLEFILE_AVAILABLE = True
except ImportError:
    OLEFILE_AVAILABLE = False

# =============================================================================
# 0. 설정
# =============================================================================

BASE_DIR = Path("/content/drive/MyDrive/interx_gov_intelligence")

SPREADSHEET_NAME     = os.getenv("INTERX_SHEET_NAME", "InterX_BD_CRM_v10_fresh_template")
SERVICE_ACCOUNT_JSON = os.getenv("INTERX_SA_JSON",    str(BASE_DIR / "service_account.json"))
DB_PATH              = os.getenv("INTERX_DB_PATH",    str(BASE_DIR / "data" / "interx_engine.db"))
ATTACHMENT_DIR       = os.getenv("INTERX_ATT_DIR",    str(BASE_DIR / "data" / "attachments"))
LOG_DIR              = os.getenv("INTERX_LOG_DIR",    str(BASE_DIR / "logs"))
MAX_WORKERS          = int(os.getenv("INTERX_WORKERS",   "8"))
COLLECTOR_TIMEOUT    = int(os.getenv("INTERX_TIMEOUT",   "15"))   # ★ v4.1: 45 → 15
MAX_PAGES            = int(os.getenv("INTERX_MAX_PAGES", "5"))
PLAYWRIGHT_SITES     = set(os.getenv("PLAYWRIGHT_SITES", "iris,dicia").split(","))

HF_API_URL  = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
LLM_ENABLED = True
LLM_ENABLED = False

L3_STRONG_THRESHOLD    = 55
PARTNER_CAND_THRESHOLD = 35
MIN_FIT_SCORE          = 5

# ── 제목 블랙리스트 (수집 단계에서 아예 스킵) ────────────────────────────────
TITLE_BLACKLIST = [
    "게임", "웹툰", "만화", "영화", "애니메이션", "캐릭터",
    "축제", "공연", "음악", "전시", "e스포츠", "공모전",
    "관광", "패션", "뷰티", "스포츠", "문화", "예술", "방송", "미디어", "콘텐츠",
    "마케터", "해외마케팅", "해외진출", "수출지원", "수출바우처",
    "포스터", "보안교육", "운영관리자 과정",
    "선정결과", "심사결과", "평가결과", "입주기업 선정", "결과 공고", "합격자",
    "창작", "K-콘텐츠", "콘텐츠코리아", "글로벌게임",
    "콘텐츠 제작", "콘텐츠기업", "웹진", "뉴스레터", "농업", "어업", "수산",
]

POSITIVE_KEYWORDS: Dict[str, float] = {
    # ★ 2026 최신 정책 / 최고 가점 (InterX 핵심 과제 직접 매칭)
    "AX": 5, "AX-Sprint": 5, "AX사업": 5, "제조인공지능": 5, "AI 자율제조": 5,
    "피지컬AI": 5, "파운데이션모델": 5, "파운데이션 모델": 5, "멀티모달": 5,
    "AI에이전트": 5, "AI Agent": 5, "Manufacturing-X": 5,
    "디지털트윈": 5, "스마트공장": 5, "자율형 스마트공장": 5, "산업AI": 5, "제조AI": 5, 
    "신속 상용화": 5, "공동제조소": 4,

    # ★ 고가점 (InterX 솔루션 직접 연관)
    "스마트제조혁신": 4, "스마트팩토리": 4, "예지보전": 4, "머신비전": 4,
    "AI팩토리": 4, "제조데이터": 4, "클라우드제조": 4, "디지털협업공장": 4,
    "공정최적화": 4, "제조안전": 4, "중대재해": 4, "응용제품": 4, "지능형 제품": 4,
    "MES": 4, "OT": 4, "PLC": 4, "협동로봇": 4,
    "스마트센서": 4, "엣지AI": 4, "온디바이스": 4, "온디바이스 AI": 4,
    "버티컬AI": 4, "실증": 4, "상용화": 4, "구축지원": 4, "고도화": 4,

    # ★ 중가점 (관련 기술 및 산업)
    "AI": 3, "인공지능": 3, "제조": 3, "품질": 3, "검사": 3, "IIoT": 3,
    "공정": 3, "설비": 3, "모니터링": 3, "이상탐지": 3, "수율": 3,
    "불량": 3, "로봇": 3, "센서": 3, "자동화": 3, "안전": 3,
    "생성형AI": 3, "LLM": 3, "RAG": 3, "시뮬레이션": 3,
    "비전검사": 3, "외관검사": 3, "뿌리산업": 3,
    "용접": 3, "도장": 3, "주조": 3, "열처리": 3, "3D프린팅": 3,
    "조선": 3, "자동차": 3, "석유화학": 3, "반도체": 3,

    # ★ 기본 가점
    "데이터": 2, "ERP": 2, "PLM": 2, "SCM": 2, "플랫폼": 2, "GPT": 2,
    "비전": 2, "PoC": 2, "R&D": 2, "R&BD": 2,
    "중소기업": 1, "클라우드": 1, "API": 1,
}

NEGATIVE_KEYWORDS: Dict[str, float] = {
    "게임": 5, "웹툰": 5, "만화": 5, "영화": 5, "애니": 5,
    "캐릭터": 4, "축제": 4, "전시": 3, "음악": 4, "공연": 4,
    "e스포츠": 5, "공모전": 3, "관광": 3, "패션": 4, "뷰티": 4,
    "스포츠": 3, "문화": 2, "예술": 3, "방송": 3, "미디어": 2, "콘텐츠": 2,
}

SOLUTION_MAP: Dict[str, Dict[str, float]] = {
    "ManufacturingDT": {
        "디지털트윈": 4, "시뮬레이션": 3, "공정": 2, "스마트팩토리": 3, "자율형 스마트공장": 3,
        "자율제조": 3, "Manufacturing-X": 4, "AI팩토리": 4, "디지털협업공장": 3,
        "AX실증": 4, "피지컬AI": 3, "클라우드제조": 3, "공동제조소": 3,
    },
    "RecipeAI": {
        "레시피": 4, "공정레시피": 4, "배합": 3, "조건최적화": 3,
        "공정최적화": 3, "파운데이션모델": 2, "열공정": 3,
    },
    "QualityAI": {
        "품질": 3, "불량": 3, "수율": 3, "이상탐지": 4,
        "SPC": 3, "제조안전": 2, "용접": 2, "도장": 2,
    },
    "InspectionAI": {
        "비전검사": 4, "외관검사": 4, "머신비전": 4,
        "비전": 2, "검사": 2,
    },
    "SafetyAI": {
        "안전": 3, "중대재해": 4, "위험": 2, "사고": 2,
        "안전모니터링": 3, "제조안전": 4, "안전시스템": 4,
    },
    "GenAI": {
        "생성형AI": 4, "LLM": 4, "RAG": 4, "GPT": 3, "멀티모달": 4,
        "AI에이전트": 4, "AI Agent": 4, "파운데이션모델": 4, "파운데이션 모델": 4,
        "인공지능": 2, "제조인공지능": 4,
    },
    "InfraDS": {
        "데이터": 2, "API": 2, "MES": 3, "ERP": 3, "PLM": 2, "SCM": 2,
        "OT": 3, "PLC": 3, "플랫폼": 2, "제조데이터": 3,
        "DPP": 3, "Manufacturing-X": 3, "스마트제조혁신": 3, "AAS": 4,
    },
    "PdM": {
        "예지보전": 4, "설비": 3, "모니터링": 3, "이상탐지": 3, "IIoT": 3,
        "센서": 3, "스마트센서": 4, "엣지AI": 3, "온디바이스": 3, "온디바이스 AI": 3,
    },
}

MASTER_COLUMNS = [
    "사이트", "공고명", "공고명링크", "상세URL",
    "등록일", "마감일", "D-day", "상태",
    "주무부처", "수행기관", "예산",
    "적합도점수", "우선순위등급",
    "추천솔루션", "사업요약",
    "ManufacturingDT점수", "RecipeAI점수", "QualityAI점수",
    "InspectionAI점수", "SafetyAI점수", "GenAI점수", "InfraDS점수", "PdM점수",
    "산업키워드", "적합키워드",
    "첨부수", "첨부명", "첨부URL",
    "담당자", "검토상태", "다음액션", "메모", "L3강공고", "파트너후보",
]
ATTACHMENT_COLUMNS = [
    "공고ID", "사이트", "공고명", "공고상세링크",
    "파일순번", "파일명", "원본URL", "다운로드링크",
    "local_path", "download_status", "parse_status", "parse_error",
]
EXEC_LOG_COLUMNS    = ["실행ID", "실행시각", "사이트", "수집건수", "첨부수", "다운로드성공",
                        "파싱성공", "L3강공고수", "파트너후보수", "소요초", "상태"]
COLLECT_LOG_COLUMNS = ["실행ID", "사이트", "공고ID", "공고명", "등록일", "마감일", "첨부수", "수집시각"]
ERROR_LOG_COLUMNS   = ["실행ID", "사이트", "공고ID", "단계", "오류유형", "오류내용", "발생시각"]

SHEET_MAP: Dict[str, str] = {
    "master":         "01_사업마스터_원본",
    "l3_strong":      "02_L3강공고",
    "partner":        "03_파트너전달",
    "attachments":    "04_첨부파일목록",
    "pipeline":       "15_사업_파이프라인",
    "pipeline_score": "16_사업_파이프라인_점수모델",
    "summary":        "20_요약대시보드",
    "exec_summary":   "21_경영진요약",
    "kpi":            "22_KPI대시보드",
    "exec_log":       "94_실행로그",
    "collect_log":    "95_수집로그",
    "error_log":      "96_수집에러로그",
}
SHEET_COLUMNS: Dict[str, List[str]] = {
    "master":       MASTER_COLUMNS,
    "l3_strong":    MASTER_COLUMNS,
    "partner":      MASTER_COLUMNS,
    "attachments":  ATTACHMENT_COLUMNS,
    "exec_log":     EXEC_LOG_COLUMNS,
    "collect_log":  COLLECT_LOG_COLUMNS,
    "error_log":    ERROR_LOG_COLUMNS,
}

# =============================================================================
# 1. 로거
# =============================================================================

def setup_logger(name: str = "interx", log_dir: str = LOG_DIR) -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(
        Path(log_dir) / f"interx_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger

log = setup_logger()

# =============================================================================
# 2. 데이터 모델
# =============================================================================

@dataclass
class Notice:
    execution_id: str
    site: str
    notice_id: str
    title: str
    detail_url: str = ""
    notice_link: str = ""
    posted_date: str = ""
    deadline_date: str = ""
    ministry: str = ""
    agency: str = ""
    business_type: str = ""
    budget: str = ""
    duration_months: str = ""
    summary: str = ""
    llm_summary: str = ""
    manager: str = ""
    recommended_solution: str = ""
    recommended_action: str = ""
    proposal_strategy: str = ""
    status: str = "NEW"
    l3_strong: str = "N"
    partner_candidate: str = "N"
    attachments: List[str] = field(default_factory=list)
    attachment_items: List[Dict[str, str]] = field(default_factory=list)
    structured: Dict[str, str] = field(default_factory=dict)
    body_text: str = ""

    @property
    def notice_key(self) -> str:
        return hashlib.md5(f"{self.site}:{self.notice_id}".encode()).hexdigest()

    def is_closed(self) -> bool:
        if not self.deadline_date:
            return False
        try:
            return date.fromisoformat(self.deadline_date[:10]) < date.today()
        except Exception:
            return False


@dataclass
class ScoreCard:
    execution_id: str
    notice_id: str
    site: str
    fitness_score: float
    priority_score: float
    priority_grade: str
    solution_scores: Dict[str, float] = field(default_factory=dict)
    positive_keywords: List[str] = field(default_factory=list)
    negative_keywords: List[str] = field(default_factory=list)
    industry_score: float = 0.0


@dataclass
class ErrorRecord:
    execution_id: str
    site: str
    notice_id: str
    stage: str
    error_type: str
    error_msg: str
    occurred_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# 3. HTTP 유틸
# =============================================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def make_session(verify_ssl: bool = True) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3, connect=3, read=3, backoff_factor=0.8,   # ★ v4.1: 6→3, 1.2→0.8
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"], raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry,
                          pool_connections=MAX_WORKERS * 2,
                          pool_maxsize=MAX_WORKERS * 4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    if not verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session.verify = False
    return session


def fetch_html(url: str, session: requests.Session,
               timeout: int = COLLECTOR_TIMEOUT,
               verify_ssl: bool = True) -> str:
    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            resp = session.get(url, headers=DEFAULT_HEADERS,
                               timeout=(5, timeout),
                               verify=verify_ssl, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.exceptions.SSLError:
            try:
                resp = session.get(url, headers=DEFAULT_HEADERS,
                                   timeout=(5, timeout), verify=False, allow_redirects=True)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text
            except Exception as e2:
                last_exc = e2
        except requests.exceptions.RequestException as e:
            last_exc = e
            wait = (1.2 ** attempt) + (attempt * 0.2)
            log.debug("[fetch] retry=%d url=%s wait=%.1fs", attempt, url, wait)
            time.sleep(wait)
    raise last_exc or RuntimeError(f"fetch_html 실패: {url}")


def fetch_html_playwright(url: str, timeout_ms: int = 30_000) -> str:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("playwright 미설치")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"})
        page.goto(url, timeout=timeout_ms, wait_until="networkidle")
        html = page.content()
        browser.close()
    return html


def fetch_html_smart(url: str, session: requests.Session,
                     site_key: str = "",
                     timeout: int = COLLECTOR_TIMEOUT) -> str:
    use_pw = site_key in PLAYWRIGHT_SITES
    if use_pw and PLAYWRIGHT_AVAILABLE:
        try:
            return fetch_html_playwright(url)
        except Exception as e:
            log.warning("[PW→requests] %s: %s", url, e)
    try:
        return fetch_html(url, session, timeout=timeout)
    except Exception as e:
        if PLAYWRIGHT_AVAILABLE and not use_pw:
            log.warning("[requests→PW] %s: %s", url, e)
            return fetch_html_playwright(url)
        raise


# =============================================================================
# 4. HTML 파싱 유틸
# =============================================================================

def safe_text(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip())


def _extract_summary(soup: BeautifulSoup, body_text: str, max_len: int = 300) -> str:
    """네비게이션 제거하고 본문 핵심만 추출"""
    # 본문 영역 직접 추출 시도
    for sel in [".view_content", ".board-view-content", ".bbs-view-body",
                ".view-body", ".content-body", ".board_view", "#content"]:
        el = soup.select_one(sel)
        if el:
            t = safe_text(el.get_text(" "))
            if len(t) > 50:
                return t[:max_len]
    # fallback: 불필요 키워드 이후 텍스트
    nav_keywords = ["본문 바로가기", "주메뉴 바로가기", "로그인", "사이트맵"]
    text = body_text
    for kw in nav_keywords:
        idx = text.find(kw)
        if idx > 0:
            text = text[idx + len(kw):]
    # 첫 200자 이후부터 의미있는 텍스트 추출
    text = text.strip()
    # 짧은 단어들(메뉴) 건너뛰기
    lines = [l.strip() for l in text.split() if len(l.strip()) > 4]
    return " ".join(lines[:60])[:max_len]


def parse_title(soup: BeautifulSoup) -> str:
    for sel in [".view-title", ".bbs-view-title", "h3.title", "h3",
                "h4", ".tit", ".title", "strong.tit", "title"]:
        el = soup.select_one(sel)
        if el:
            t = safe_text(el.get_text())
            if len(t) >= 4:
                return t
    return ""


def _ext_from_text(text: str) -> str:
    m = re.search(r"\.(pdf|hwp|hwpx|zip|doc|docx|xls|xlsx|ppt|pptx)", text or "", re.I)
    return m.group(1).lower() if m else ""


def parse_attachments(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: set = set()
    candidates = soup.select(
        "a[href], a[onclick], button[onclick], [onclick], "
        "[data-atch-file-id], [data-file-sn], .file-list li, .attach li"
    )
    for node in candidates:
        text    = safe_text(node.get_text(" "))
        href    = node.get("href", "") or ""
        onclick = node.get("onclick", "") or ""
        sig     = f"{text} {href} {onclick}"
        if not re.search(
            r"(fileLoad|fileBlank|download|atchFile|fileSn|"
            r"\.(pdf|hwp|hwpx|zip|doc|docx|xls|xlsx|ppt|pptx))",
            sig, re.I,
        ):
            continue
        url = ""
        m = re.search(r"(fileLoad|fileBlank)\(([^)]+)\)", onclick, re.I)
        if m:
            args = re.findall(r"['\"]([^'\"]+)['\"]", m.group(2))
            if len(args) >= 2 and args[0].startswith("/"):
                url = urljoin(base_url, "".join(args[:2]))
            elif args and args[0].startswith("/"):
                url = urljoin(base_url, args[0])
        if not url:
            atch = node.get("data-atch-file-id", "")
            sn   = node.get("data-file-sn", "")
            if atch and sn:
                url = f"{base_url.rstrip('/')}/cmm/fms/FileDown.do?atchFileId={atch}&fileSn={sn}"
        if not url and href and not href.lower().startswith("javascript:"):
            url = urljoin(base_url, href)
        if not url:
            for cand in re.findall(r"['\"]([^'\"]{5,})['\"]", onclick):
                if any(kw in cand for kw in ["/down", "FileDown", "atchFile", "download"]):
                    url = urljoin(base_url, cand)
                    break
        if not url:
            continue
        # ★ /webapp/upload/ 로 끝나는 불완전 URL 차단 (파일명 없는 경우)
        if url.endswith("/") and "/webapp/upload/" in url:
            continue
        # ★ "다운로드" 같은 무의미한 텍스트는 URL에서 파일명 추출
        if not text or text in ["다운로드", "download", "첨부파일", "파일"]:
            # URL에서 파일명 추출
            url_name = url.split("/")[-1].split("?")[0]
            name = url_name if url_name and "." in url_name else (text or "attachment")
        else:
            name = text
        if "." not in name.split("/")[-1]:
            ext = _ext_from_text(sig) or _ext_from_text(url)
            if ext:
                name = f"{name}.{ext}"
        key = (name[:80], url[:200])
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name[:200], "url": url,
                    "ext": _ext_from_text(name) or _ext_from_text(url)})
    return out



# ★ 섹션 정제 함수 (불렛/번호/공백/네비게이션 제거)
SECTION_SPEC = {
    "사업목적":  {"max_chars": 500, "patterns": ["사업목적", "사업의 목적", "추진목적", "추진배경"]},
    "지원대상":  {"max_chars": 400, "patterns": ["지원대상", "신청자격", "지원 대상", "참여자격"]},
    "지원내용":  {"max_chars": 600, "patterns": ["지원내용", "지원 내용", "지원규모", "지원금액", "지원사항"]},
    "지원조건":  {"max_chars": 300, "patterns": ["지원조건", "신청조건", "참여조건", "자격조건"]},
    "신청방법":  {"max_chars": 300, "patterns": ["신청방법", "신청절차", "접수방법", "신청기간"]},
    "평가기준":  {"max_chars": 300, "patterns": ["평가기준", "선정기준", "심사기준", "평가항목"]},
}

NAV_KEYWORDS = [
    "본문 바로가기", "주메뉴 바로가기", "사이트맵", "전체메뉴",
    "공고/알림", "알림마당", "Home >", "home >", "<title",
    "layout:title", "바로가기", "대메뉴",
]

def clean_section_text(text: str, max_chars: int = 500) -> str:
    if not text:
        return ""
    # 네비게이션 텍스트 제거
    for kw in NAV_KEYWORDS:
        idx = text.find(kw)
        if idx >= 0:
            text = text[idx + len(kw):]
    # 불렛/번호/공백 정리
    text = re.sub(r"[○◦▸▪·□■▶➢➤※]\s*", "", text)
    text = re.sub(r"^\s*\d+[.)]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text[:max_chars]

# ★ 비정형 신청기간 패턴 (팀원 코드 통합)
NONSTANDARD_PERIODS = {
    "예산 소진시까지", "상시 접수", "추후 공지",
    "매월 1일~20일", "세부사업별 상이", "상시", "수시",
}

def _norm_date_str(s: str) -> str:
    """날짜 문자열 정규화: 2026.3.5 / 2026년 3월 5일 → 2026-03-05"""
    s = s.strip()
    parts = re.split(r"[.\-/년월]", s)
    parts = [p.strip().rstrip("일").strip() for p in parts if p.strip().isdigit()]
    if len(parts) >= 3:
        try:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except Exception:
            pass
    return s.strip()


def extract_dates(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not text:
        return result
    t = re.sub(r"\s+", " ", text).strip()
    t = t.replace("∼", "~").replace("～", "~").replace("–", "~").replace("—", "~")
    DATE_PAT = r"\d{4}[.\-/년]\s*\d{1,2}[.\-/월]?\s*\d{1,2}\s*일?"

    # 1. 기간 섹션에서 start~end 추출
    for kw in ["신청기간", "접수기간", "공모기간", "모집기간", "사업기간"]:
        m = re.search(kw + r"\s*[:：]?\s*([^\n\r]{5,80})", t)
        if m:
            seg = m.group(1)
            dates = re.findall(DATE_PAT, seg)
            if len(dates) >= 2:
                result["posted_date"]   = _norm_date_str(dates[0])
                result["deadline_date"] = _norm_date_str(dates[1])
                return result
            elif len(dates) == 1 and "~" in seg:
                right = seg[seg.find("~")+1:]
                rd = re.findall(DATE_PAT, right)
                if rd:
                    result["deadline_date"] = _norm_date_str(rd[0])

    # 2. 전체 텍스트에서 ~ 기준 날짜 2개
    if "deadline_date" not in result:
        tilde = t.find("~")
        if tilde > 0:
            left  = re.findall(DATE_PAT, t[:tilde])
            right = re.findall(DATE_PAT, t[tilde:])
            if left and right:
                result["posted_date"]   = _norm_date_str(left[-1])
                result["deadline_date"] = _norm_date_str(right[0])
                return result

    # 3. 키워드 기반 단일 날짜
    kw_pats = {
        "posted_date":   [r"공고일\s*[:：]?\s*(" + DATE_PAT + ")", r"등록일\s*[:：]?\s*(" + DATE_PAT + ")", r"게시일\s*[:：]?\s*(" + DATE_PAT + ")"],
        "deadline_date": [r"마감일\s*[:：]?\s*(" + DATE_PAT + ")", r"접수\s*마감\s*[:：]?\s*(" + DATE_PAT + ")", r"제출\s*기한\s*[:：]?\s*(" + DATE_PAT + ")", r"까지\s*[:：]?\s*(" + DATE_PAT + ")"],
    }
    for key, pats in kw_pats.items():
        if key in result:
            continue
        for pat in pats:
            m = re.search(pat, t, re.S)
            if m:
                result[key] = _norm_date_str(m.group(1))
                break
    return result


def extract_budget(text: str) -> str:
    for pat in [
        r"예산\s*[:：]?\s*([\d,]+\s*(?:억|백만|만)\s*원)",
        r"지원금액\s*[:：]?\s*([\d,]+\s*(?:억|백만|만)\s*원)",
        r"총\s*사업비\s*[:：]?\s*([\d,]+\s*(?:억|백만|만)\s*원)",
        r"지원규모\s*[:：]?\s*([\d,]+\s*(?:억|백만|만)\s*원)",
    ]:
        m = re.search(pat, text)
        if m:
            return safe_text(m.group(1))
    return ""


def extract_ministry(text: str) -> str:
    m = re.search(
        r"(주관|주무|담당)\s*부처\s*[:：]?\s*([^,（(]{2,20}(?:부|처|청|원|위원회))",
        text,
    )
    return safe_text(m.group(2)) if m else ""


def calc_dday(deadline_str: str) -> Tuple[str, str]:
    if not deadline_str:
        return "마감일미상", "NEW"
    try:
        dl    = date.fromisoformat(deadline_str[:10])
        today = date.today()
        diff  = (dl - today).days
        if diff < 0:
            return f"마감({abs(diff)}일전)", "CLOSED"
        if diff == 0:
            return "D-Day(오늘마감)", "DEADLINE_SOON"
        if diff <= 3:
            return f"D-{diff}(긴급)", "DEADLINE_SOON"
        if diff <= 7:
            return f"D-{diff}(이번주)", "DEADLINE_SOON"
        if diff <= 14:
            return f"D-{diff}(2주내)", "NEW"
        if diff <= 30:
            return f"D-{diff}(이번달)", "NEW"
        return f"D-{diff}일남음", "NEW"
    except Exception:
        return "날짜오류", "NEW"




SECTION_SPEC = {
    "사업목적": {"patterns": [r"사업\s*목적", r"추진\s*배경", r"사업\s*개요"], "max_chars": 500},
    "지원대상": {"patterns": [r"지원\s*대상", r"신청\s*자격", r"참여\s*자격"], "max_chars": 800},
    "지원내용": {"patterns": [r"지원\s*내용", r"지원\s*분야", r"세부\s*내용"], "max_chars": 1000},
    "지원조건": {"patterns": [r"지원\s*조건", r"선정\s*조건"], "max_chars": 500},
    "예산":     {"patterns": [r"예산", r"지원\s*금액", r"총\s*사업비", r"지원\s*규모"], "max_chars": 300},
    "일정":     {"patterns": [r"추진\s*일정", r"사업\s*일정", r"세부\s*일정"], "max_chars": 500},
    "신청방법": {"patterns": [r"신청\s*방법", r"접수\s*방법", r"신청\s*절차"], "max_chars": 500},
    "접수기간": {"patterns": [r"접수\s*기간", r"신청\s*기간"], "max_chars": 300},
    "제출서류": {"patterns": [r"제출\s*서류", r"제출\s*자료", r"신청\s*서류"], "max_chars": 500},
    "평가기준": {"patterns": [r"평가\s*기준", r"선정\s*기준", r"평가\s*지표"], "max_chars": 600},
    "담당자":   {"patterns": [r"담당\s*자", r"문의\s*처", r"문의"], "max_chars": 200},
}

def clean_section_text(text: str, max_chars: int = 500) -> str:
    if not text: return ""
    t = re.sub(r"[○●□■△▲▽▼\-ㆍ·\*▶▷]", "", text)
    t = re.sub(r"^\s*(?:\d+[\.\)]|[가-힣][\.\)]|[a-zA-Z][\.\)]|[①-⑳]|[⑴-⑽])\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"[\r\t]+", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()

def extract_structured_sections(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not text: return result
    anchors: List[Tuple[int, str, int]] = []
    
    for section, spec in SECTION_SPEC.items():
        combined = "|".join(f"(?:{p})" for p in spec["patterns"])
        regex = re.compile(rf"(?:^||\s)(?:[○●□■\-\d\.]\s*)?({combined})\s*[:\]\)]?", re.I)
        for m in regex.finditer(text): 
            anchors.append((m.start(), section, spec["max_chars"]))
            
    anchors.sort(key=lambda x: x[0])
    
    for idx, (start, section, max_chars) in enumerate(anchors):
        if section in result: continue
        end = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(text)
        chunk_raw = text[start:end]
        chunk_no_header = re.sub(r"^.*?", "", chunk_raw, count=1).strip()
        cleaned = clean_section_text(chunk_no_header or chunk_raw)
        if len(cleaned) > 5: 
            result[section] = cleaned[:max_chars]
            
    return result

# =============================================================================
# 5. 무료 LLM 요약 (HuggingFace)
# =============================================================================

def llm_summarize(notice: Notice, max_chars: int = 3000) -> str:
    """
    Gemini 2.0 Flash로 공고 핵심 요약 + InterX 적합도 분석.
    구조화 데이터(structured_clean)를 우선 사용하여 분석 품질 극대화.
    """
    if not LLM_ENABLED:
        return ""
        
    # 방금 패치한 구조화 데이터(SECTION_SPEC 결과물)를 프롬프트 재료로 조립
    context_parts = []
    for k, v in notice.structured.items():
        if len(v) > 10:
            context_parts.append(f"[{k}]{v[:500]}")
    context_str = "".join(context_parts)
    
    # 구조화 파싱이 너무 안 된 문서의 경우 안전장치(Fallback)
    if len(context_str) < 100:
        context_str = notice.body_text[:max_chars]

    time.sleep(4)  # rate limit 방지
    for attempt in range(3):
        try:
            import os
            from google import genai as _genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key: return ""
            client = _genai.Client(api_key=api_key)
            
            # BD 맞춤형 하드코딩 프롬프트
            prompt = f"""아래는 정부 지원사업 공고입니다. InterX는 제조 AI 기업(핵심기술: 디지털트윈, 예지보전, 비전품질검사, 레시피최적화, AAS데이터표준화)입니다.

공고명: {notice.title}
내용(주요 섹션 추출본):
{context_str[:3000]}

위 내용을 바탕으로 InterX 영업대표가 10초 만에 핵심을 파악할 수 있게 아래 형식으로 요약해줘 (각 항목 1~2줄, 마크다운 없이 텍스트로만):
[사업목적] 
[지원대상] 
[지원규모] 
[InterX적합도] 상/중/하 (당사 제조 솔루션 도입/PoC 연계 가능성 기준 구체적 이유 1줄)
[추천솔루션] ManufacturingDT/RecipeAI/QualityAI/InspectionAI/SafetyAI/GenAI/InfraDS/PdM 중 해당"""
            
            resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return resp.text.strip()
        except Exception as e:
            if "429" in str(e): time.sleep((attempt + 1) * 15)
            else: return ""
    return ""


class BaseCollector(ABC):
    site_key:   str  = "base"
    base_url:   str  = ""
    ssl_verify: bool = True

    def __init__(self, max_pages: int = MAX_PAGES, timeout: int = COLLECTOR_TIMEOUT):
        self.max_pages = max_pages
        self.timeout   = timeout
        self.session   = make_session(verify_ssl=self.ssl_verify)
        self._errors:  List[ErrorRecord] = []

    @abstractmethod
    def get_list_url(self, page: int) -> str: ...

    @abstractmethod
    def parse_list_page(self, html: str) -> List[Dict[str, str]]: ...

    @abstractmethod
    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]: ...

    def make_notice_id(self, detail_url: str) -> str:
        try:
            q = parse_qs(urlparse(detail_url).query)
            for key in ["policyNewsId", "pblancId", "biz_no", "ntcId", "id",
                        "seq", "no", "idx", "articleId", "bbsSeq"]:
                val = (q.get(key) or [""])[0]
                if val:
                    return f"{self.site_key}-{val}"[:80]
        except Exception:
            pass
        slug = detail_url.rstrip("/").split("/")[-1][:60]
        return f"{self.site_key}-{slug}"

    def collect(self, execution_id: str) -> List[Notice]:
        notices:   List[Notice] = []
        seen_urls: set = set()
        self._errors = []

        for page in range(1, self.max_pages + 1):
            list_url = self.get_list_url(page)
            try:
                html = fetch_html_smart(list_url, self.session,
                                        site_key=self.site_key, timeout=self.timeout)
            except Exception as e:
                log.error("[%s] 목록 실패 page=%d: %s", self.site_key, page, e)
                self._errors.append(ErrorRecord(execution_id, self.site_key, "",
                                                "list_fetch", type(e).__name__, str(e)[:300]))
                break

            items = self.parse_list_page(html)
            if not items:
                break

            new_items = [it for it in items if it["detail_url"] not in seen_urls]
            if not new_items:
                break

            for item in new_items:
                seen_urls.add(item["detail_url"])
                
                # [핵심 방어막] 상세 페이지 접속 전에 '목록 제목'만 보고 네거티브 키워드 즉시 차단
                raw_title_list = item.get("title", "")
                if any(kw in raw_title_list for kw in TITLE_BLACKLIST):
                    log.debug("[%s] 🚫 제목 네거티브 키워드 차단(스킵): %s", self.site_key, raw_title_list[:40])
                    continue

                # [수정1: 404 URL 자동 보정 및 재시도 로직]
                def get_fallback_url(original_url: str, site_key: str) -> str:
                    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
                    parsed = urlparse(original_url)
                    path = parsed.path
                    if site_key == "uipa" and path.startswith("/view.html"): path = "/webuser/business/view.html"
                    elif site_key == "nipa" and path.startswith("/view"): path = "/site/main/board/notice/view"
                    elif site_key == "kiat" and path.startswith("/boardView.do"): path = "/site/main/board/boardView.do"
                    query_params = parse_qs(parsed.query)
                    for k in ['page', 'pageIndex', 'pageNumber']: query_params.pop(k, None)
                    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, urlencode(query_params, doseq=True), parsed.fragment))

                try:
                    dhtml  = fetch_html_smart(item["detail_url"], self.session, site_key=self.site_key, timeout=self.timeout)
                    detail = self.parse_detail_page(dhtml, item["detail_url"])
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        fallback_url = get_fallback_url(item["detail_url"], self.site_key)
                        log.warning("[%s] 404 발생. URL 보정 후 재시도: %s", self.site_key, fallback_url)
                        try:
                            dhtml = fetch_html_smart(fallback_url, self.session, site_key=self.site_key, timeout=self.timeout)
                            detail = self.parse_detail_page(dhtml, fallback_url)
                            item["detail_url"] = fallback_url
                        except Exception as fallback_e:
                            log.error("[%s] 보정 URL도 실패 %s: %s", self.site_key, fallback_url, fallback_e)
                            continue
                    else:
                        log.error("[%s] 상세 실패 %s: %s", self.site_key, item["detail_url"], e)
                        continue
                except Exception as e:
                    log.error("[%s] 상세 실패 %s: %s", self.site_key, item["detail_url"], e)
                    self._errors.append(ErrorRecord(execution_id, self.site_key, self.make_notice_id(item["detail_url"]), "detail_fetch", type(e).__name__, str(e)[:300]))
                    continue

                # ── 제목 블랙리스트 필터 ────────────────────────────────────
                raw_title = detail.get("title") or item.get("title", "")
                if any(kw in raw_title for kw in TITLE_BLACKLIST):
                    log.debug("[%s] 블랙리스트 제외: %s", self.site_key, raw_title[:40])
                    continue

                # ── 마감 공고 완전 차단 ─────────────────────────────────────
                # 선정결과/심사결과 등 완료 공고 제외
                if any(kw in raw_title for kw in ["선정 결과", "선정결과", "심사결과", "평가 결과", "결과 공고"]):
                    log.debug("[%s] 완료공고 제외: %s", self.site_key, raw_title[:40])
                    continue

                deadline = detail.get("deadline_date", "")
                if deadline:
                    try:
                        if date.fromisoformat(deadline[:10]) < date.today():
                            log.debug("[%s] 마감 제외: %s", self.site_key, item.get("title", "")[:40])
                            continue
                    except Exception:
                        pass

                atts      = detail.get("attachments", [])
                body_text = detail.get("body_text", "")
                _, status = calc_dday(deadline)

                notice = Notice(
                    execution_id=execution_id,
                    site=self.site_key,
                    notice_id=self.make_notice_id(item["detail_url"]),
                    title=detail.get("title") or item.get("title", ""),
                    detail_url=item["detail_url"],
                    notice_link=item["detail_url"],
                    posted_date=detail.get("posted_date", ""),
                    deadline_date=deadline,
                    ministry=detail.get("ministry", ""),
                    agency=detail.get("agency", self.site_key),
                    business_type=detail.get("business_type", ""),
                    budget=detail.get("budget", ""),
                    duration_months=detail.get("duration_months", ""),
                    summary=detail.get("summary", body_text[:300]),
                    manager=detail.get("manager", ""),
                    status=status,
                    attachments=[a.get("name", "") for a in atts],
                    attachment_items=atts,
                    structured=extract_structured_sections(body_text),
                    body_text=body_text,
                )
                notices.append(notice)
                log.debug("[%s] 수집: %s", self.site_key, notice.title[:50])

        return notices


# =============================================================================
# 7. 사이트별 수집기
# =============================================================================

class BizinfoCollector(BaseCollector):
    """기업마당 https://www.bizinfo.go.kr"""
    site_key = "bizinfo"
    base_url = "https://www.bizinfo.go.kr"

    def get_list_url(self, page: int) -> str:
        return (f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/"
                f"list.do?pageIndex={page}")

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()

        def add(raw_url: str, title: str = "") -> None:
            if not raw_url:
                return
            u = unescape(raw_url.strip())
            if not u.startswith("http"):
                u = self.base_url + u if u.startswith("/") else f"{self.base_url}/{u}"
            # ★ v4.1: list.do / pageIndex 포함 URL 차단 → 루프 원인 제거
            if "list.do" in u or "pageIndex" in u:
                return
            if "selectBIZA200Detail.do" not in u and "policyNewsId=" not in u:
                return
            if u in seen:
                return
            seen.add(u)
            items.append({"title": title, "detail_url": u})

        for a in soup.select("a[href]"):
            href  = (a.get("href") or "").strip()
            title = safe_text(a.get_text(" ", strip=True))
            # ★ v4.1: list.do 포함 href 즉시 skip
            if "list.do" in href or "pageIndex" in href:
                continue
            if "selectBIZA200Detail.do" in href or "policyNewsId=" in href:
                add(href, title)

        for node in soup.select("[onclick]"):
            oc    = node.get("onclick", "") or ""
            title = safe_text(node.get_text(" ", strip=True))
            if "list.do" in oc:
                continue
            m = re.search(
                r"(/[^\s'\"]*selectBIZA200Detail\.do\?[^\s'\"]*policyNewsId=\d+[^\s'\"]*)",
                oc, re.I,
            )
            if m:
                add(m.group(1), title)
            else:
                for cand in re.findall(r"['\"]([^'\"]+)['\"]", oc):
                    if ("selectBIZA200Detail.do" in cand or "policyNewsId=" in cand) \
                            and "list.do" not in cand:
                        add(cand, title)
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title":         parse_title(soup),
            "body_text":     body_text,
            "posted_date":   dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget":        extract_budget(body_text),
            "ministry":      extract_ministry(body_text),
            "agency":        "기업마당",
            "business_type": "정보지원사업",
            "summary":       _extract_summary(soup, body_text),
            "attachments":   parse_attachments(soup, detail_url),
        }


class CbtpCollector(BaseCollector):
    """충북테크노파크 https://www.cbtp.or.kr"""
    site_key   = "cbtp"
    base_url   = "https://www.cbtp.or.kr"
    ssl_verify = False

    def collect(self, execution_id: str):
        # ★ DH_KEY_TOO_SMALL 우회: requests legacy SSL
        import ssl, urllib3
        urllib3.disable_warnings()
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        import requests.adapters
        from urllib3.util.ssl_ import create_urllib3_context
        class LegacyAdapter(requests.adapters.HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                ctx2 = create_urllib3_context(ciphers="DEFAULT:@SECLEVEL=0")
                ctx2.check_hostname = False
                ctx2.verify_mode = ssl.CERT_NONE
                kwargs["ssl_context"] = ctx2
                return super().init_poolmanager(*args, **kwargs)
        self.session.mount("https://", LegacyAdapter())
        return super().collect(execution_id)

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/index.php?board_id=saup_notice&page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("table tbody tr td.subject a, .board-list td.title a, td.subject a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "충북테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class TtpCollector(BaseCollector):
    """대구테크노파크 https://www.ttp.org"""
    site_key = "ttp"
    base_url = "https://www.ttp.org"

    def get_list_url(self, page: int) -> str:
        return (f"{self.base_url}/bbs/BoardControll.do"
                f"?bbsId=BBSMSTR_000000000003&pageIndex={page}")

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("td.subject a, td.title a, .bbs-list td a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3 and "BoardControll" not in href:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        for node in soup.select("[onclick]"):
            oc    = node.get("onclick", "") or ""
            title = safe_text(node.get_text())
            for m in re.finditer(r"['\"]([^'\"]*BoardRead[^'\"]*)['\"]", oc):
                href = urljoin(self.base_url, m.group(1))
                if href not in seen:
                    seen.add(href)
                    items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "대구테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class JejutpCollector(BaseCollector):
    """제주테크노파크 https://jejutp.or.kr"""
    site_key = "jejutp"
    base_url = "https://jejutp.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board/business?pageNumber={page - 1}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("table tbody tr td a, .board-list a, ul.list li a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3 and "business" in href:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "제주테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class DiciaCollector(BaseCollector):
    """DICIA PMS https://pms.dicia.or.kr"""
    site_key = "dicia"
    base_url = "https://pms.dicia.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/mgmt/mjgg/mjggMgmtListR.do?pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("td.subject a, td.title a, table tbody tr td a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        for node in soup.select("[onclick]"):
            oc    = node.get("onclick", "") or ""
            title = safe_text(node.get_text())
            for m in re.finditer(r"['\"]([^'\"]*mjgg[^'\"]*)['\"]", oc):
                href = urljoin(self.base_url, m.group(1))
                if href not in seen:
                    seen.add(href)
                    items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "DICIA", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class BipaCollector(BaseCollector):
    """부산정보산업진흥원 https://bipa.kr"""
    site_key = "bipa"
    base_url = "https://bipa.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board/business/list?page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("table tbody tr td a, .board-list td.title a, ul.list li a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            # ★ D-숫자 / 마감 접두어 제거
            title = re.sub(r"^(?:D-\d+|마감)\s*", "", title).strip()
            if href not in seen and len(title) > 3 and "부산정보산업진흥원" not in title:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": next((safe_text(el.get_text()) for el in soup.select(".view-title, .board-view h3, .subject, h3, h2") if safe_text(el.get_text()) and "부산정보산업진흥원" not in safe_text(el.get_text()) and len(safe_text(el.get_text())) > 3), parse_title(soup)), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "부산정보산업진흥원", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class UipaCollector(BaseCollector):
    """울산정보산업진흥원 https://uipa.or.kr"""
    site_key   = "uipa"
    base_url   = "https://uipa.or.kr"
    ssl_verify = False

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/webuser/business/list.html?page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()

        for a in soup.select("a[href]"):
            href  = a.get("href", "") or ""
            title = safe_text(a.get_text())
            if "view.html" not in href and "bd_id=" not in href:
                continue
            full_url = urljoin(
                f"{self.base_url}/webuser/business/list.html", href
            )
            if full_url not in seen and len(title) > 5 and title not in ["주변영역", "전체", "닫기", "열기", "이전", "다음"]:
                seen.add(full_url)
                items.append({"title": title, "detail_url": full_url})

        log.debug("[uipa] parse_list_page: %d개 발견", len(items))
        if not items:
            log.warning("[uipa] 파싱 결과 0개. HTML 앞 500자: %s", html[:500])
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        # ★ uipa 제목은 dt 태그 두 번째에 있고 날짜 제거 필요
        title = ""
        for dt in soup.select("dt"):
            txt = safe_text(dt.get_text())
            if len(txt) > 5 and txt != "추천":
                # 날짜 패턴 제거 (예: 2026.03.25)
                title = re.sub(r"\d{4}\.\d{2}\.\d{2}$", "", txt).strip()
                break
        if not title:
            title = parse_title(soup)
        # ★ 본문 영역만 추출 (네비게이션 제외)
        content_area = soup.select_one(".view_content, .board-view, .content, #content, .bbs-view")
        if content_area:
            summary_text = safe_text(content_area.get_text(" "))[:300]
        else:
            # 네비게이션 키워드 이후 텍스트만 사용
            nav_end = body_text.find("사업공고")
            summary_text = body_text[nav_end:nav_end+300] if nav_end > 0 else body_text[:300]
        return {
            "title":         title,
            "body_text":     body_text,
            "posted_date":   dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget":        extract_budget(body_text),
            "ministry":      extract_ministry(body_text),
            "agency":        "울산정보산업진흥원",
            "business_type": "",
            "summary":       summary_text,
            "attachments":   parse_attachments(soup, detail_url),
        }


class GiconCollector(BaseCollector):
    """광주정보문화산업진흥원 https://www.gicon.or.kr"""
    site_key = "gicon"
    base_url = "https://www.gicon.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board.es?mid=a10204000000&bid=0006&page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("table tbody tr td.title a, td.subject a, .board-list a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "광주정보문화산업진흥원", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class IrisCollector(BaseCollector):
    """IRIS https://www.iris.go.kr"""
    site_key = "iris"
    base_url = "https://www.iris.go.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/contents/retrieveBsnsAncmListView.do?pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("table tbody tr td a, .list-wrap a, td.subject a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 5 and (
                "retrieveBsnsAncmDetailView" in href or
                "ancmId=" in href or
                "bsnsId=" in href
            ):
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        for node in soup.select("[onclick]"):
            oc    = node.get("onclick", "") or ""
            title = safe_text(node.get_text())
            for m in re.finditer(r"['\"]([^'\"]*BsnsAncm[^'\"]*)['\"]", oc):
                href = urljoin(self.base_url, m.group(1))
                if href not in seen and len(title) > 5:
                    seen.add(href)
                    items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "IRIS", "business_type": "R&D",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class KiatCollector(BaseCollector):
    """한국산업기술진흥원 https://www.kiat.or.kr"""
    site_key = "kiat"
    base_url = "https://www.kiat.or.kr"

    def get_list_url(self, page: int) -> str:
        # 🛑 [액션 필요] 웹사이트 개편으로 인한 URL 변경. 
        # 브라우저에서 최신 사업공고 게시판 접속 후, 아래 URL을 교체해주세요.
        # page 번호가 들어가는 곳은 {page} 로 처리하시면 됩니다.
        # (예시: return f"{self.base_url}/front/board/boardContentsList.do?board_id=226&pageIndex={page}")
        
        # 임시 적용 URL (작동하지 않으면 실제 URL로 교체 필요)
        return f"{self.base_url}/site/main/board/boardList.do?boardId=1&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        
        # UI 개편에 대비하여 a 태그 추출 셀렉터를 폭넓게 추가
        for a in soup.select("td.subject a, td.title a, .bbs-list td a, .board-list td.title a, div.list_wrap a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "한국산업기술진흥원", "business_type": "산업기술",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

class SmbaCollector(BaseCollector):
    """중소벤처기업부 https://www.mss.go.kr"""
    site_key = "smba"
    base_url = "https://www.mss.go.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/site/smba/ex/bbs/List.do?cbIdx=86&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("td.subject a, td.title a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text),
            "ministry": "중소벤처기업부", "agency": "중소벤처기업부",
            "business_type": "중소기업지원",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class InnopolisCollector(BaseCollector):
    """연구개발특구진흥재단 https://www.innopolis.or.kr"""
    site_key = "innopolis"
    base_url = "https://www.innopolis.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/bbs/board.php?bo_table=notice&page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select(".bo_tit a, td.title a, .list_wrap a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "연구개발특구진흥재단", "business_type": "R&D",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class NipaCollector(BaseCollector):
    """정보통신산업진흥원(NIPA) https://www.nipa.kr"""
    site_key = "nipa"
    base_url = "https://www.nipa.kr"

    def get_list_url(self, page: int) -> str:
        # NIPA 사업공고 게시판 URL 구조
        return f"{self.base_url}/site/main/board/notice/list?pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        # NIPA 특유의 리스트 UI 대응
        for a in soup.select("td.subject a, .board-list td.title a, div.list_wrap a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = safe_text(soup.get_text(" "))
        dates     = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "NIPA(정보통신산업진흥원)", "business_type": "IT/SW/AI",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }



# =============================================================================
# 신규 TP 컬렉터들 (board.es 계열)
# =============================================================================

class BoardEsCollector(BaseCollector):
    """board.es 기반 TP 공통 수집기"""
    bid: str = "0001"
    mid_path: str = ""

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board.es?mid={self.mid_path}&bid={self.bid}&nPage={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, .board-list td a, td.title a, td.subject a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": self.site_key.upper(), "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class DjtpCollector(BoardEsCollector):
    """대전TP https://www.djtp.or.kr"""
    site_key = "djtp"
    base_url  = "https://www.djtp.or.kr"
    mid_path  = "a10401000000"

class CtpCollector(BoardEsCollector):
    """충남TP https://www.ctp.or.kr"""
    site_key = "ctp"
    base_url  = "https://www.ctp.or.kr"
    mid_path  = "a10401000000"

class JntpCollector(BaseCollector):
    """전남TP https://www.jntp.or.kr"""
    site_key = "jntp"
    base_url  = "https://www.jntp.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/base/board/list?boardManagementNo=13&menuLevel=2&menuNo=46&page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        # 전남TP: table 기반 게시판
        for a in soup.select("table tbody tr td a, td.title a, td.subject a, .board-list a"):
            href  = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3 and "boardManagementNo" not in href:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup      = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates     = extract_dates(body_text)
        return {
            "title":         parse_title(soup),
            "body_text":     body_text,
            "posted_date":   dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget":        extract_budget(body_text),
            "ministry":      extract_ministry(body_text),
            "agency":        "전남테크노파크",
            "business_type": "",
            "summary":       body_text[:300],
            "attachments":   parse_attachments(soup, detail_url),
        }

class GwtpCollector(BoardEsCollector):
    """강원TP https://www.gwtp.or.kr"""
    site_key = "gwtp"
    base_url  = "https://www.gwtp.or.kr"
    mid_path  = "a10401000000"   # ★ 수정: a10201 → a10401 (공지사항 경로)

class GbtpCollector(BaseCollector):
    site_key = "gbtp"
    base_url  = "https://www.gbtp.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/user/board.do?bbsId=BBSMSTR_000000000021&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, td.title a, td.subject a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "경북테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

class GtpCollector(BaseCollector):
    """경기TP https://www.gtp.or.kr"""
    site_key = "gtp"
    base_url  = "https://www.gtp.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/web/board/list.do?menuIdx=32&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, td.title a, td.subject a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "경기테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

class BtpCollector(BaseCollector):
    """부산TP https://www.btp.or.kr"""
    site_key  = "btp"
    base_url  = "https://www.btp.or.kr"
    _encoding = "utf-8"   # 실제 응답 인코딩 (euc-kr / utf-8 자동 감지)

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/kor/CMS/Board/Board.do?mCode=MN058&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, td.title a, td.subject a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "부산테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

class JbtpCollector(BaseCollector):
    """전북TP https://www.jbtp.or.kr"""
    site_key = "jbtp"
    base_url  = "https://www.jbtp.or.kr"

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/board/list.do?boardId=BBS_0000000000000003&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, td.title a, td.subject a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "전북테크노파크", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

class SmartFactoryCollector(BaseCollector):
    site_key = "smart"
    base_url  = "https://www.smart-factory.kr"

    def get_list_url(self, page: int) -> str:
        # 스마트공장 사업공고 경로 (404 수정)
        return f"{self.base_url}/usr/bbs/bbsList.do?menuNo=00000157&pageIndex={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen: set = set()
        for a in soup.select("table tbody tr td a, .notice-list a, td.title a, td.subject a, ul.list li a"):
            href = urljoin(self.base_url, (a.get("href") or "").strip())
            title = safe_text(a.get_text())
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body_text = _extract_summary(soup, safe_text(soup.get_text(" ")))
        dates = extract_dates(body_text)
        return {
            "title": parse_title(soup), "body_text": body_text,
            "posted_date": dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget": extract_budget(body_text), "ministry": extract_ministry(body_text),
            "agency": "스마트제조혁신추진단", "business_type": "스마트공장",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }

COLLECTOR_REGISTRY: Dict[str, type] = {
    "bizinfo":   BizinfoCollector,
    "cbtp":      CbtpCollector,
    "ttp":       TtpCollector,
    "jejutp":    JejutpCollector,
    "dicia":     DiciaCollector,
    "bipa":      BipaCollector,
    "uipa":      UipaCollector,
    "gicon":     GiconCollector,
    "iris":      IrisCollector,
    "smba":      SmbaCollector,
    "innopolis": InnopolisCollector,
    "djtp":      DjtpCollector,
    "ctp":       CtpCollector,
    "jntp":      JntpCollector,
    "gwtp":      GwtpCollector,
    "gbtp":      GbtpCollector,
    "gtp":       GtpCollector,
    "btp":       BtpCollector,
    "jbtp":      JbtpCollector,
    "smart":     SmartFactoryCollector,
}


def build_collectors(site_keys: Optional[List[str]] = None,
                     max_pages: int = MAX_PAGES,
                     timeout: int = COLLECTOR_TIMEOUT) -> List[BaseCollector]:
    keys = site_keys or list(COLLECTOR_REGISTRY.keys())
    return [
        COLLECTOR_REGISTRY[k](max_pages=max_pages, timeout=timeout)
        for k in keys if k in COLLECTOR_REGISTRY
    ]


# =============================================================================
# 8. 점수 엔진
# =============================================================================

class ScoreEngine:
    def __init__(self):
        self.pos_kw  = {k.lower(): v for k, v in POSITIVE_KEYWORDS.items()}
        self.neg_kw  = {k.lower(): v for k, v in NEGATIVE_KEYWORDS.items()}
        self.sol_map = {sol: {k.lower(): v for k, v in kws.items()} for sol, kws in SOLUTION_MAP.items()}

    def _full_text(self, n: Notice) -> str:
        parts = [n.title, n.summary, n.business_type, n.agency, n.ministry]
        # structured 섹션별 정제 텍스트 우선 사용
        for sec, val in (n.structured or {}).items():
            cleaned = clean_section_text(val, 300)
            if cleaned:
                parts.append(cleaned)
        # 첨부파일 텍스트 (핵심 500자)
        for att in n.attachment_items or []:
            txt = att.get("text", "")
            if txt:
                parts.append(clean_section_text(txt, 500))
        return " ".join(p for p in parts if p).lower()

    def score_one(self, notice: Notice) -> ScoreCard:
        text = self._full_text(notice)

        # InterX 절대 필수(Core) 키워드 세트 정의 및 하드 필터
        CORE_KEYWORDS = {
            "제조", "스마트공장", "스마트팩토리", "디지털트윈", "예지보전",
            "산업ai", "제조ai", "공정", "설비", "머신비전", "ax",
            "ai", "인공지능", "데이터", "실증", "자동화", "iot", "센서",
            "로봇", "품질", "안전", "클라우드", "플랫폼", "poc",
        }
        core_found = any(kw in text for kw in CORE_KEYWORDS)

        pos_hits = []
        pos_score = 0.0
        for kw, w in self.pos_kw.items():
            if kw in text:
                pos_hits.append(kw)
                pos_score += w

        neg_hits = []
        neg_score = 0.0
        for kw, w in self.neg_kw.items():
            if kw in text:
                neg_hits.append(kw)
                neg_score += w

        struct_bonus = 0.0
        core_text = (notice.structured.get("사업목적", "") + " " + notice.structured.get("지원내용", "")).lower()
        
        for kw, w in self.pos_kw.items():
            if kw in core_text:
                struct_bonus += (w * 1.5)
                if kw not in pos_hits:
                    pos_hits.append(kw)

        if notice.structured.get("지원대상"): struct_bonus += 2.0
        if notice.budget: struct_bonus += 3.0

        # 코어 키워드 누락 시 0점 강제 할당
        if not core_found:
            raw_fit = 0.0
            log.debug("[Score] 필수 제조/AI 키워드 누락으로 0점 처리: %s", notice.title[:30])
        # 가점 키워드만 히트 (순수 가점 1~2점짜리만) → 제외
        elif pos_score <= 3.0 and not any(kw in text for kw in [
            "ai", "인공지능", "제조", "실증", "자동화", "로봇", "품질", "안전",
            "데이터", "공정", "설비", "센서", "모니터링", "디지털트윈", "예지보전"
        ]):
            raw_fit = 0.0
            log.debug("[Score] 가점 키워드만 히트, 제외: %s", notice.title[:30])
        else:
            raw_fit = (pos_score * 5.0) - (neg_score * 6.0) + struct_bonus

        fitness = max(0.0, min(100.0, raw_fit))

        sol_scores = {}
        for sol, kws in self.sol_map.items():
            s = sum(w * (1.2 if kw in core_text else 1.0) for kw, w in kws.items() if kw in text)
            sol_scores[sol] = round(min(100.0, s * 15.0), 1) if core_found else 0.0

        industry_score = round(sum(sol_scores.values()) / max(len(sol_scores), 1), 1) if sol_scores else 0.0
        priority = round(fitness * 0.6 + industry_score * 0.4, 1)
        grade = ("P1" if priority >= 80 else
                 "P2" if priority >= 65 else
                 "P3" if priority >= 50 else "P4")

        top3 = sorted(sol_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        notice.recommended_solution = " / ".join(s for s, v in top3 if v > 0) or "-"
        notice.recommended_action   = "제안 검토" if priority >= L3_STRONG_THRESHOLD else "모니터링"
        notice.l3_strong            = "Y" if fitness >= L3_STRONG_THRESHOLD else "N"
        notice.partner_candidate    = (
            "Y" if (priority >= PARTNER_CAND_THRESHOLD and notice.l3_strong != "Y") else "N"
        )

        return ScoreCard(
            execution_id=notice.execution_id, notice_id=notice.notice_id, site=notice.site,
            fitness_score=round(fitness, 1), priority_score=priority, priority_grade=grade,
            solution_scores=sol_scores, positive_keywords=pos_hits[:10],
            negative_keywords=neg_hits[:5], industry_score=industry_score,
        )

    def score_all(self, notices: List[Notice]) -> Tuple[List[Notice], List[ScoreCard]]:
        return notices, [self.score_one(n) for n in notices]



# =============================================================================
# 9. 첨부파일 다운로더
# =============================================================================

def classify_download_error(err: str, url: str) -> str:
    e = (err or "").lower(); u = (url or "").lower()
    if not url:                                return "empty_url"
    if "youtube.com" in u or "youtu.be" in u: return "non_file_link:youtube"
    if "ssl" in e or "certificate" in e:       return "ssl_error"
    if "http_403" in e:                        return "forbidden_403"
    if "http_404" in e:                        return "not_found_404"
    if "http_410" in e:                        return "gone_410"
    if "http_429" in e:                        return "rate_limited_429"
    if "http_5" in e:                          return "server_error_5xx"
    if "timed out" in e or "timeout" in e:     return "timeout"
    if "connection reset" in e:                return "connection_reset"
    if "connection refused" in e:              return "connection_refused"
    if "name or service not known" in e:       return "dns_error"
    if "empty_file" in e:                      return "empty_file"
    return "unknown_error"


class AttachmentDownloader:
    def __init__(self, base_dir: str = ATTACHMENT_DIR,
                 timeout: int = 15, max_workers: int = MAX_WORKERS):
        self.base_dir    = Path(base_dir)
        self.timeout     = timeout
        self.max_workers = max_workers
        self.session     = make_session()

    def _dest(self, notice: Notice, name: str, ext: str) -> Path:
        safe = re.sub(r'[\\/:*?"<>|]', "_", name)
        if ext and not safe.lower().endswith(f".{ext}"):
            safe += f".{ext}"
        return self.base_dir / notice.site / notice.notice_id / safe

    def _download_one(self, url: str, dest: Path, referer: str = "") -> Tuple[bool, str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        headers = dict(DEFAULT_HEADERS)
        if referer:
            headers["Referer"] = referer
        for attempt in range(1, 5):
            try:
                with self.session.get(url, headers=headers, timeout=(10, self.timeout),
                                      stream=True, allow_redirects=True) as resp:
                    if resp.status_code >= 400:
                        time.sleep(0.8 * attempt)
                        return False, f"http_{resp.status_code}"
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            if chunk:
                                f.write(chunk)
                if dest.exists() and dest.stat().st_size > 0:
                    return True, ""
                return False, "empty_file"
            except requests.exceptions.SSLError:
                try:
                    with self.session.get(url, headers=headers, timeout=(10, self.timeout),
                                          stream=True, verify=False) as r2:
                        if r2.status_code >= 400:
                            return False, f"http_{r2.status_code}|ssl_bypassed"
                        with open(dest, "wb") as f:
                            for chunk in r2.iter_content(8192):
                                if chunk:
                                    f.write(chunk)
                    if dest.exists() and dest.stat().st_size > 0:
                        return True, ""
                except Exception as e2:
                    return False, f"ssl_bypass_failed:{str(e2)[:80]}"
            except Exception as e:
                time.sleep(1.0 * attempt)
                if attempt == 4:
                    return False, f"{type(e).__name__}:{str(e)[:100]}"
        return False, "max_retries"

    def process_notice(self, notice: Notice) -> Dict[str, int]:
        downloaded = failed = skipped = 0
        for i, att in enumerate(notice.attachment_items or [], start=1):
            name = (att.get("name") or f"attachment_{i}").strip()
            url  = (att.get("url") or "").strip()
            ext  = (att.get("ext") or _ext_from_text(url)).lower()
            att.update({"download_status": "skipped", "parse_status": "skipped", "parse_error": ""})
            if not url:
                att["download_status"] = "failed"; att["parse_error"] = "empty_url"
                failed += 1; continue
            dest = self._dest(notice, name, ext)
            att["local_path"] = str(dest)
            # ★ 신청서/양식류 스킵
            skip_keywords = ["신청서", "신청양식", "제출서류", "양식", "개인정보", "동의서"]
            if any(kw in name for kw in skip_keywords):
                att["download_status"] = "skipped"
                skipped += 1
                continue
            # ★ 이미 다운로드된 파일 스킵 (재실행 시 속도 대폭 향상)
            if dest.exists() and dest.stat().st_size > 0:
                att["download_status"] = "downloaded"
                downloaded += 1
                log.debug("[DL] 캐시 사용: %s", dest.name)
                continue
            ok, err = self._download_one(url, dest, referer=notice.detail_url)
            if not ok:
                att["download_status"] = "failed"
                att["parse_error"]     = classify_download_error(err, url)
                failed += 1
                log.warning("[DL] 실패 %s/%s reason=%s", notice.notice_id, name, att["parse_error"])
            else:
                att["download_status"] = "downloaded"; downloaded += 1
        return {"downloaded": downloaded, "failed": failed, "skipped": skipped}

    def process_all(self, notices: List[Notice]) -> Dict[str, int]:
        total = {"downloaded": 0, "failed": 0, "skipped": 0}
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(self.process_notice, n): n for n in notices}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    for k in total:
                        total[k] += res.get(k, 0)
                except Exception as e:
                    log.error("[DL] 예외: %s", e)
        return total


# =============================================================================
# 10. 문서 파서
# =============================================================================

class DocumentParser:
    MAX_PAGES = 20
    MAX_CHARS = 20_000

    def parse(self, local_path: str, ext: str) -> Tuple[str, str, str]:
        p = Path(local_path)
        if not p.exists() or p.stat().st_size == 0:
            return "failed", "file_not_found_or_empty", ""
        e = (ext or "").lower().strip(".")
        try:
            if e == "pdf":              return self._pdf(p)
            if e == "hwpx":             return self._hwpx(p)
            if e in ("doc", "docx"):    return self._docx(p)
            if e == "hwp":
                return self._hwp_libreoffice(p)
            return "skipped", f"unsupported:{e}", ""
        except Exception as ex:
            return "failed", f"{type(ex).__name__}:{str(ex)[:200]}", ""

    def _pdf(self, p: Path) -> Tuple[str, str, str]:
        # 1차: pdfplumber (텍스트 기반 PDF)
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(str(p)) as pdf:
                for pg in pdf.pages[: self.MAX_PAGES]:
                    t = pg.extract_text() or ""
                    if t.strip():
                        texts.append(t)
            full = "".join(texts).strip()[: self.MAX_CHARS]
            if full:
                return "parsed", "", full
        except Exception:
            pass

        # 2차: pypdf fallback
        if PYPDF_AVAILABLE:
            try:
                reader = PdfReader(str(p))
                texts = []
                for pg in reader.pages[: self.MAX_PAGES]:
                    t = pg.extract_text() or ""
                    if t.strip():
                        texts.append(t)
                full = "".join(texts).strip()[: self.MAX_CHARS]
                if full:
                    return "parsed", "", full
            except Exception:
                pass

        # 3차: EasyOCR fallback (스캔 PDF)
        try:
            import fitz  # PyMuPDF
            import easyocr
            reader_ocr = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
            doc = fitz.open(str(p))
            texts = []
            for i, page in enumerate(doc):
                if i >= self.MAX_PAGES:
                    break
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                results = reader_ocr.readtext(img_bytes, detail=0)
                texts.append(" ".join(results))
            doc.close()
            full = " ".join(texts).strip()[: self.MAX_CHARS]
            if full:
                return "parsed", "ocr", full
        except Exception as e:
            return "failed", f"pdf_ocr:{str(e)[:100]}", ""

        return "skipped", "pdf_no_text", ""

    def _hwpx(self, p: Path) -> Tuple[str, str, str]:
        texts: List[str] = []
        with zipfile.ZipFile(p, "r") as zf:
            targets = sorted([
                n for n in zf.namelist()
                if n.lower().endswith(".xml")
                and any(kw in n.lower() for kw in ["section", "content", "body"])
            ])
            for name in targets[: self.MAX_PAGES]:
                try:
                    raw = zf.read(name).decode("utf-8", errors="ignore")
                    t   = re.sub(r"<[^>]+>", " ", raw)
                    t   = re.sub(r"\s+", " ", t).strip()
                    if t:
                        texts.append(t)
                except Exception:
                    pass
        full = "".join(texts).strip()[: self.MAX_CHARS]
        return ("parsed" if full else "skipped"), "", full

    def _docx(self, p: Path) -> Tuple[str, str, str]:
        if not DOCX_AVAILABLE:
            return "skipped", "python_docx_not_installed", ""
        doc   = python_docx.Document(str(p))
        lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        full  = "".join(lines)[: self.MAX_CHARS]
        return ("parsed" if full else "skipped"), "", full


    def _hwp_libreoffice(self, p: Path) -> Tuple[str, str, str]:
        """HWP 파싱: PrvText(미리보기) → BodyText 순서로 시도"""
        try:
            import olefile, zlib
            ole = olefile.OleFileIO(str(p))

            # 1차: PrvText (미리보기 텍스트 - 가장 안정적)
            if ole.exists("PrvText"):
                data = ole.openstream("PrvText").read()
                text = data.decode("utf-16-le", errors="ignore").strip()
                text = re.sub(r"[<>]", " ", text)  # 태그 제거
                text = re.sub(r"\s+", " ", text)[: self.MAX_CHARS]
                if len(text) > 50:
                    ole.close()
                    return "parsed", "", text

            # 2차: BodyText/Section0
            if ole.exists("BodyText/Section0") and ole.exists("FileHeader"):
                header = ole.openstream("FileHeader").read()
                is_compressed = header[36] & 1
                data = ole.openstream("BodyText/Section0").read()
                if is_compressed:
                    data = zlib.decompress(data, -15)
                text = ""
                i = 0
                while i + 4 <= len(data):
                    tag_id = (data[i] | data[i+1] << 8) & 0x3FF
                    size   = (data[i+2] | data[i+3] << 8) & 0xFFFF
                    i += 4
                    if tag_id == 67 and i + size <= len(data):
                        text += data[i:i+size].decode("utf-16-le", errors="ignore")
                    i += size
                text = re.sub(r"\s+", " ", text.strip())[: self.MAX_CHARS]
                if len(text) > 50:
                    ole.close()
                    return "parsed", "", text

            ole.close()
        except Exception as e:
            return "failed", f"hwp:{str(e)[:80]}", ""
        return "skipped", "hwp_no_text", ""


def parse_attachments_in_notices(notices: List[Notice]) -> Dict[str, int]:
    parser = DocumentParser()
    parsed = failed = skipped = 0
    
    import os
    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key) if api_key else None
    except ImportError:
        client = None

    for n in notices:
        for att in n.attachment_items or []:
            if att.get("download_status") != "downloaded":
                continue
            local = att.get("local_path", "")
            ext   = att.get("ext", "").lower()
            name  = att.get("name", "").lower()
            if not local:
                continue
            # 포스터/이미지/압축 스킵
            if ext in ("jpg", "jpeg", "png", "gif", "zip", "xls", "xlsx", "hwpx"):
                att["parse_status"] = "skipped"; skipped += 1; continue
            if any(kw in name for kw in ["포스터", "poster", "이미지", "배너", "홍보물"]):
                att["parse_status"] = "skipped"; skipped += 1; continue
            # hwpx → hwp 파서로 fallback
            if ext == "hwpx":
                ext = "hwp"
            
            # 파싱 상태 초기화 (캐시 무시하고 무조건 재파싱)
            att["parse_status"] = ""
            status, err, text = parser.parse(local, ext)
            
            # [LLM 정밀 파싱 로직 - 발동 조건 완화]
            # 텍스트가 100자 이상이고, 이미지/압축파일이 아니면 무조건 실행!
            is_valid_ext = ext.lower() in ["pdf", "hwp", "hwpx", "doc", "docx"]
            
            if status == "parsed" and len(text.strip()) > 100 and client and is_valid_ext:
                try:
                    import time
                    time.sleep(3) # Rate Limit 3초 대기
                    import logging
                    logging.getLogger("interx").info("[LLM Parsing] %s (%s) 🚀 강제 정밀 분석 가동!", n.notice_id, att.get("name", ""))
                    
                    prompt = f"""
너는 최고의 사업 기획자야. 아래는 공공기관의 첨부파일에서 추출한 텍스트야. 표나 서식이 깨져있을 수 있어.
어지러운 텍스트 속에서 문맥을 완벽하게 파악해서 아래 항목들만 깔끔하게 JSON 형태로 뽑아줘.

[첨부파일 텍스트]
{text[:15000]}

[출력 요구사항 (반드시 JSON 형식만 출력할 것)]
{{
  "사업목적": "사업의 핵심 목적 1~2줄 요약",
  "지원대상": "구체적인 신청 자격 및 업종",
  "지원규모": "지원 예산, 기업당 한도액 등",
  "필수조건": "특이사항이나 제한조건"
}}"""
                    resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                    
                    import json
                    json_str = re.search(r"\{.*\}", resp.text, re.DOTALL)
                    if json_str:
                        llm_data = json.loads(json_str.group())
                        # 기존 값에 덮어쓰거나 덧붙임
                        n.structured["사업목적"] = llm_data.get("사업목적", "")
                        n.structured["지원대상"] = llm_data.get("지원대상", "")
                        n.structured["예산"]     = llm_data.get("지원규모", "")
                        n.structured["지원조건"] = llm_data.get("필수조건", "")
                        
                        text = f"■ [LLM 정밀 파싱 성공] ■{json.dumps(llm_data, ensure_ascii=False, indent=2)}■ [원본 텍스트] ■{text}"
                        logging.getLogger("interx").info("[LLM Parsing] %s 완료! (JSON 주입)", n.notice_id)
                except Exception as e:
                    import logging
                    logging.getLogger("interx").debug("[LLM Parsing Error] %s", e)
            
            if not text.strip():
                text = f"{att.get('name', '첨부파일')} (문서 파싱 불가로 파일명 대체)"
            
            att["parse_status"] = status
            att["parse_error"]  = err
            att["text"]         = text
            att["text_len"]     = len(text)
            
            if status == "parsed":   parsed += 1
            elif status == "failed": failed += 1
            else:                    skipped += 1
            
    return {"parsed": parsed, "failed": failed, "skipped": skipped}


# =============================================================================
# 11. SQLite
# =============================================================================

class SQLiteGateway:
    DDL = """
    CREATE TABLE IF NOT EXISTS notices (
        notice_key TEXT PRIMARY KEY,
        execution_id TEXT, site TEXT, notice_id TEXT,
        title TEXT, detail_url TEXT, posted_date TEXT, deadline_date TEXT,
        ministry TEXT, agency TEXT, business_type TEXT, budget TEXT,
        l3_strong TEXT, partner_candidate TEXT,
        fitness_score REAL, priority_score REAL, priority_grade TEXT,
        status TEXT, created_at TEXT, updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notice_key TEXT, execution_id TEXT, notice_id TEXT,
        file_no INTEGER, name TEXT, url TEXT, local_path TEXT,
        download_status TEXT, parse_status TEXT, parse_error TEXT, text_len INTEGER
    );
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        execution_id TEXT PRIMARY KEY,
        site_keys TEXT, notice_count INTEGER, attachment_count INTEGER,
        downloaded INTEGER, parsed INTEGER, l3_count INTEGER,
        partner_count INTEGER, elapsed_sec REAL, created_at TEXT
    );
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path), timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init(self) -> None:
        with self._con() as con:
            con.executescript(self.DDL)

    def existing_keys(self) -> set:
        with self._con() as con:
            return {r[0] for r in con.execute("SELECT notice_key FROM notices").fetchall()}

    def upsert_notices(self, notices: List[Notice], score_map: Dict[str, ScoreCard]) -> None:
        now  = datetime.now().isoformat()
        rows = []
        for n in notices:
            s = score_map.get(n.notice_id)
            rows.append((
                n.notice_key, n.execution_id, n.site, n.notice_id,
                n.title, n.detail_url, n.posted_date, n.deadline_date,
                n.ministry, n.agency, n.business_type, n.budget,
                n.l3_strong, n.partner_candidate,
                (s.fitness_score  if s else None),
                (s.priority_score if s else None),
                (s.priority_grade if s else None),
                n.status, now, now,
            ))
        with self._con() as con:
            con.executemany(
                """INSERT INTO notices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(notice_key) DO UPDATE SET
                   status=excluded.status, updated_at=excluded.updated_at,
                   fitness_score=excluded.fitness_score,
                   priority_score=excluded.priority_score""",
                rows,
            )

    def upsert_attachments(self, notices: List[Notice]) -> None:
        rows = []
        for n in notices:
            for i, a in enumerate(n.attachment_items or [], start=1):
                rows.append((
                    n.notice_key, n.execution_id, n.notice_id,
                    i, a.get("name", ""), a.get("url", ""),
                    a.get("local_path", ""), a.get("download_status", ""),
                    a.get("parse_status", ""), a.get("parse_error", ""),
                    a.get("text_len", 0),
                ))
        with self._con() as con:
            con.executemany(
                """INSERT INTO attachments
                   (notice_key, execution_id, notice_id, file_no, name, url,
                    local_path, download_status, parse_status, parse_error, text_len)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )

    def save_run(self, execution_id: str, **kw) -> None:
        with self._con() as con:
            con.execute(
                "INSERT OR REPLACE INTO pipeline_runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (execution_id, kw.get("site_keys",""), kw.get("notice_count",0),
                 kw.get("attachment_count",0), kw.get("downloaded",0),
                 kw.get("parsed",0), kw.get("l3_count",0), kw.get("partner_count",0),
                 kw.get("elapsed_sec",0.0), datetime.now().isoformat()),
            )


# =============================================================================
# 12. Google Sheets
# =============================================================================

class GoogleSheetGateway:
    SCOPES     = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
    BATCH_SIZE = 500

    def __init__(self, spreadsheet_name: str = SPREADSHEET_NAME,
                 service_account_json: str = SERVICE_ACCOUNT_JSON):
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread 미설치")
        # gspread 6.x: authorize() 제거됨 → service_account() 사용
        try:
            client = gspread.service_account(
                filename=service_account_json,
                scopes=self.SCOPES,
            )
        except Exception:
            # fallback: 구버전 gspread 호환
            creds  = Credentials.from_service_account_file(service_account_json, scopes=self.SCOPES)
            client = gspread.Client(auth=creds)
            client.session = gspread.auth.HTTPClient(creds)
        self._ss       = client.open(spreadsheet_name)
        self._ws_cache: Dict[str, Any] = {}

    def _ws(self, sheet_name: str):
        if sheet_name not in self._ws_cache:
            try:
                self._ws_cache[sheet_name] = self._ss.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                # 시트 없으면 자동 생성
                ws = self._ss.add_worksheet(title=sheet_name, rows=2000, cols=60)
                self._ws_cache[sheet_name] = ws
                log.info("Sheets: 새 시트 생성 → %s", sheet_name)
        return self._ws_cache[sheet_name]

    def _ensure_header(self, ws, rows: List[Dict[str, Any]]) -> None:
        """첫 행이 비어있으면 헤더(컬럼명) 자동 삽입."""
        try:
            existing = ws.row_values(1)
            if not existing or existing[0] == "":
                ws.insert_row(list(rows[0].keys()), index=1)
        except Exception:
            pass

    def append_rows_batch(self, sheet_key: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        sheet_name = SHEET_MAP.get(sheet_key, sheet_key)
        ws         = self._ws(sheet_name)
        self._ensure_header(ws, rows)
        
        # [수정2: 시트 헤더 무시, 코드의 SHEET_COLUMNS 절대 기준 매핑]
        expected_columns = SHEET_COLUMNS.get(sheet_key, list(rows[0].keys()) if rows else [])

        values = []
        for r in rows:
            row_data = []
            for col_name in expected_columns:
                val = r.get(col_name, "")
                row_data.append(str(val) if val is not None else "")
            values.append(row_data)

        for i in range(0, len(values), self.BATCH_SIZE):
            batch = values[i: i + self.BATCH_SIZE]
            ws.append_rows(batch, value_input_option="USER_ENTERED", table_range="A1")
            import logging
            logging.getLogger("interx").info("[Sheets] %s: %d행 append (절대 기준 매핑 완료)", sheet_name, len(batch))
            import time
            time.sleep(0.5)


# =============================================================================
# 13. Row 매퍼
# =============================================================================
def notice_to_master_row(notice: Notice, score: Optional[ScoreCard] = None) -> Dict[str, Any]:
    sol = score.solution_scores if score else {}
    today = date.today()
    if notice.deadline_date:
        try:
            dl = date.fromisoformat(notice.deadline_date)
            dday = (dl - today).days
            dday_str = f"D-{abs(dday)}" if dday < 0 else f"D+{dday}" if dday > 0 else "D-day"
        except Exception:
            dday_str = ""
    else:
        dday_str = ""

    if notice.detail_url:
        safe_title = re.sub(r'[\x00-\x1f"]', "", notice.title or "")
        link_formula = f'=HYPERLINK("{notice.detail_url}","{safe_title}")'
    else:
        link_formula = notice.title or ""

    # 사업요약 정제 (SECTION_SPEC 기반)
    raw_summary = notice.llm_summary or notice.summary or ""
    # structured에서 핵심 섹션 우선 사용
    if notice.structured:
        parts = []
        for sec in ["사업목적", "지원대상", "지원내용"]:
            val = notice.structured.get(sec, "")
            if val:
                parts.append(clean_section_text(val, 150))
        if parts:
            raw_summary = " | ".join(parts)
    clean_summary = clean_section_text(raw_summary, 300)

    # 공고명 D-숫자/마감 접두어 제거
    clean_title = re.sub(r"^(D-\d+|마감)\s*", "", notice.title or "").strip()

    return {
        "사이트":           notice.site,
        "공고명":           clean_title,
        "공고명링크":       link_formula,
        "상세URL":         notice.detail_url or "",
        "등록일":           notice.posted_date or "",
        "마감일":           notice.deadline_date or "",
        "D-day":           dday_str,
        "상태":             notice.status or "",
        "주무부처":         notice.ministry or "",
        "수행기관":         notice.agency or "",
        "예산":             notice.budget or "",
        "적합도점수":       score.fitness_score if score else "",
        "우선순위등급":     score.priority_grade if score else "",
        "추천솔루션":       notice.recommended_solution or "",
        "사업요약":         clean_summary,
        "ManufacturingDT점수": sol.get("ManufacturingDT", ""),
        "RecipeAI점수":    sol.get("RecipeAI", ""),
        "QualityAI점수":   sol.get("QualityAI", ""),
        "InspectionAI점수": sol.get("InspectionAI", ""),
        "SafetyAI점수":    sol.get("SafetyAI", ""),
        "GenAI점수":       sol.get("GenAI", ""),
        "InfraDS점수":     sol.get("InfraDS", ""),
        "PdM점수":         sol.get("PdM", ""),
        "산업키워드":       " | ".join(score.positive_keywords) if score else "",
        "적합키워드":       " | ".join(score.positive_keywords) if score else "",
        "첨부수":           len(notice.attachments),
        "첨부명":           " | ".join(notice.attachments[:5]),
        "첨부URL":         " | ".join(a.get("url","") for a in (notice.attachment_items or [])[:5]),
        "담당자":           notice.manager or "",
        "검토상태":         "",
        "다음액션":         "",
        "메모":             "",
        "L3강공고":         notice.l3_strong or "",
        "파트너후보":       notice.partner_candidate or "",
    }


def notice_to_attachment_rows(notice: Notice) -> List[Dict[str, Any]]:
    return [{
        "공고ID": notice.notice_id, "사이트": notice.site,
        "공고명": notice.title, "공고상세링크": notice.detail_url,
        "파일순번": i, "파일명": a.get("name",""), "원본URL": a.get("url",""),
        "다운로드링크": a.get("url",""), "local_path": a.get("local_path",""),
        "download_status": a.get("download_status",""),
        "parse_status": a.get("parse_status",""), "parse_error": a.get("parse_error",""),
    } for i, a in enumerate(notice.attachment_items or [], start=1)]


def make_exec_log_row(execution_id: str, site: str, notice_count: int,
                       att_count: int, downloaded: int, parsed: int,
                       l3_count: int, partner_count: int,
                       elapsed: float, status: str = "OK") -> Dict[str, Any]:
    return {
        "실행ID": execution_id, "실행시각": datetime.now().isoformat(), "사이트": site,
        "수집건수": notice_count, "첨부수": att_count, "다운로드성공": downloaded,
        "파싱성공": parsed, "L3강공고수": l3_count, "파트너후보수": partner_count,
        "소요초": round(elapsed, 1), "상태": status,
    }


def make_error_log_rows(errors: List[ErrorRecord]) -> List[Dict[str, Any]]:
    return [{
        "실행ID": e.execution_id, "사이트": e.site, "공고ID": e.notice_id,
        "단계": e.stage, "오류유형": e.error_type, "오류내용": e.error_msg,
        "발생시각": e.occurred_at,
    } for e in errors]


# =============================================================================
# 14. 파이프라인
# =============================================================================

class DailyPipelineOrchestrator:
    def __init__(self, collectors: List[BaseCollector],
                 sheet_gateway: Optional[GoogleSheetGateway] = None,
                 sqlite_gateway: Optional[SQLiteGateway] = None,
                 attachment_dir: str = ATTACHMENT_DIR):
        self.collectors     = collectors
        self.sheet_gateway  = sheet_gateway
        self.sqlite_gateway = sqlite_gateway
        self.downloader     = AttachmentDownloader(base_dir=attachment_dir)
        self.scorer         = ScoreEngine()

    def _collect_all(self, execution_id: str) -> Tuple[List[Notice], List[ErrorRecord]]:
        all_notices: List[Notice]      = []
        all_errors:  List[ErrorRecord] = []

        SITE_TIMEOUT = 120  # ★ v4.1: 사이트당 최대 120초

        with ThreadPoolExecutor(max_workers=min(len(self.collectors), MAX_WORKERS)) as ex:
            futures = {ex.submit(c.collect, execution_id): c for c in self.collectors}
            for fut in as_completed(futures, timeout=SITE_TIMEOUT * max(len(self.collectors), 1)):
                col = futures[fut]
                try:
                    notices = fut.result(timeout=SITE_TIMEOUT)  # ★ v4.1
                    all_notices.extend(notices)
                    all_errors.extend(getattr(col, "_errors", []))
                    log.info("[Collect] %s: %d건", col.site_key, len(notices))
                except TimeoutError:
                    log.error("[Collect] %s: 120초 타임아웃 → 스킵", col.site_key)
                    all_errors.append(ErrorRecord(execution_id, col.site_key, "",
                                                  "collector_timeout", "TimeoutError",
                                                  "120s limit exceeded"))
                    fut.cancel()
                except Exception as e:
                    log.error("[Collect] %s 실패: %s", col.site_key, e)
                    all_errors.append(ErrorRecord(execution_id, col.site_key, "",
                                                  "collector", type(e).__name__, str(e)[:300]))
        return all_notices, all_errors

    def run(self, execution_id: str) -> Dict[str, Any]:
        t0 = time.time()
        log.info("===== PIPELINE START %s =====", execution_id)

        notices, errors = self._collect_all(execution_id)
        log.info("[Pipeline] 총 %d건 수집", len(notices))

        if self.sqlite_gateway:
            existing = self.sqlite_gateway.existing_keys()
            before   = len(notices)
            notices  = [n for n in notices if n.notice_key not in existing]
            log.info("[Dedup] %d → %d (중복 %d)", before, len(notices), before - len(notices))

        dl_summary    = self.downloader.process_all(notices)
        parse_summary = parse_attachments_in_notices(notices)

        # [핵심 패치] 다운로드 및 파싱 실패 건을 수집하여 에러 로그(96_수집에러로그) 배열에 추가
        for n in notices:
            for att in n.attachment_items or []:
                if att.get("download_status") == "failed":
                    errors.append(ErrorRecord(
                        execution_id, n.site, n.notice_id, 
                        "download_failed", att.get("parse_error", "error"), 
                        f"{att.get('name')} 다운로드 실패"
                    ))
                elif att.get("parse_status") == "failed":
                    errors.append(ErrorRecord(
                        execution_id, n.site, n.notice_id, 
                        "parsing_failed", att.get("parse_error", "error"), 
                        f"[{att.get('ext')}] {att.get('name')} 파싱 실패"
                    ))

        for n in notices:
            try:
                n.llm_summary = llm_summarize(n)  # Notice 객체 전체를 넘겨 구조화 데이터 활용
            except Exception as e:
                log.debug("[LLM] 요약 실패: %s", e)

        # ★ 첨부파일 텍스트 반영해서 점수화
        notices, score_cards = self.scorer.score_all(notices)
        score_map = {s.notice_id: s for s in score_cards}

        before  = len(notices)
        notices = [n for n in notices
                   if score_map.get(n.notice_id) and
                   score_map[n.notice_id].fitness_score >= MIN_FIT_SCORE and
                   n.status not in ("CLOSED", "DEADLINE_PASSED") and
                   not (n.title or "").startswith("마감")]
        log.info("[Filter] 점수 필터 %d → %d", before, len(notices))

        master_rows: List[Dict] = []; attachment_rows: List[Dict] = []
        l3_rows:     List[Dict] = []; partner_rows:    List[Dict] = []
        collect_log_rows: List[Dict] = []

        for n in notices:
            row = notice_to_master_row(n, score_map.get(n.notice_id))
            master_rows.append(row)
            attachment_rows.extend(notice_to_attachment_rows(n))
            if n.l3_strong == "Y":         l3_rows.append(row)
            if n.partner_candidate == "Y": partner_rows.append(row)
            collect_log_rows.append({
                "실행ID": n.execution_id, "사이트": n.site, "공고ID": n.notice_id,
                "공고명": n.title[:60], "등록일": n.posted_date, "마감일": n.deadline_date,
                "첨부수": len(n.attachments), "수집시각": datetime.now().isoformat(),
            })

        elapsed = time.time() - t0

        if self.sheet_gateway:
            try:
                self.sheet_gateway.append_rows_batch("master",      master_rows)
                self.sheet_gateway.append_rows_batch("attachments", attachment_rows)
                if l3_rows:      self.sheet_gateway.append_rows_batch("l3_strong",   l3_rows)
                if partner_rows: self.sheet_gateway.append_rows_batch("partner",     partner_rows)
                self.sheet_gateway.append_rows_batch("collect_log", collect_log_rows)
                if errors: self.sheet_gateway.append_rows_batch("error_log", make_error_log_rows(errors))
                self.sheet_gateway.append_rows_batch("exec_log", [make_exec_log_row(
                    execution_id,
                    site=",".join(c.site_key for c in self.collectors),
                    notice_count=len(notices), att_count=len(attachment_rows),
                    downloaded=dl_summary.get("downloaded",0),
                    parsed=parse_summary.get("parsed",0),
                    l3_count=len(l3_rows), partner_count=len(partner_rows), elapsed=elapsed,
                )])
            except Exception as e:
                log.error("[Sheets] 업로드 실패: %s", e)
                errors.append(ErrorRecord(execution_id,"all","","sheets_upload",
                                          type(e).__name__,str(e)[:300]))

        if self.sqlite_gateway:
            try:
                self.sqlite_gateway.upsert_notices(notices, score_map)
                self.sqlite_gateway.upsert_attachments(notices)
                self.sqlite_gateway.save_run(
                    execution_id,
                    site_keys=",".join(c.site_key for c in self.collectors),
                    notice_count=len(notices), attachment_count=len(attachment_rows),
                    downloaded=dl_summary.get("downloaded",0),
                    parsed=parse_summary.get("parsed",0),
                    l3_count=len(l3_rows), partner_count=len(partner_rows),
                    elapsed_sec=round(elapsed,2),
                )
            except Exception as e:
                log.error("[SQLite] 저장 실패: %s", e)

        result = {
            "execution_id":     execution_id,
            "notice_count":     len(notices),
            "l3_count":         len(l3_rows),
            "partner_count":    len(partner_rows),
            "attachment_count": len(attachment_rows),
            "download_summary": dl_summary,
            "parse_summary":    parse_summary,
            "error_count":      len(errors),
            "elapsed_sec":      round(elapsed, 2),
        }

        log.info("===== PIPELINE DONE =====")
        log.info("notice_count  = %d", result["notice_count"])
        log.info("l3_count      = %d", result["l3_count"])
        log.info("partner_count = %d", result["partner_count"])
        log.info("download      = %s", dl_summary)
        log.info("parse         = %s", parse_summary)
        log.info("errors        = %d", result["error_count"])
        log.info("elapsed       = %.1fs", elapsed)
        return result


# =============================================================================
# 15. Colab asyncio 패치
# =============================================================================

def _patch_asyncio_for_colab() -> None:
    try:
        import nest_asyncio
        nest_asyncio.apply()
        log.debug("nest_asyncio 적용 완료")
    except ImportError:
        pass


# =============================================================================
# 16. 진입점
# =============================================================================

def main(
    site_keys: Optional[List[str]] = None,
    max_pages: int = MAX_PAGES,
    enable_sheets: bool = True,
    enable_sqlite: bool = True,
) -> Dict[str, Any]:
    _patch_asyncio_for_colab()

    execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")
    log.info("InterX Government Intelligence Engine v4.1")
    log.info("execution_id = %s", execution_id)
    log.info("대상 사이트  = %s", site_keys or list(COLLECTOR_REGISTRY.keys()))

    collectors = build_collectors(site_keys=site_keys, max_pages=max_pages)
    if not collectors:
        log.error("사용 가능한 수집기 없음")
        return {}

    sheet_gateway: Optional[GoogleSheetGateway] = None
    if enable_sheets and GSPREAD_AVAILABLE and Path(SERVICE_ACCOUNT_JSON).exists():
        try:
            sheet_gateway = GoogleSheetGateway()
            log.info("Google Sheets 연결 완료")
        except Exception as e:
            log.warning("Google Sheets 연결 실패: %s", e)
    else:
        log.info("Google Sheets 비활성")

    sqlite_gateway: Optional[SQLiteGateway] = None
    if enable_sqlite:
        sqlite_gateway = SQLiteGateway()
        log.info("SQLite 활성: %s", DB_PATH)

    return DailyPipelineOrchestrator(
        collectors=collectors,
        sheet_gateway=sheet_gateway,
        sqlite_gateway=sqlite_gateway,
        attachment_dir=ATTACHMENT_DIR,
    ).run(execution_id)


# =============================================================================
# 직접 실행 진입점
# =============================================================================

if __name__ == "__main__":
    result = main(
        site_keys=["bizinfo"],   # None 이면 전체 12개 사이트
        max_pages=3,
        enable_sheets=True,
        enable_sqlite=True,
    )
    print("=== FINAL RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))



# =========================
# [추가] 공통 유틸 & DB 저장
# =========================
import sqlite3
from datetime import datetime

DB_PATH = "/content/drive/MyDrive/interx_gov_intelligence/data/notices.db"

def save_to_sqlite(notices):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        site TEXT,
        deadline TEXT,
        url TEXT,
        created_at TEXT
    )
    """)

    for n in notices:
        try:
            cur.execute("""
            INSERT INTO notices (title, site, deadline, url, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                n.get("title"),
                n.get("site"),
                n.get("deadline"),
                n.get("url"),
                datetime.now().isoformat()
            ))
        except Exception as e:
            print(f"[DB ERROR] {e}")

    conn.commit()
    conn.close()


# =========================
# [추가] 실행 래퍼
# =========================
def run_pipeline_with_logging():
    print("🚀 파이프라인 실행 시작")

    try:
        # 기존 main 실행 함수 호출 가정
        # run_pipeline() 또는 main() 중 하나일 가능성 있음

        if "run_pipeline" in globals():
            notices = run_pipeline()
        elif "main" in globals():
            notices = main()
        else:
            raise Exception("실행 함수 없음 (run_pipeline or main 필요)")

        print(f"✅ 수집 완료: {len(notices) if notices else 0}건")

        if notices:
            save_to_sqlite(notices)
            print("✅ SQLite 저장 완료")

    except Exception as e:
        print(f"❌ 실행 오류: {e}")

    print("🏁 파이프라인 종료")

# =========================
# [추가] 공통 유틸 & DB 저장
# =========================
import sqlite3
from datetime import datetime
import asyncio
import nest_asyncio

# 코랩 대응
nest_asyncio.apply()

DB_PATH = "/content/drive/MyDrive/interx_gov_intelligence/data/notices.db"

def save_to_sqlite(notices):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        site TEXT,
        deadline TEXT,
        url TEXT,
        created_at TEXT
    )
    """)

    for n in notices:
        try:
            cur.execute("""
            INSERT INTO notices (title, site, deadline, url, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                n.get("title"),
                n.get("site"),
                n.get("deadline"),
                n.get("url"),
                datetime.now().isoformat()
            ))
        except Exception as e:
            print(f"[DB ERROR] {e}")

    conn.commit()
    conn.close()


# =========================
# [추가] 실행 래퍼 (완전 안정 버전)
# =========================
def run_pipeline_with_logging():
    print("🚀 파이프라인 실행 시작")

    try:
        if "run_pipeline" in globals():
            result = run_pipeline()
        elif "main" in globals():
            result = main()
        else:
            raise Exception("실행 함수 없음")

        # =========================
        # async 안전 처리 (코랩 포함)
        # =========================
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_event_loop()
                notices = loop.run_until_complete(result)
            except RuntimeError:
                # loop 이미 실행 중일 때
                notices = asyncio.ensure_future(result)
                loop = asyncio.get_event_loop()
                loop.run_until_complete(notices)
        else:
            notices = result

        # None 방어
        if notices is None:
            notices = []

        print(f"✅ 수집 완료: {len(notices)}건")

        if len(notices) > 0:
            save_to_sqlite(notices)
            print("✅ SQLite 저장 완료")
        else:
            print("⚠️ 저장할 데이터 없음 (필터링 되었을 가능성 높음)")

    except Exception as e:
        print(f"❌ 실행 오류: {e}")

    print("🏁 파이프라인 종료")

# =========================
# [추가] 공통 유틸 & DB 저장
# =========================
import sqlite3
from datetime import datetime
import asyncio
import nest_asyncio

# 코랩 대응
nest_asyncio.apply()

DB_PATH = "/content/drive/MyDrive/interx_gov_intelligence/data/notices.db"

def save_to_sqlite(notices):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        site TEXT,
        deadline TEXT,
        url TEXT,
        created_at TEXT
    )
    """)

    for n in notices:
        try:
            cur.execute("""
            INSERT INTO notices (title, site, deadline, url, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                n.get("title"),
                n.get("site"),
                n.get("deadline"),
                n.get("url"),
                datetime.now().isoformat()
            ))
        except Exception as e:
            print(f"[DB ERROR] {e}")

    conn.commit()
    conn.close()


# =========================
# [추가] 실행 래퍼 (완전 안정 버전)
# =========================
def run_pipeline_with_logging():
    print("🚀 파이프라인 실행 시작")

    try:
        if "run_pipeline" in globals():
            result = run_pipeline()
        elif "main" in globals():
            result = main()
        else:
            raise Exception("실행 함수 없음")

        # =========================
        # async 안전 처리 (코랩 포함)
        # =========================
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_event_loop()
                notices = loop.run_until_complete(result)
            except RuntimeError:
                # loop 이미 실행 중일 때
                notices = asyncio.ensure_future(result)
                loop = asyncio.get_event_loop()
                loop.run_until_complete(notices)
        else:
            notices = result

        # None 방어
        if notices is None:
            notices = []

        print(f"✅ 수집 완료: {len(notices)}건")

        if len(notices) > 0:
            save_to_sqlite(notices)
            print("✅ SQLite 저장 완료")
        else:
            print("⚠️ 저장할 데이터 없음 (필터링 되었을 가능성 높음)")

    except Exception as e:
        print(f"❌ 실행 오류: {e}")

    print("🏁 파이프라인 종료")

# =========================
# [추가] 공통 유틸 & DB 저장
# =========================
import sqlite3
from datetime import datetime
import asyncio
import nest_asyncio

# 코랩 환경 대응
nest_asyncio.apply()

DB_PATH = "/content/drive/MyDrive/interx_gov_intelligence/data/notices.db"

def save_to_sqlite(notices):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        site TEXT,
        deadline TEXT,
        url TEXT,
        created_at TEXT
    )
    """)

    # None 방어
    if notices is None:
        notices = []

    for n in notices:
        try:
            cur.execute("""
            INSERT INTO notices (title, site, deadline, url, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                n.get("title"),
                n.get("site"),
                n.get("deadline"),
                n.get("url"),
                datetime.now().isoformat()
            ))
        except Exception as e:
            print(f"[DB ERROR] {e}")

    conn.commit()
    conn.close()


# =========================
# [추가] 실행 래퍼 (코랩 안정 버전)
# =========================
def run_pipeline_with_logging():
    print("🚀 파이프라인 실행 시작")

    try:
        # 실행 함수 자동 감지
        if "run_pipeline" in globals():
            result = run_pipeline()
        elif "main" in globals():
            result = main()
        else:
            raise Exception("실행 함수 없음")

        # =========================
        # async 안전 처리
        # =========================
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_event_loop()
                notices = loop.run_until_complete(result)
            except RuntimeError:
                # 이미 loop 실행 중일 경우
                notices = asyncio.ensure_future(result)
                loop = asyncio.get_event_loop()
                loop.run_until_complete(notices)
        else:
            notices = result

        # None 방어
        if notices is None:
            notices = []

        print(f"✅ 수집 완료: {len(notices)}건")

        # 🔥 핵심: 무조건 DB 저장 (필터 상관없이)
        save_to_sqlite(notices)
        print("✅ SQLite 저장 완료")

        if len(notices) == 0:
            print("⚠️ 현재 필터 조건 때문에 결과가 없을 가능성 높음")

    except Exception as e:
        print(f"❌ 실행 오류: {e}")

    print("🏁 파이프라인 종료")