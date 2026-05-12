"""
경쟁사 트래킹 — 공고 수행기관/주관기관/제목에서 경쟁사 자동 감지
configs/competitors.yaml 기반
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.competitor")


def _load_competitors() -> dict:
    for p in [
        Path(__file__).resolve().parents[5] / "configs/competitors.yaml",
        Path("/content/drive/MyDrive/interx_gov_intelligence/configs/competitors.yaml"),
    ]:
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")).get("competitors", {})
    return {}


def track_competitors(notices: List[Notice]) -> List[Notice]:
    """
    경쟁사 감지 → notice.competitor_flag 설정, 메모에 경고 추가.
    tier1(직접 경쟁) / tier2(간접 경쟁) 구분.
    """
    comp  = _load_competitors()
    tier1 = [c.lower() for c in comp.get("tier1", [])]
    tier2 = [c.lower() for c in comp.get("tier2", [])]

    flagged = 0
    for notice in notices:
        text = f"{notice.agency} {notice.ministry} {notice.title}".lower()

        t1_matched = [c for c in tier1 if c in text]
        t2_matched = [c for c in tier2 if c in text]
        all_matched = t1_matched + t2_matched

        if all_matched:
            tier_label = "직접경쟁" if t1_matched else "간접경쟁"
            notice.competitor_flag = f"{tier_label}: {', '.join(all_matched)}"
            memo = getattr(notice, "memo", "") or ""
            notice.memo = (memo + f" ⚔️{tier_label}({','.join(all_matched)})").strip()
            flagged += 1

    if flagged:
        log.info("[Competitor] 경쟁사 감지: %d건", flagged)
    return notices
