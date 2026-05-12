"""
담당자 자동 배정 — configs/manager_rules.yaml 규칙 기반
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import yaml

from interx_engine.core.entities.notice import Notice

log = logging.getLogger("interx.assign")


def _load_rules() -> list:
    for p in [
        Path(__file__).resolve().parents[5] / "configs/manager_rules.yaml",
        Path("/content/drive/MyDrive/interx_gov_intelligence/configs/manager_rules.yaml"),
    ]:
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")).get("rules", [])
    return []


def assign_managers(notices: List[Notice]) -> List[Notice]:
    """
    규칙 기반 담당자 자동 배정.
    이미 담당자가 있는 공고는 유지 (수동 배정 우선).
    """
    rules = _load_rules()
    if not rules:
        log.warning("[Assign] manager_rules.yaml 없음 — 배정 스킵")
        return notices

    assigned = 0
    for notice in notices:
        if notice.manager:          # 이미 배정된 경우 유지
            continue
        text = f"{notice.title} {notice.ministry} {notice.agency}".lower()

        for rule in rules:
            cond      = rule.get("conditions", {})
            kws       = [k.lower() for k in cond.get("keywords", [])]
            mins      = [m.lower() for m in cond.get("ministry", [])]
            kw_match  = any(k in text for k in kws) if kws else True
            min_match = any(m in text for m in mins) if mins else True

            if kw_match and min_match:
                notice.manager = rule.get("manager", "미배정")
                assigned += 1
                break

    log.info("[Assign] 담당자 배정: %d건", assigned)
    return notices
