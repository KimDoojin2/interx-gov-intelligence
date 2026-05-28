"""
KPI / 로그 시트용 row 빌더
22_KPI현황 컬럼: [기준일, 구분, 지표, 값, 실행ID]  (수직 피벗)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


def _urgent_dday() -> int:
    from interx_engine.application.ports.settings_port import urgent_dday
    return urgent_dday()


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _kpi(today: str, execution_id: str, category: str, metric: str, value) -> Dict[str, Any]:
    return {"기준일": today, "구분": category, "지표": metric, "값": str(value), "실행ID": execution_id}


# ─────────────────────────────────────────────────────────────────────────────
# 22_KPI현황  →  [기준일, 구분, 지표, 값, 실행ID]  (수직 피벗)
# ─────────────────────────────────────────────────────────────────────────────
def build_kpi_rows(
    execution_id: str,
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> List[Dict[str, Any]]:
    today = _today()
    sc    = score_cards

    # ── 수집현황 ─────────────────────────────────────────────────────────────
    total       = len(notices)
    l3_cnt      = sum(1 for n in notices if n.l3_strong       == "Y")
    partner_cnt = sum(1 for n in notices if n.partner_candidate == "Y")
    closed_cnt  = sum(1 for n in notices if n.is_closed())
    open_cnt    = total - closed_cnt

    # D-7 긴급마감 수
    urgent_cnt = 0
    from interx_engine.application.mappers.notice_mapper import _calc_dday
    for n in notices:
        try:
            d = _calc_dday(n.deadline_date)
            if d and d != "상시" and 0 <= int(d) <= _urgent_dday():
                urgent_cnt += 1
        except ValueError:
            pass

    # ── 등급현황 ─────────────────────────────────────────────────────────────
    p1 = sum(1 for s in sc if s.priority_grade == "A")
    p2 = sum(1 for s in sc if s.priority_grade == "B")
    p3 = sum(1 for s in sc if s.priority_grade == "C")
    p4 = sum(1 for s in sc if s.priority_grade == "D")

    # ── 솔루션현황 ───────────────────────────────────────────────────────────
    sol_counter: Dict[str, int] = {}
    for n in notices:
        for sol in (n.recommended_solution or "").split("/"):
            s = sol.strip()
            if s:
                sol_counter[s] = sol_counter.get(s, 0) + 1

    # ── 예산현황 ─────────────────────────────────────────────────────────────
    budgets = []
    for n in notices:
        raw = str(n.budget or "").replace(",", "").replace("억", "").strip()
        try:
            budgets.append(float(raw))
        except ValueError:
            pass
    avg_budget = round(sum(budgets) / len(budgets), 1) if budgets else 0
    max_budget = max(budgets) if budgets else 0

    rows: List[Dict[str, Any]] = []

    # 수집현황
    for metric, val in [
        ("전체공고수",    total),
        ("공개중공고수",  open_cnt),
        ("마감공고수",    closed_cnt),
        ("긴급마감수",    urgent_cnt),
        ("L3강공고수",    l3_cnt),
        ("파트너전달수",  partner_cnt),
    ]:
        rows.append(_kpi(today, execution_id, "수집현황", metric, val))

    # 등급현황
    for metric, val in [("A등급수", p1), ("B등급수", p2), ("C등급수", p3), ("D등급수", p4)]:
        rows.append(_kpi(today, execution_id, "등급현황", metric, val))

    # 솔루션현황
    for sol, cnt in sorted(sol_counter.items(), key=lambda x: -x[1]):
        rows.append(_kpi(today, execution_id, "솔루션현황", f"{sol}건수", cnt))

    # 예산현황
    rows.append(_kpi(today, execution_id, "예산현황", "평균예산(억)", avg_budget))
    rows.append(_kpi(today, execution_id, "예산현황", "최대예산(억)", max_budget))

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 94_실행로그  →  [실행ID, 실행시각, 단계, 상태, 소요초, 메시지]
# ─────────────────────────────────────────────────────────────────────────────
def build_exec_log_row(
    execution_id: str,
    step: str,
    status: str,
    elapsed_sec: float = 0.0,
    message: str = "",
) -> Dict[str, Any]:
    return {
        "실행ID":   execution_id,
        "실행시각": _ts(),
        "단계":     step,
        "상태":     status,
        "소요초":   round(elapsed_sec, 1),
        "메시지":   message,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 93_사이트별수집통계  →  사이트 단위 집계 (append)
# ─────────────────────────────────────────────────────────────────────────────
def build_site_stats_rows(
    execution_id: str,
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> List[Dict[str, Any]]:
    """사이트별 수집 건수·마감임박·L3·등급 통계 행 반환."""
    from interx_engine.application.mappers.notice_mapper import _calc_dday

    today = _today()
    score_map = {s.notice_id: s for s in score_cards}

    # 사이트별 버킷
    buckets: Dict[str, Dict[str, int]] = {}
    for n in notices:
        site = n.site or "기타"
        b = buckets.setdefault(site, {"수집건수": 0, "마감임박건수": 0,
                                      "L3건수": 0, "A건수": 0,
                                      "B건수": 0, "C건수": 0})
        b["수집건수"] += 1
        try:
            d = _calc_dday(n.deadline_date)
            if d and d != "상시" and 0 <= int(d) <= _urgent_dday():
                b["마감임박건수"] += 1
        except ValueError:
            pass
        if n.l3_strong == "Y":
            b["L3건수"] += 1
        sc = score_map.get(n.notice_id)
        if sc:
            grade = sc.priority_grade or ""
            if grade == "A":
                b["A건수"] += 1
            elif grade == "B":
                b["B건수"] += 1
            elif grade == "C":
                b["C건수"] += 1

    return [
        {
            "기준일":    today,
            "실행ID":    execution_id,
            "사이트":    site,
            **counts,
        }
        for site, counts in sorted(buckets.items())
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 96_수집에러로그  →  [실행ID, 실행시각, 사이트, 에러유형, 에러메시지]
# ─────────────────────────────────────────────────────────────────────────────
def build_collect_error_rows(
    execution_id: str,
    errors: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """콜렉터 에러 목록 → 96_수집에러로그 행."""
    ts = _ts()
    return [
        {
            "실행ID":    execution_id,
            "실행시각":  ts,
            "사이트":    e.get("site",          ""),
            "에러유형":  e.get("error_type",    ""),
            "에러메시지": e.get("error_message", ""),
        }
        for e in errors
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 95_수집로그 (deprecated — 94_실행로그로 통합)
# [실행ID, 사이트, 공고ID, 공고명, 등록일, 마감일, 첨부수, 수집시각]
# ─────────────────────────────────────────────────────────────────────────────
def build_collect_log_rows(execution_id: str, notices: List[Notice]) -> List[Dict[str, Any]]:
    ts = _ts()
    return [
        {
            "실행ID":   execution_id,
            "사이트":   n.site,
            "공고ID":   n.notice_id,
            "공고명":   n.title,
            "등록일":   n.posted_date,
            "마감일":   n.deadline_date,
            "첨부수":   len(n.attachments),
            "수집시각": ts,
        }
        for n in notices
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 96_에러로그  →  [실행ID, 사이트, 공고ID, 에러유형, 에러메시지, 실행시각]
# ─────────────────────────────────────────────────────────────────────────────
def build_error_log_rows(
    execution_id: str,
    errors: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    ts = _ts()
    return [
        {
            "실행ID":    execution_id,
            "사이트":    e.get("site",          ""),
            "공고ID":    e.get("notice_id",     ""),
            "에러유형":  e.get("error_type",    ""),
            "에러메시지": e.get("error_message", ""),
            "실행시각":  ts,
        }
        for e in errors
    ]
