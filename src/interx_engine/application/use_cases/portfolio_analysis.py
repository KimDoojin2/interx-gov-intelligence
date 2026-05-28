"""
PortfolioAnalysisUseCase — pandas 기반 포트폴리오 분석
  - 월별 수집 트렌드
  - 부처별 예산 비중 시계열
  - 유사 공고 클러스터링 → 패키지 제안
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Optional

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.core.entities.analysis_report import (
    AnalysisReport, ClusterGroup, MinistryBudget, MonthlyTrend,
)
from interx_engine.application.ports.budget_utils_port import normalize_budget

log = logging.getLogger("interx.portfolio")

# 솔루션별 패키지 제안 매핑
_PACKAGE_MAP = {
    frozenset(["ManufacturingDT", "PdM"]):    "스마트팩토리 풀패키지",
    frozenset(["QualityAI", "InspectionAI"]): "품질·검사 번들",
    frozenset(["GenAI", "InfraDS"]):           "데이터·AI 플랫폼",
    frozenset(["SafetyAI", "PdM"]):            "안전·예지보전 패키지",
}


def _budget_억(raw: str) -> float:
    try:
        norm = normalize_budget(raw)
        if not norm:
            return 0.0
        digits = "".join(c for c in norm if c.isdigit() or c == ".")
        return float(digits) if digits else 0.0
    except Exception:
        return 0.0


def _ym(date_str: str) -> str:
    if date_str and len(date_str) >= 7:
        return date_str[:7]
    return "unknown"


class PortfolioAnalysisUseCase:
    """notices + score_cards → AnalysisReport"""

    def execute(
        self,
        execution_id: str,
        notices: List[Notice],
        score_cards: List[ScoreCard],
    ) -> AnalysisReport:
        sc_map = {s.notice_id: s for s in score_cards}
        report = AnalysisReport(execution_id=execution_id, total_notices=len(notices))

        # ── 월별 트렌드 ──────────────────────────────────────────────────────
        monthly: dict = defaultdict(lambda: {"count": 0, "l3": 0, "fitness": [], "budget": 0.0})
        for n in notices:
            ym = _ym(n.posted_date or n.deadline_date)
            monthly[ym]["count"] += 1
            if n.l3_strong == "Y":
                monthly[ym]["l3"] += 1
            sc = sc_map.get(n.notice_id)
            if sc:
                monthly[ym]["fitness"].append(sc.fitness_score)
            monthly[ym]["budget"] += _budget_억(n.budget)

        for ym, v in sorted(monthly.items()):
            report.monthly_trends.append(MonthlyTrend(
                month=ym,
                count=v["count"],
                l3_count=v["l3"],
                avg_fitness=round(sum(v["fitness"]) / len(v["fitness"]), 1) if v["fitness"] else 0.0,
                total_budget_억=round(v["budget"], 1),
            ))

        # ── 부처별 예산 비중 ─────────────────────────────────────────────────
        ministry_budget: dict = defaultdict(float)
        ministry_count:  dict = defaultdict(int)
        for n in notices:
            mn = n.ministry or "미분류"
            ministry_budget[mn] += _budget_억(n.budget)
            ministry_count[mn]  += 1

        total_budget = sum(ministry_budget.values()) or 1.0
        for mn, bgt in sorted(ministry_budget.items(), key=lambda x: -x[1])[:10]:
            report.ministry_budgets.append(MinistryBudget(
                ministry=mn,
                total_budget_억=round(bgt, 1),
                notice_count=ministry_count[mn],
                share_pct=round(bgt / total_budget * 100, 1),
            ))

        # ── 클러스터 → 패키지 제안 ───────────────────────────────────────────
        report.cluster_groups = self._cluster_and_suggest(notices, sc_map)

        # ── 솔루션 현황 ──────────────────────────────────────────────────────
        sol_counter: dict = defaultdict(int)
        for sc in score_cards:
            for sol, score in sc.solution_scores.items():
                if score >= 30:
                    sol_counter[sol] += 1
        report.top_solutions = [
            {"solution": sol, "count": cnt}
            for sol, cnt in sorted(sol_counter.items(), key=lambda x: -x[1])
        ]

        # ── 인사이트 요약 ────────────────────────────────────────────────────
        l3_cnt = sum(1 for n in notices if n.l3_strong == "Y")
        a_cnt = sum(1 for sc in score_cards if sc.priority_grade == "A")
        report.insight_summary = (
            f"총 {len(notices)}건 수집 | L3강공고 {l3_cnt}건 | A등급 {a_cnt}건 | "
            f"클러스터 {len(report.cluster_groups)}그룹 | "
            f"부처별 예산 1위: {report.ministry_budgets[0].ministry if report.ministry_budgets else '-'}"
        )
        log.info("[Portfolio] %s", report.insight_summary)
        return report

    def _cluster_and_suggest(self, notices, sc_map) -> List[ClusterGroup]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
            from sklearn.cluster import KMeans  # type: ignore
        except ImportError:
            log.warning("[Portfolio] scikit-learn 없음 — 클러스터링 스킵")
            return []

        if len(notices) < 3:
            return []

        titles = [n.title for n in notices]
        k = min(max(2, len(notices) // 8), 10)

        try:
            vec    = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
            tfidf  = vec.fit_transform(titles)
            labels = KMeans(n_clusters=k, random_state=42, n_init=5).fit_predict(tfidf)
        except Exception as e:
            log.warning("[Portfolio] 클러스터링 실패: %s", e)
            return []

        groups: dict = defaultdict(list)
        for notice, label in zip(notices, labels):
            groups[int(label)].append(notice)

        result = []
        for cid, members in sorted(groups.items()):
            fitnesses = [
                sc_map[n.notice_id].fitness_score
                for n in members if n.notice_id in sc_map
            ]
            avg_fit = round(sum(fitnesses) / len(fitnesses), 1) if fitnesses else 0.0

            # 그룹 내 추천솔루션 조합으로 패키지 제안
            sols = frozenset(
                n.recommended_solution for n in members if n.recommended_solution
            )
            package = next(
                (v for k, v in _PACKAGE_MAP.items() if k & sols), "맞춤 솔루션 제안"
            )
            rep = max(members, key=lambda n: sc_map.get(n.notice_id, type("", (), {"fitness_score": 0})()).fitness_score if n.notice_id in sc_map else 0)

            result.append(ClusterGroup(
                cluster_id=str(cid),
                size=len(members),
                representative_title=rep.title[:60],
                avg_fitness=avg_fit,
                suggested_package=package,
            ))

        return result
