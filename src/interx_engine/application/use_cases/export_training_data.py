"""
C/D 등급 공고 학습데이터 Export
파이프라인 실행마다 자동으로 data/exports/training/ 에 JSONL 저장.
포맷: 공고 1건 = 1줄 JSON (fine-tuning / 분류 학습용)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.export")

_TRAINING_GRADES = {"A", "B", "C", "D"}  # 전 등급 저장 (A/B=win=1, C/D=win=0)


def export_training_data(
    notices: List[Notice],
    score_cards: List[ScoreCard],
    execution_id: str,
    output_dir: str = "",
) -> str:
    """
    C/D 등급 공고를 JSONL 파일로 저장.
    Returns: 저장된 파일 경로 (없으면 빈 문자열)
    """
    if not output_dir:
        try:
            from interx_engine.application.ports.settings_port import project_root
            output_dir = str(Path(project_root()) / "data" / "exports" / "training")
        except Exception:
            output_dir = str(Path.cwd() / "data" / "exports" / "training")

    score_map = {s.notice_id: s for s in score_cards}
    records = []

    for notice in notices:
        sc = score_map.get(notice.notice_id)
        if sc is None or sc.priority_grade not in _TRAINING_GRADES:
            continue

        records.append({
            "notice_id":           notice.notice_id,
            "site":                notice.site,
            "title":               notice.title,
            "summary":             notice.summary or "",
            "ministry":            notice.ministry or "",
            "agency":              notice.agency or "",
            "business_type":       notice.business_type or "",
            "budget":              notice.budget or "",
            "posted_date":         notice.posted_date or "",
            "deadline_date":       notice.deadline_date or "",
            "detail_url":          notice.detail_url or "",
            "grade":               sc.priority_grade,
            "fitness_score":       sc.fitness_score,
            "priority_score":      sc.priority_score,
            "industry_score":      getattr(sc, "industry_score", 0.0),
            "positive_keywords":   sc.positive_keywords,
            "negative_keywords":   sc.negative_keywords,
            "solution_scores":     sc.solution_scores,
            "l3_strong":           notice.l3_strong,
            "label":               "win" if sc.priority_grade in ("A", "B") else "low_relevance",
            "win_label":           1 if sc.priority_grade in ("A", "B") else 0,
            "execution_id":        execution_id,
            "exported_at":         datetime.now().isoformat(),
        })

    if not records:
        log.info("[Export] C/D 등급 공고 없음 — 학습데이터 저장 건너뜀")
        return ""

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_dir) / f"training_cd_{date_str}.jsonl"

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log.info("[Export] C/D 학습데이터 %d건 저장: %s", len(records), out_path)
    return str(out_path)
