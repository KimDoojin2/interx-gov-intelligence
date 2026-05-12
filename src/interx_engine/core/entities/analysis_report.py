from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class MonthlyTrend:
    month: str          # "2026-03"
    count: int
    l3_count: int
    avg_fitness: float
    total_budget_억: float


@dataclass
class MinistryBudget:
    ministry: str
    total_budget_억: float
    notice_count: int
    share_pct: float    # 전체 대비 비중 (%)


@dataclass
class ClusterGroup:
    cluster_id: str
    size: int
    representative_title: str
    avg_fitness: float
    suggested_package: str  # 패키지 제안 (솔루션 조합)


@dataclass
class AnalysisReport:
    execution_id: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_notices: int = 0
    monthly_trends: List[MonthlyTrend] = field(default_factory=list)
    ministry_budgets: List[MinistryBudget] = field(default_factory=list)
    cluster_groups: List[ClusterGroup] = field(default_factory=list)
    top_solutions: List[Dict[str, Any]] = field(default_factory=list)
    insight_summary: str = ""
