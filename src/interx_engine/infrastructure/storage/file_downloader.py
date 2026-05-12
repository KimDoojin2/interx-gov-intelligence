from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

class FileDownloader:
    def __init__(self, timeout: int = 60, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        retry = Retry(total=6, connect=6, read=6, backoff_factor=1.0,
                      status_forcelist=[429,500,502,503,504], allowed_methods=["GET"], raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry, pool_connections=30, pool_maxsize=30)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def download(self, url: str, dest_path: Path, referer: str = "") -> Tuple[bool, str]:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = referer or "https://www.bizinfo.go.kr/"
        last_error = "unknown"
        for _ in range(5):
            try:
                with self.session.get(url, timeout=(10, self.timeout), stream=True, headers=headers) as r:
                    if r.status_code >= 400:
                        last_error = f"http_{r.status_code}"
                        time.sleep(1.0)
                        continue
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return True, ""
            except Exception as e:
                last_error = str(e)[:240]
                time.sleep(1.0)
        return False, last_error
