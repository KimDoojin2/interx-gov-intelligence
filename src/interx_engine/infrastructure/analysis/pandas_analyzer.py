"""
PandasAnalyzer — AnalysisReport → pandas DataFrame 변환 및 시각화 데이터 생성
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from interx_engine.core.entities.analysis_report import AnalysisReport


def report_to_trend_df(report: "AnalysisReport"):
    """월별 트렌드 → DataFrame"""
    import pandas as pd
    rows = [
        {
            "월": t.month,
            "수집건수": t.count,
            "L3건수": t.l3_count,
            "평균적합도": t.avg_fitness,
            "예산합계(억)": t.total_budget_억,
        }
        for t in report.monthly_trends
    ]
    return pd.DataFrame(rows).sort_values("월") if rows else pd.DataFrame()


def report_to_ministry_df(report: "AnalysisReport"):
    """부처별 예산 → DataFrame"""
    import pandas as pd
    rows = [
        {
            "부처": m.ministry,
            "예산합계(억)": m.total_budget_억,
            "공고수": m.notice_count,
            "비중(%)": m.share_pct,
        }
        for m in report.ministry_budgets
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def report_to_cluster_df(report: "AnalysisReport"):
    """클러스터 → DataFrame"""
    import pandas as pd
    rows = [
        {
            "클러스터ID": g.cluster_id,
            "공고수": g.size,
            "대표공고": g.representative_title,
            "평균적합도": g.avg_fitness,
            "패키지제안": g.suggested_package,
        }
        for g in report.cluster_groups
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def prediction_to_df(predictions: list):
    """WinPredictionReport.predictions → DataFrame"""
    import pandas as pd
    rows = [
        {
            "공고ID": p.notice_id,
            "사이트": p.site,
            "공고명": p.title,
            "수주확률": p.win_probability,
            "등급": p.win_grade,
            "우선순위": p.recommended_priority,
        }
        for p in predictions
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame()
