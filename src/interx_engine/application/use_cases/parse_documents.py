from __future__ import annotations
from pathlib import Path
from collections import Counter
import re

_STOP = {"그리고","또한","대한","관련","위한","통해","사업","지원","공고","신청","접수","기간","중소기업","기업"}

def _kw(text: str, n: int = 8) -> list[str]:
    toks = re.findall(r"[A-Za-z가-힣]{2,}", text or "")
    toks = [t.lower() for t in toks if t.lower() not in _STOP]
    return [w for w, _ in Counter(toks).most_common(n)]

class ParseDocumentsUseCase:
    def __init__(self, max_chars: int = 3000):
        self.max_chars = max_chars

    def execute(self, notices) -> dict:
        parsed = skipped = failed = 0
        try:
            from pypdf import PdfReader
        except Exception:
            PdfReader = None

        for notice in notices:
            best_text = ""
            for att in getattr(notice, "attachment_items", []) or []:
                lp = (att.get("local_path") or "").strip()
                if not lp:
                    att["parsing_status"] = "skipped_no_file"; att["parsing_error"] = ""; skipped += 1; continue
                ext = Path(lp).suffix.lower().replace(".", "")
                if ext != "pdf":
                    att["parsing_status"] = "skipped_unsupported"; att["parsing_error"] = ""; skipped += 1; continue
                if PdfReader is None:
                    att["parsing_status"] = "failed"; att["parsing_error"] = "pypdf_not_installed"; failed += 1; continue
                try:
                    r = PdfReader(lp)
                    text = "\n".join([(p.extract_text() or "") for p in r.pages[:20]]).strip()
                    att["parsed_text"] = text[:self.max_chars]
                    att["parsing_status"] = "parsed"; att["parsing_error"] = ""; parsed += 1
                    if len(text) > len(best_text): best_text = text
                except Exception as e:
                    att["parsing_status"] = "failed"; att["parsing_error"] = str(e)[:200]; failed += 1

            if best_text:
                notice.summary = best_text[:500]
                notice.recommended_solution = ", ".join(_kw(best_text, 8))
            else:
                base = f"{notice.title} {notice.business_type} {notice.agency}".strip()
                notice.summary = base[:500] if base else notice.summary
                if not notice.recommended_solution:
                    notice.recommended_solution = ", ".join(_kw(base, 5))
        return {"parsed": parsed, "skipped": skipped, "failed": failed}
