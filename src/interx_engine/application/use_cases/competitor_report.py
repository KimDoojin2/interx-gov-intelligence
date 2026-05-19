"""
경쟁사 분석 리포트 자동 생성 — matplotlib + pandas 기반
track_competitors() 이후 결과를 시각화·통계화하여 PNG + CSV 저장
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.competitor_report")


def _load_competitors() -> dict:
    """configs/competitors.yaml 로드."""
    import yaml
    base = Path(__file__).resolve()
    for p in [
        base.parents[4] / "configs/competitors.yaml",   # src 기준
        base.parents[5] / "configs/competitors.yaml",   # 하위 호환
        Path("/content/drive/MyDrive/interx_gov_intelligence/configs/competitors.yaml"),
    ]:
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")).get("competitors", {})
    return {}


def generate_competitor_report(
    notices: List[Notice],
    score_cards: List[ScoreCard],
    output_dir: str = "",
    execution_id: str = "",
) -> Dict[str, Any]:
    """
    경쟁사 분석 리포트 생성.

    Returns:
        {
            "summary": {...},         # 통계 요약
            "chart_path": str,        # PNG 차트 경로
            "csv_path": str,          # CSV 상세 데이터 경로
            "competitor_notices": [...] # 경쟁사 관련 공고 목록
        }
    """
    comp = _load_competitors()
    tier1 = [c.lower() for c in comp.get("tier1", [])]
    tier2 = [c.lower() for c in comp.get("tier2", [])]
    partners = [c.lower() for c in comp.get("partners", [])]
    all_names = {n: "tier1" for n in tier1}
    all_names.update({n: "tier2" for n in tier2})
    all_names.update({n: "partner" for n in partners})

    score_map = {s.notice_id: s for s in score_cards}

    # ── 분석 ────────────────────────────────────────────────────────────────
    competitor_notices = []       # 경쟁사 관련 공고
    comp_counter = Counter()     # 경쟁사별 출현 횟수
    tier_counter = Counter()     # tier별 건수
    grade_by_comp = defaultdict(lambda: Counter())  # 경쟁사별 등급 분포
    site_by_comp = defaultdict(set)                  # 경쟁사별 사이트
    monthly_comp = defaultdict(lambda: Counter())    # 월별 경쟁사 활동

    for notice in notices:
        text = f"{notice.agency} {notice.ministry} {notice.title}".lower()
        matched = []
        for name, tier in all_names.items():
            if name in text:
                matched.append((name, tier))
                comp_counter[name] += 1
                tier_counter[tier] += 1
                sc = score_map.get(notice.notice_id)
                grade = sc.priority_grade if sc else "D"
                grade_by_comp[name][grade] += 1
                site_by_comp[name].add(notice.site)
                # 월별
                month = (notice.posted_date or "")[:7]
                if month:
                    monthly_comp[month][name] += 1

        if matched:
            sc = score_map.get(notice.notice_id)
            competitor_notices.append({
                "notice_id": notice.notice_id,
                "title": notice.title,
                "site": notice.site,
                "deadline": notice.deadline_date,
                "grade": sc.priority_grade if sc else "D",
                "competitors": [m[0] for m in matched],
                "tiers": [m[1] for m in matched],
            })

    # ── 요약 통계 ────────────────────────────────────────────────────────────
    summary = {
        "total_notices": len(notices),
        "competitor_related": len(competitor_notices),
        "competitor_ratio": round(len(competitor_notices) / max(1, len(notices)) * 100, 1),
        "tier1_count": tier_counter.get("tier1", 0),
        "tier2_count": tier_counter.get("tier2", 0),
        "partner_count": tier_counter.get("partner", 0),
        "top_competitors": comp_counter.most_common(10),
        "grade_distribution": {
            name: dict(grades) for name, grades in grade_by_comp.items()
        },
    }

    # ── 출력 디렉토리 ────────────────────────────────────────────────────────
    if not output_dir:
        output_dir = str(Path(__file__).resolve().parents[5] / "data" / "analysis")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ts = execution_id or datetime.now().strftime("%Y%m%d-%H%M%S")

    # ── CSV 저장 ─────────────────────────────────────────────────────────────
    csv_path = out / f"competitor_report_{ts}.csv"
    try:
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "notice_id", "title", "site", "deadline", "grade", "competitors", "tiers"
            ])
            writer.writeheader()
            for row in competitor_notices:
                writer.writerow({
                    **row,
                    "competitors": " | ".join(row["competitors"]),
                    "tiers": " | ".join(row["tiers"]),
                })
        log.info("[CompReport] CSV: %s", csv_path)
    except Exception as e:
        log.warning("[CompReport] CSV 저장 실패: %s", e)
        csv_path = ""

    # ── 차트 PNG ─────────────────────────────────────────────────────────────
    chart_path = out / f"competitor_chart_{ts}.png"
    try:
        chart_path = _generate_chart(
            comp_counter, tier_counter, grade_by_comp, monthly_comp,
            len(notices), chart_path,
        )
        log.info("[CompReport] Chart: %s", chart_path)
    except Exception as e:
        log.warning("[CompReport] 차트 생성 실패: %s", e)
        chart_path = ""

    result = {
        "summary": summary,
        "chart_path": str(chart_path),
        "csv_path": str(csv_path),
        "competitor_notices": competitor_notices,
    }
    log.info(
        "[CompReport] 경쟁사 관련 %d건 / 전체 %d건 (%.1f%%)",
        len(competitor_notices), len(notices), summary["competitor_ratio"],
    )
    return result


def _generate_chart(
    comp_counter: Counter,
    tier_counter: Counter,
    grade_by_comp: dict,
    monthly_comp: dict,
    total_notices: int,
    output_path: Path,
) -> Path:
    """4패널 경쟁사 분석 차트 생성."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    # 한글 폰트 설정
    for font_name in ["Malgun Gothic", "NanumGothic", "AppleGothic"]:
        if any(font_name in f.name for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False

    NAVY = "#0A1628"
    CYAN = "#00CFFF"
    GOLD = "#FFD700"
    COLORS = {
        "tier1": "#FF6B6B",  # 빨강 (직접 경쟁)
        "tier2": "#4ECDC4",  # 민트 (간접 경쟁)
        "partner": "#45B7D1",  # 파랑 (파트너)
    }
    GRADE_COLORS = {"A": "#22C55E", "B": "#00CFFF", "C": "#FFD700", "D": "#EF4444"}

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor=NAVY)
    fig.suptitle(
        "Competition Intelligence Report",
        fontsize=18, fontweight="bold", color="white", y=0.97,
    )

    for ax in axes.flat:
        ax.set_facecolor(NAVY)
        ax.tick_params(colors="white", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#2A3A5C")

    # ── 1. 경쟁사 TOP10 (가로 막대) ────────────────────────────────────────
    ax1 = axes[0, 0]
    top10 = comp_counter.most_common(10)
    if top10:
        names, counts = zip(*reversed(top10))
        colors = []
        comp_data = _load_competitors()
        tier1_set = {c.lower() for c in comp_data.get("tier1", [])}
        for n in names:
            colors.append(COLORS["tier1"] if n in tier1_set else COLORS["tier2"])
        ax1.barh(range(len(names)), counts, color=colors, height=0.6)
        ax1.set_yticks(range(len(names)))
        ax1.set_yticklabels(names, color="white", fontsize=9)
        ax1.set_xlabel("Detection Count", color="gray", fontsize=9)
    ax1.set_title("Top 10 Competitors", color=CYAN, fontsize=12, pad=10)

    # ── 2. Tier 분포 (도넛) ────────────────────────────────────────────────
    ax2 = axes[0, 1]
    tier_data = [(k, v) for k, v in tier_counter.items() if v > 0]
    if tier_data:
        labels, sizes = zip(*tier_data)
        tier_colors = [COLORS.get(l, CYAN) for l in labels]
        label_map = {"tier1": "Tier1 (Direct)", "tier2": "Tier2 (Indirect)", "partner": "Partners"}
        display_labels = [label_map.get(l, l) for l in labels]
        wedges, texts, autotexts = ax2.pie(
            sizes, labels=display_labels, colors=tier_colors, autopct="%1.0f%%",
            startangle=90, wedgeprops={"width": 0.5, "edgecolor": NAVY},
            textprops={"color": "white", "fontsize": 10},
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
    ax2.set_title("Tier Distribution", color=CYAN, fontsize=12, pad=10)

    # ── 3. 경쟁사별 등급 분포 (스택 바) ─────────────────────────────────────
    ax3 = axes[1, 0]
    top5 = comp_counter.most_common(5)
    if top5:
        top5_names = [n for n, _ in top5]
        x = range(len(top5_names))
        bottom = [0] * len(top5_names)
        for grade in ["A", "B", "C", "D"]:
            vals = [grade_by_comp[n].get(grade, 0) for n in top5_names]
            ax3.bar(x, vals, bottom=bottom, color=GRADE_COLORS[grade],
                    label=f"Grade {grade}", width=0.5)
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax3.set_xticks(x)
        ax3.set_xticklabels(top5_names, color="white", fontsize=9, rotation=15)
        ax3.legend(loc="upper right", fontsize=8, facecolor=NAVY,
                   edgecolor="#2A3A5C", labelcolor="white")
    ax3.set_title("Competitor x Grade (Top 5)", color=CYAN, fontsize=12, pad=10)
    ax3.set_ylabel("Notices", color="gray", fontsize=9)

    # ── 4. 월별 경쟁사 활동 트렌드 ──────────────────────────────────────────
    ax4 = axes[1, 1]
    if monthly_comp:
        months = sorted(monthly_comp.keys())[-6:]  # 최근 6개월
        month_totals = [sum(monthly_comp[m].values()) for m in months]
        ax4.plot(months, month_totals, color=CYAN, marker="o", linewidth=2,
                 markersize=6, markerfacecolor=GOLD)
        ax4.fill_between(months, month_totals, alpha=0.15, color=CYAN)
        ax4.set_xticklabels(months, color="white", fontsize=8, rotation=30)
        for i, v in enumerate(month_totals):
            ax4.annotate(str(v), (months[i], v), textcoords="offset points",
                         xytext=(0, 8), color="white", fontsize=9, ha="center")
    ax4.set_title("Monthly Competitor Activity", color=CYAN, fontsize=12, pad=10)
    ax4.set_ylabel("Detections", color="gray", fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(str(output_path), dpi=150, facecolor=NAVY, bbox_inches="tight")
    plt.close()
    return output_path
