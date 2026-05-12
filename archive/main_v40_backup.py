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
    import docx as python_docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# =============================================================================
# 0. 설정
# =============================================================================

BASE_DIR = Path("/content/drive/MyDrive/interx_gov_intelligence")

SPREADSHEET_NAME     = os.getenv("INTERX_SHEET_NAME", "InterX_BD_CRM_v10_fresh_template")
SERVICE_ACCOUNT_JSON = os.getenv("INTERX_SA_JSON",    str(BASE_DIR / "service_account.json"))
DB_PATH              = os.getenv("INTERX_DB_PATH",    str(BASE_DIR / "data" / "interx_engine.db"))
ATTACHMENT_DIR       = os.getenv("INTERX_ATT_DIR",    str(BASE_DIR / "data" / "attachments"))
LOG_DIR              = os.getenv("INTERX_LOG_DIR",    str(BASE_DIR / "logs"))
MAX_WORKERS          = int(os.getenv("INTERX_WORKERS",   "4"))
COLLECTOR_TIMEOUT    = int(os.getenv("INTERX_TIMEOUT",   "15"))   # ★ v4.1: 45 → 15
MAX_PAGES            = int(os.getenv("INTERX_MAX_PAGES", "5"))
PLAYWRIGHT_SITES     = set(os.getenv("PLAYWRIGHT_SITES", "iris,dicia").split(","))

HF_API_URL  = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
HF_TOKEN    = os.getenv("HF_TOKEN", "")
LLM_ENABLED = True

L3_STRONG_THRESHOLD    = 70
PARTNER_CAND_THRESHOLD = 50
MIN_FIT_SCORE          = 20

POSITIVE_KEYWORDS: Dict[str, float] = {
    "스마트팩토리": 3, "디지털트윈": 3, "산업AI": 3, "제조AI": 3,
    "예지보전": 3, "머신비전": 3, "자율제조": 3, "스마트공장": 3,
    "AI": 2, "인공지능": 2, "제조": 2, "품질": 2, "검사": 2,
    "공정": 2, "설비": 2, "모니터링": 2, "이상탐지": 2, "수율": 2,
    "불량": 2, "로봇": 2, "센서": 2, "자동화": 2, "안전": 2,
    "중대재해": 2, "생성형AI": 2, "LLM": 2, "RAG": 2,
    "데이터": 1, "MES": 1, "ERP": 1, "OT": 1, "PLC": 1,
    "플랫폼": 1, "시뮬레이션": 1, "API": 1, "실증": 1,
    "상용화": 1, "비전": 1, "GPT": 1, "클라우드": 1,
}

NEGATIVE_KEYWORDS: Dict[str, float] = {
    "게임": 5, "웹툰": 5, "만화": 5, "영화": 5, "애니": 5,
    "캐릭터": 4, "축제": 4, "전시": 3, "음악": 4, "공연": 4,
    "e스포츠": 5, "공모전": 3, "관광": 3, "패션": 4, "뷰티": 4,
    "스포츠": 3, "문화": 2, "예술": 3, "방송": 3, "미디어": 2, "콘텐츠": 2,
}

SOLUTION_MAP: Dict[str, Dict[str, float]] = {
    "ManufacturingDT": {"디지털트윈": 3, "시뮬레이션": 2, "공정": 1, "스마트팩토리": 2, "자율제조": 2},
    "RecipeAI":        {"레시피": 3, "공정레시피": 3, "배합": 2, "조건최적화": 2},
    "QualityAI":       {"품질": 2, "불량": 2, "수율": 2, "이상탐지": 3, "SPC": 2},
    "InspectionAI":    {"비전검사": 3, "외관검사": 3, "머신비전": 3, "비전": 1, "검사": 1},
    "SafetyAI":        {"안전": 2, "중대재해": 3, "위험": 1, "사고": 1, "안전모니터링": 2},
    "GenAI":           {"생성형AI": 3, "LLM": 3, "RAG": 3, "GPT": 2, "AI": 1, "인공지능": 1},
    "InfraDS":         {"데이터": 1, "API": 1, "MES": 2, "ERP": 2, "OT": 2, "PLC": 2, "플랫폼": 1},
}

