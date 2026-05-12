from __future__ import annotations

import datetime
import random
import re
import time
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
ALLOWED_EXT = {"pdf", "hwp", "hwpx", "zip", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}

def safe_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())

def to_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    text = safe_text(value)
    for pat in [r"(\d{4})[년\-/](\d{1,2})[월\-/](\d{1,2})", r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})"]:
        m = re.search(pat, text)
        if m:
            try:
                return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                pass
    try:
        return dtparser.parse(text, fuzzy=True).date()
    except Exception:
        return None

def fetch_html(url: str, session: requests.Session, timeout: int = 45, max_retries: int = 5, backoff_base: float = 1.2) -> str:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, headers=DEFAULT_HEADERS, timeout=(10, timeout))
            r.raise_for_status()
            return r.text
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep((backoff_base ** attempt) + random.uniform(0.1, 0.6))
    raise last_exc

def parse_title(soup: BeautifulSoup) -> Optional[str]:
    for selector in ["h3", "h4", ".tit", ".title", "strong", "title"]:
        el = soup.select_one(selector)
        if el:
            t = safe_text(el.get_text())
            if t and len(t) >= 4:
                return t
    return None

def _find_ext(text: str) -> str:
    m = re.search(r"(pdf|hwp|hwpx|zip|doc|docx|xls|xlsx|ppt|pptx)", text or "", re.I)
    return m.group(1).lower() if m else ""

def _extract_js_file_call(onclick: str, base_url: str) -> tuple[str, str]:
    m = re.search(r"(fileLoad|fileBlank)\((.*)\)\s*;?$", onclick or "", re.I)
    if not m:
        return "", ""
    body = m.group(2)
    args = re.split(r",(?![^()]*\))", body, maxsplit=1)
    path_expr = args[0] if args else ""
    parts = re.findall(r"'([^']*)'|\"([^\"]*)\"", path_expr)
    path = "".join([a or b for a, b in parts]).replace(" ", "")
    url = urljoin(base_url, path) if path else ""
    name = ""
    if len(args) > 1:
        q = re.findall(r"'([^']*)'|\"([^\"]*)\"", args[1])
        if q:
            name = (q[0][0] or q[0][1]).strip()
    return url, name

def parse_attachments(soup: BeautifulSoup, base_url: str) -> list[dict]:
    attachments = []
    seen = set()

    for node in soup.select("a[href], a[onclick], button[onclick], [onclick], [data-atch-file-id], [data-file-sn]"):
        text = safe_text(node.get_text(" "))
        href = (node.get("href") or "").strip()
        onclick = (node.get("onclick") or "").strip()
        data_atch = (node.get("data-atch-file-id") or "").strip()
        data_sn = (node.get("data-file-sn") or "").strip()

        parent = node.find_parent(["li", "tr", "td", "div"])
        ptxt = safe_text(parent.get_text(" ")) if parent else ""

        url, js_name = _extract_js_file_call(onclick, base_url)
        if not url and href and not href.lower().startswith("javascript:"):
            url = urljoin(base_url, href)
        if not url and data_atch and data_sn:
            url = f"{base_url.rstrip('/')}/cmm/fms/FileDown.do?atchFileId={data_atch}&fileSn={data_sn}"

        raw = f"{text} {href} {onclick} {ptxt} {url}"
        ext = _find_ext(raw)
        if not ext or ext not in ALLOWED_EXT:
            continue

        name = text or js_name or "attachment"
        if not re.search(r"\.(pdf|hwp|hwpx|zip|doc|docx|xls|xlsx|ppt|pptx)$", name, re.I):
            mname = re.search(r"([A-Za-z0-9_\-\(\)\[\]\s가-힣]+\.(?:pdf|hwp|hwpx|zip|doc|docx|xls|xlsx|ppt|pptx))", ptxt, re.I)
            if mname:
                name = mname.group(1).strip()
            else:
                name = f"{name}.{ext}" if "attachment" not in name else f"attachment_{len(attachments)+1}.{ext}"

        key = (name, url)
        if not url or key in seen:
            continue
        seen.add(key)
        attachments.append({"name": name, "url": url, "ext": ext})

    return attachments
