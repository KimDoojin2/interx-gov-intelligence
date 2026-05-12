from __future__ import annotations
from pathlib import Path
import re
from urllib.parse import urlparse, parse_qs

def _safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    return name[:180] if name else "attachment.bin"

def _fallback_urls(url: str) -> list[str]:
    cands = [url]
    if "getImageFile.do" in url:
        q = parse_qs(urlparse(url).query)
        atch = (q.get("atchFileId") or [""])[0]
        sn = (q.get("fileSn") or ["0"])[0]
        if atch:
            cands.append(f"https://www.bizinfo.go.kr/cmm/fms/FileDown.do?atchFileId={atch}&fileSn={sn}")
    return list(dict.fromkeys(cands))

class DownloadAttachmentsUseCase:
    def __init__(self, downloader, base_dir: str):
        self.downloader = downloader
        self.base_dir = Path(base_dir)

    def execute(self, notices, execution_id: str) -> dict:
        downloaded = failed = skipped = 0
        for notice in notices:
            notice_dir = self.base_dir / execution_id / notice.notice_id
            for att in getattr(notice, "attachment_items", []) or []:
                raw_url = (att.get("url") or "").strip()
                if not raw_url.startswith("http"):
                    att["download_status"] = "skipped_non_http"
                    att["download_error"] = "non_http_url"
                    att["local_path"] = ""
                    skipped += 1
                    continue

                filename = _safe_filename(att.get("name", "attachment.bin"))
                dest = notice_dir / filename

                ok = False
                last_err = "unknown"
                resolved = raw_url
                for u in _fallback_urls(raw_url):
                    ok, err = self.downloader.download(u, dest, referer=getattr(notice, "detail_url", ""))
                    if ok:
                        resolved = u
                        break
                    last_err = err

                if ok:
                    downloaded += 1
                    att["local_path"] = str(dest)
                    att["download_status"] = "downloaded"
                    att["download_error"] = ""
                    att["source_url_resolved"] = resolved
                else:
                    failed += 1
                    att["local_path"] = ""
                    att["download_status"] = "failed"
                    att["download_error"] = last_err
                    att["source_url_resolved"] = resolved
        return {"downloaded": downloaded, "failed": failed, "skipped": skipped}