MASTER_COLUMNS = [
    "실행ID", "사이트", "그룹사이트", "공고ID", "중복그룹", "중복순위", "대표공고여부",
    "공고명", "공고명링크", "상세URL",
    "등록일", "마감일", "D-day", "상태", "마감여부",
    "사업유형", "사업유형근거", "주무부처", "수행기관", "예산", "기간개월",
    "적합도점수", "우선순위점수", "우선순위등급", "공고분류", "액션유형",
    "제안전략", "추천솔루션", "추천액션", "상위솔루션", "사업요약",
    "산업점수", "ManufacturingDT점수", "RecipeAI점수", "QualityAI점수",
    "InspectionAI점수", "SafetyAI점수", "GenAI점수", "InfraDS점수",
    "파트너점수", "기관가점", "감점",
    "산업키워드", "적합키워드", "무관키워드",
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
        name = text if text else "attachment"
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


def extract_dates(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    patterns = {
        "posted_date": [
            r"등록일\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"공고일\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"게시일\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
        ],
        "deadline_date": [
            r"접수\s*마감\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"신청\s*마감\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"마감일\s*[:：]?\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"접수기간.*?~\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"모집\s*기간.*?~\s*(\d{4}[-./]\d{2}[-./]\d{2})",
            r"신청\s*기간.*?~\s*(\d{4}[-./]\d{2}[-./]\d{2})",
        ],
    }
    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text)
            if m:
                result[key] = m.group(1).replace("/", "-").replace(".", "-")
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
        r"(주관|주무|담당)\s*부처\s*[:：]?\s*([^\n,（(]{2,20}(?:부|처|청|원|위원회))",
        text,
    )
    return safe_text(m.group(2)) if m else ""


def calc_dday(deadline_str: str) -> Tuple[str, str]:
    if not deadline_str:
        return "", "NEW"
    try:
        dl    = date.fromisoformat(deadline_str[:10])
        today = date.today()
        diff  = (dl - today).days
        if diff < 0:
            return f"D+{abs(diff)}", "CLOSED"
        if diff <= 7:
            return f"D-{diff}", "DEADLINE_SOON"
        return f"D-{diff}", "NEW"
    except Exception:
        return "", "NEW"


STRUCTURED_SECTIONS = {
    "사업목적":  [r"사업\s*목적", r"추진\s*배경", r"사업\s*개요"],
    "추진방향":  [r"추진\s*방향", r"추진\s*내용", r"세부\s*내용"],
    "지원대상":  [r"지원\s*대상", r"신청\s*자격", r"참여\s*자격"],
    "지원조건":  [r"지원\s*조건", r"선정\s*조건"],
    "예산":      [r"예산", r"지원\s*금액", r"총\s*사업비"],
    "일정":      [r"추진\s*일정", r"사업\s*일정", r"세부\s*일정"],
    "신청방법":  [r"신청\s*방법", r"접수\s*방법", r"신청\s*절차"],
    "제출서류":  [r"제출\s*서류", r"제출\s*자료", r"신청\s*서류"],
    "평가기준":  [r"평가\s*기준", r"선정\s*기준", r"평가\s*지표"],
    "담당자":    [r"담당\s*자", r"문의\s*처", r"문의"],
    "접수기간":  [r"접수\s*기간", r"신청\s*기간"],
}


def extract_structured_sections(text: str) -> Dict[str, str]:
    result:  Dict[str, str] = {}
    anchors: List[Tuple[int, str]] = []
    for section, patterns in STRUCTURED_SECTIONS.items():
        combined = "|".join(f"(?:{p})" for p in patterns)
        for m in re.finditer(combined, text, re.I):
            anchors.append((m.start(), section))
    anchors.sort(key=lambda x: x[0])
    for idx, (start, section) in enumerate(anchors):
        end   = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(text)
        chunk = text[start:end].strip()
        chunk = re.sub(r"^[^\n]{0,30}\n", "", chunk, count=1).strip()
        if chunk and section not in result:
            result[section] = chunk[:500]
    return result


