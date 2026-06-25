"""파싱 검증 — 수집 품질을 사이트·필드별로 진단한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


REQUIRED_FIELDS = ["title", "detail_url", "deadline_date", "agency", "body_text"]
DESIRED_FIELDS = ["budget", "ministry", "summary", "structured"]

GRADE_WEIGHT = {"A": 4, "B": 3, "C": 2, "D": 1}


@dataclass
class FieldStat:
    total: int = 0
    filled: int = 0

    @property
    def ratio(self) -> float:
        return self.filled / self.total if self.total else 0.0

    @property
    def pct(self) -> int:
        return round(self.ratio * 100)


@dataclass
class NoticeIssue:
    notice_id: str
    title: str
    site: str
    grade: str
    issues: List[str] = field(default_factory=list)
    severity: str = "warning"


@dataclass
class SiteReport:
    site: str
    total: int = 0
    field_stats: Dict[str, FieldStat] = field(default_factory=dict)
    completeness_pct: int = 0
    grade_dist: Dict[str, int] = field(default_factory=dict)


@dataclass
class ValidationResult:
    total_notices: int = 0
    total_issues: int = 0
    overall_completeness: int = 0
    site_reports: List[SiteReport] = field(default_factory=list)
    issues: List[NoticeIssue] = field(default_factory=list)
    grade_accuracy_flags: List[NoticeIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


def _field_value(notice: Notice, fname: str) -> bool:
    val = getattr(notice, fname, None)
    if val is None:
        return False
    if isinstance(val, str):
        return len(val.strip()) > 0
    if isinstance(val, dict):
        return len(val) > 0
    if isinstance(val, list):
        return len(val) > 0
    return bool(val)


def _check_grade_accuracy(
    notice: Notice, sc: Optional[ScoreCard]
) -> List[str]:
    if not sc:
        return ["점수 카드 없음"]

    issues = []
    grade = sc.priority_grade

    if grade == "A":
        if sc.fitness_score < 30:
            issues.append(f"A등급인데 적합도 {sc.fitness_score}점으로 낮음")
        if not notice.body_text or len(notice.body_text.strip()) < 50:
            issues.append("A등급인데 본문이 거의 없음 — 키워드 매칭 신뢰도 낮음")
        if not notice.deadline_date:
            issues.append("A등급인데 마감일 없음")

    if grade in ("A", "B"):
        if not notice.agency and not notice.ministry:
            issues.append(f"{grade}등급인데 기관·부처 정보 모두 없음")
        if sc.fitness_score > 0 and not sc.positive_keywords:
            issues.append(f"적합도 {sc.fitness_score}점인데 매칭 키워드 목록 비어있음")

    if grade == "D" and sc.fitness_score >= 48:
        issues.append(f"D등급인데 적합도 {sc.fitness_score}점 — 등급 산정 오류 가능")

    return issues


def validate_parsing(
    notices: List[Notice],
    score_cards: List[ScoreCard],
) -> ValidationResult:
    sc_map = {s.notice_id: s for s in score_cards}
    result = ValidationResult(total_notices=len(notices))

    site_data: Dict[str, List[Notice]] = {}
    for n in notices:
        site_data.setdefault(n.site, []).append(n)

    all_fields = REQUIRED_FIELDS + DESIRED_FIELDS
    total_filled = 0
    total_checks = 0

    for site, site_notices in sorted(site_data.items()):
        sr = SiteReport(site=site, total=len(site_notices))
        site_filled = 0
        site_checks = 0

        for fname in all_fields:
            fs = FieldStat(total=len(site_notices))
            for n in site_notices:
                if _field_value(n, fname):
                    fs.filled += 1
            sr.field_stats[fname] = fs
            site_filled += fs.filled
            site_checks += fs.total

        for n in site_notices:
            sc = sc_map.get(n.notice_id)
            grade = sc.priority_grade if sc else "?"
            sr.grade_dist[grade] = sr.grade_dist.get(grade, 0) + 1

        sr.completeness_pct = round(site_filled / site_checks * 100) if site_checks else 0
        result.site_reports.append(sr)
        total_filled += site_filled
        total_checks += site_checks

    result.overall_completeness = round(total_filled / total_checks * 100) if total_checks else 0

    for n in notices:
        sc = sc_map.get(n.notice_id)
        grade = sc.priority_grade if sc else "?"
        notice_issues = []

        for fname in REQUIRED_FIELDS:
            if not _field_value(n, fname):
                notice_issues.append(f"필수 필드 누락: {fname}")

        if n.body_text and len(n.body_text.strip()) < 30:
            notice_issues.append(f"본문 너무 짧음 ({len(n.body_text.strip())}자)")

        if n.title and len(n.title.strip()) < 5:
            notice_issues.append(f"제목 너무 짧음 ({len(n.title.strip())}자)")

        if notice_issues:
            severity = "error" if grade in ("A", "B") else "warning"
            result.issues.append(NoticeIssue(
                notice_id=n.notice_id, title=n.title, site=n.site,
                grade=grade, issues=notice_issues, severity=severity,
            ))

        grade_issues = _check_grade_accuracy(n, sc)
        if grade_issues:
            result.grade_accuracy_flags.append(NoticeIssue(
                notice_id=n.notice_id, title=n.title, site=n.site,
                grade=grade, issues=grade_issues, severity="error",
            ))

    result.total_issues = len(result.issues) + len(result.grade_accuracy_flags)

    best_site = max(result.site_reports, key=lambda s: s.completeness_pct) if result.site_reports else None
    worst_site = min(result.site_reports, key=lambda s: s.completeness_pct) if result.site_reports else None
    result.summary = {
        "total_notices": len(notices),
        "total_sites": len(site_data),
        "overall_completeness": result.overall_completeness,
        "total_issues": result.total_issues,
        "parsing_issues": len(result.issues),
        "grade_flags": len(result.grade_accuracy_flags),
        "best_site": best_site.site if best_site else "-",
        "best_pct": best_site.completeness_pct if best_site else 0,
        "worst_site": worst_site.site if worst_site else "-",
        "worst_pct": worst_site.completeness_pct if worst_site else 0,
    }

    return result
