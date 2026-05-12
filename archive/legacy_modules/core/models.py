import hashlib
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import date

@dataclass
class Notice:
    execution_id: str
    site: str
    notice_id: str
    title: str
    detail_url: str = ""
    posted_date: str = ""
    deadline_date: str = ""
    ministry: str = ""
    agency: str = ""
    business_type: str = ""
    budget: str = ""
    summary: str = ""
    body_text: str = ""
    attachments: List[str] = field(default_factory=list)
    attachment_items: List[Dict[str, str]] = field(default_factory=list)
    structured: Dict[str, str] = field(default_factory=dict)

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