# =============================================================================
# 5. 무료 LLM 요약 (HuggingFace)
# =============================================================================

def llm_summarize(text: str, max_chars: int = 1000) -> str:
    if not LLM_ENABLED or not text.strip():
        return ""
    try:
        payload = {
            "inputs": text[:max_chars],
            "parameters": {"max_length": 130, "min_length": 30, "do_sample": False},
        }
        headers = {"Content-Type": "application/json"}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"
        resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("summary_text", "")
    except Exception as e:
        log.debug("[LLM] 요약 실패(무시): %s", e)
    return ""


# =============================================================================
# 6. 수집기 베이스
# =============================================================================

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
                try:
                    dhtml  = fetch_html_smart(item["detail_url"], self.session,
                                              site_key=self.site_key, timeout=self.timeout)
                    detail = self.parse_detail_page(dhtml, item["detail_url"])
                except Exception as e:
                    log.error("[%s] 상세 실패 %s: %s", self.site_key, item["detail_url"], e)
                    self._errors.append(ErrorRecord(
                        execution_id, self.site_key,
                        self.make_notice_id(item["detail_url"]),
                        "detail_fetch", type(e).__name__, str(e)[:300],
                    ))
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
            "summary":       body_text[:300],
            "attachments":   parse_attachments(soup, detail_url),
        }


class CbtpCollector(BaseCollector):
    """충북테크노파크 https://www.cbtp.or.kr"""
    site_key = "cbtp"
    base_url = "https://www.cbtp.or.kr"

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
            "agency": "부산정보산업진흥원", "business_type": "",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class UipaCollector(BaseCollector):
    """울산정보산업진흥원 https://uipa.or.kr"""
    site_key   = "uipa"
    base_url   = "https://uipa.or.kr"
    ssl_verify = False   # ★ v4.1: SSL 오류 우회

    def get_list_url(self, page: int) -> str:
        # ★ v4.1: 실제 게시판 URL + 페이지 파라미터 정리
        if page == 1:
            return f"{self.base_url}/board/business"
        return f"{self.base_url}/board/business?page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()

        # ★ v4.1: 다중 셀렉터 fallback
        SELECTORS = [
            "table tbody tr td a",
            ".bbs-list td.title a",
            ".board-list td.title a",
            ".list_wrap a",
            ".board_list a",
            "ul.list li a",
            ".notice-list a",
            "td.subject a",
            "a[href*='business']",
        ]

        base_stripped = self.base_url.rstrip("/")

        for sel in SELECTORS:
            for a in soup.select(sel):
                href  = urljoin(self.base_url, (a.get("href") or "").strip())
                title = safe_text(a.get_text())
                if href.rstrip("/") == f"{base_stripped}/board/business":
                    continue
                if href not in seen and len(title) > 3:
                    seen.add(href)
                    items.append({"title": title, "detail_url": href})
            if items:
                log.debug("[uipa] 셀렉터 '%s' 로 %d개 발견", sel, len(items))
                break

        if not items:
            log.warning("[uipa] 파싱 결과 0개. HTML 앞 500자: %s", html[:500])

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
            "agency":        "울산정보산업진흥원",
            "business_type": "",
            "summary":       body_text[:300],
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
            if href not in seen and len(title) > 3:
                seen.add(href)
                items.append({"title": title, "detail_url": href})
        for node in soup.select("[onclick]"):
            oc    = node.get("onclick", "") or ""
            title = safe_text(node.get_text())
            for m in re.finditer(r"['\"]([^'\"]*BsnsAncm[^'\"]*)['\"]", oc):
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
            "agency": "IRIS", "business_type": "R&D",
            "summary": body_text[:300], "attachments": parse_attachments(soup, detail_url),
        }


