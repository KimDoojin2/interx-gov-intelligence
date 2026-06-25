from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


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
    recommended_solution: str = ""
    recommended_action: str = ""
    l3_strong: str = "N"
    partner_candidate: str = "N"
    attachments: List[str] = field(default_factory=list)
    attachment_items: List[Dict[str, str]] = field(default_factory=list)
    # 상세 파싱 필드 (BizinfoCollector 등에서 채움)
    structured: Dict[str, str] = field(default_factory=dict)
    body_text: str = ""
    category: str = ""                      # R&D / 실증(PoC) / 바우처 / 인력양성 / 기타
    cluster_id: str = ""                    # 클러스터 ID
    partner_candidates: List[Dict[str, Any]] = field(default_factory=list)
    manager: str = ""                       # 담당자
    status: str = ""                        # 검토상태
    open_ended: bool = False                # 상시모집/예산소진시 등 비정형 마감
    duplicate_flag: str = "N"             # TF-IDF 중복 감지 플래그
    is_new: bool = False                  # 신규 공고 (이전 실행 대비)
    is_changed: bool = False              # 변경 감지 (마감일·예산 등)
    memo: str = ""                        # 자동 메모 (중복의심·변경감지·경쟁사)
    bd_milestone: str = ""               # BD 마일스톤 코드 (M01~M18 / P01~P10)
    recurring_flag: str = "N"           # 정기공고 여부 (Y/N)
    recurring_group: str = ""           # 정기공고 그룹명 (e.g. 스마트공장구축, AI바우처)
    apply_status: str = ""             # 접수상태 (접수중/접수예정/마감)

    @property
    def notice_key(self) -> str:
        return hashlib.md5(f"{self.site}:{self.notice_id}".encode()).hexdigest()

    def is_closed(self) -> bool:
        if self.open_ended:
            return False   # 상시모집은 항상 공개
        if not self.deadline_date:
            return False
        try:
            return date.fromisoformat(self.deadline_date[:10]) < date.today()
        except Exception:
            return False