class KiatCollector(BaseCollector):
    """한국산업기술진흥원 https://www.kiat.or.kr"""
    site_key = "kiat"
    base_url = "https://www.kiat.or.kr"

    def get_list_url(self, page: int) -> str:
        return (f"{self.base_url}/site/main/board/boardList.do"
                f"?pageIndex={page}&boardManagementNo=9")

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup  = BeautifulSoup(html, "lxml")
        items: List[Dict[str, str]] = []
        seen:  set = set()
        for a in soup.select("td.subject a, td.title a, .bbs-list td a"):
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
    "kiat":      KiatCollector,
    "smba":      SmbaCollector,
    "innopolis": InnopolisCollector,
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
        self.sol_map = {
            sol: {k.lower(): v for k, v in kws.items()}
            for sol, kws in SOLUTION_MAP.items()
        }

    def _full_text(self, n: Notice) -> str:
        parts = [n.title, n.summary, n.business_type, n.agency, n.ministry]
        parts += list(n.structured.values())
        for att in n.attachment_items or []:
            txt = att.get("text", "")
            if txt:
                parts.append(txt[:500])
        return " ".join(parts).lower()

    def score_one(self, notice: Notice) -> ScoreCard:
        text = self._full_text(notice)

        pos_hits:  List[str] = []
        pos_score: float = 0.0
        for kw, w in self.pos_kw.items():
            if kw in text:
                pos_hits.append(kw)
                pos_score += w

        neg_hits:  List[str] = []
        neg_score: float = 0.0
        for kw, w in self.neg_kw.items():
            if kw in text:
                neg_hits.append(kw)
                neg_score += w

        struct_bonus = (3.0 if notice.structured.get("지원대상") else 0.0) + \
                       (2.0 if notice.structured.get("평가기준") else 0.0)
        budget_bonus = 3.0 if notice.budget else 0.0

        raw_fit = (pos_score * 5.0) - (neg_score * 6.0) + struct_bonus + budget_bonus
        fitness = max(0.0, min(100.0, raw_fit))

        sol_scores: Dict[str, float] = {}
        for sol, kws in self.sol_map.items():
            s = sum(w for kw, w in kws.items() if kw in text)
            sol_scores[sol] = round(min(100.0, s * 15.0), 1)

        industry_score = round(sum(sol_scores.values()) / max(len(sol_scores), 1), 1)
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
                 timeout: int = 30, max_workers: int = MAX_WORKERS):
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
            if e == "hwp":              return "skipped", "hwp_not_supported", ""
            return "skipped", f"unsupported:{e}", ""
        except Exception as ex:
            return "failed", f"{type(ex).__name__}:{str(ex)[:200]}", ""

    def _pdf(self, p: Path) -> Tuple[str, str, str]:
        if not PYPDF_AVAILABLE:
            return "skipped", "pypdf_not_installed", ""
        reader = PdfReader(str(p))
        texts  = []
        for pg in reader.pages[: self.MAX_PAGES]:
            try:
                t = pg.extract_text() or ""
                if t.strip():
                    texts.append(t)
            except Exception:
                pass
        full = "\n".join(texts).strip()[: self.MAX_CHARS]
        return ("parsed" if full else "skipped"), "", full

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
        full = "\n".join(texts).strip()[: self.MAX_CHARS]
        return ("parsed" if full else "skipped"), "", full

    def _docx(self, p: Path) -> Tuple[str, str, str]:
        if not DOCX_AVAILABLE:
            return "skipped", "python_docx_not_installed", ""
        doc   = python_docx.Document(str(p))
        lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        full  = "\n".join(lines)[: self.MAX_CHARS]
        return ("parsed" if full else "skipped"), "", full


def parse_attachments_in_notices(notices: List[Notice]) -> Dict[str, int]:
    parser = DocumentParser()
    parsed = failed = skipped = 0
    for n in notices:
        for att in n.attachment_items or []:
            if att.get("download_status") != "downloaded":
                continue
            local = att.get("local_path", "")
            ext   = att.get("ext", "")
            if not local:
                continue
            status, err, text = parser.parse(local, ext)
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
        creds  = Credentials.from_service_account_file(service_account_json, scopes=self.SCOPES)
        client = gspread.authorize(creds)
        self._ss       = client.open(spreadsheet_name)
        self._ws_cache: Dict[str, Any] = {}

    def _ws(self, sheet_name: str):
        if sheet_name not in self._ws_cache:
            self._ws_cache[sheet_name] = self._ss.worksheet(sheet_name)
        return self._ws_cache[sheet_name]

    def append_rows_batch(self, sheet_key: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        sheet_name = SHEET_MAP.get(sheet_key, sheet_key)
        columns    = SHEET_COLUMNS.get(sheet_key, [])
        ws         = self._ws(sheet_name)
        values     = [[r.get(c, "") for c in columns] for r in rows]
        for i in range(0, len(values), self.BATCH_SIZE):
            batch = values[i: i + self.BATCH_SIZE]
            ws.append_rows(batch, value_input_option="USER_ENTERED")
            log.info("[Sheets] %s: %d행 append", sheet_name, len(batch))
            time.sleep(0.5)


# =============================================================================
# 13. Row 매퍼
# =============================================================================

def notice_to_master_row(notice: Notice,
                          score: Optional[ScoreCard] = None) -> Dict[str, Any]:
    dday, _ = calc_dday(notice.deadline_date)
    closed  = "Y" if notice.status == "CLOSED" else "N"
    sol     = score.solution_scores if score else {}

    if notice.detail_url:
        safe_title   = notice.title.replace('"', '""')
        link_formula = f'=HYPERLINK("{notice.detail_url}","{safe_title}")'
    else:
        link_formula = notice.title

    return {
        "실행ID": notice.execution_id, "사이트": notice.site, "그룹사이트": notice.site,
        "공고ID": notice.notice_id, "중복그룹": "", "중복순위": "", "대표공고여부": "Y",
        "공고명": notice.title,
        "공고명링크": link_formula,
        "상세URL": notice.detail_url,
        "등록일": notice.posted_date, "마감일": notice.deadline_date,
        "D-day": dday, "상태": notice.status, "마감여부": closed,
        "사업유형": notice.business_type, "사업유형근거": "",
        "주무부처": notice.ministry, "수행기관": notice.agency,
        "예산": notice.budget, "기간개월": notice.duration_months,
        "적합도점수":   score.fitness_score   if score else "",
        "우선순위점수": score.priority_score  if score else "",
        "우선순위등급": score.priority_grade  if score else "",
        "공고분류": "", "액션유형": "",
        "제안전략": notice.proposal_strategy,
        "추천솔루션": notice.recommended_solution,
        "추천액션": notice.recommended_action,
        "상위솔루션": notice.recommended_solution,
        "사업요약": notice.llm_summary or notice.summary[:200],
        "산업점수": score.industry_score if score else "",
        "ManufacturingDT점수": sol.get("ManufacturingDT", ""),
        "RecipeAI점수":    sol.get("RecipeAI", ""),
        "QualityAI점수":   sol.get("QualityAI", ""),
        "InspectionAI점수": sol.get("InspectionAI", ""),
        "SafetyAI점수":    sol.get("SafetyAI", ""),
        "GenAI점수":       sol.get("GenAI", ""),
        "InfraDS점수":     sol.get("InfraDS", ""),
        "파트너점수": "", "기관가점": "", "감점": "",
        "산업키워드": " | ".join(score.positive_keywords) if score else "",
        "적합키워드": " | ".join(score.positive_keywords) if score else "",
        "무관키워드": " | ".join(score.negative_keywords) if score else "",
        "첨부수": len(notice.attachments),
        "첨부명": " | ".join(notice.attachments[:5]),
        "첨부URL": " | ".join(a.get("url","") for a in (notice.attachment_items or [])[:5]),
        "담당자": notice.manager, "검토상태": "", "다음액션": "", "메모": "",
        "L3강공고": notice.l3_strong, "파트너후보": notice.partner_candidate,
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

        for n in notices:
            try:
                src = n.structured.get("사업목적", "") or n.body_text[:800]
                n.llm_summary = llm_summarize(src)
            except Exception:
                pass

        notices, score_cards = self.scorer.score_all(notices)
        score_map = {s.notice_id: s for s in score_cards}

        before  = len(notices)
        notices = [n for n in notices
                   if score_map.get(n.notice_id) and
                   score_map[n.notice_id].fitness_score >= MIN_FIT_SCORE]
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
    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
