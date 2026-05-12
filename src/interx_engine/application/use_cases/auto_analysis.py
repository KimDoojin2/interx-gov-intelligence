# -*- coding: utf-8 -*-
"""
AutoAnalysisUseCase — 파이프라인 완료 직후 자동 비지도학습 분석 + 시각화 PNG 생성

비용: 0원 (scikit-learn + matplotlib 로컬 연산)
호출: DailyPipelineOrchestrator.run() 마지막 단계에서 자동 실행
출력: data/analysis/dashboard_{execution_id}.png
"""
from __future__ import annotations

import logging
import os
import warnings
from datetime import date
from typing import List, TYPE_CHECKING

warnings.filterwarnings("ignore")
log = logging.getLogger("interx.auto_analysis")

if TYPE_CHECKING:
    from interx_engine.core.entities.notice import Notice
    from interx_engine.core.entities.score_card import ScoreCard


# ── 외부 라이브러리 lazy import (없으면 graceful skip) ───────────────────────
def _imports_ok() -> bool:
    try:
        import numpy, pandas, sklearn, matplotlib  # noqa: F401
        return True
    except ImportError as e:
        log.warning("[AutoAnalysis] 라이브러리 미설치 — 분석 건너뜀: %s", e)
        return False


def _parse_budget(x: str) -> int:
    """예산 문자열 → 만원 단위 정수. budget_parser.normalize_budget 결과를 재파싱."""
    try:
        from interx_engine.infrastructure.utils.budget_parser import normalize_budget
        norm = normalize_budget(str(x))
        # normalize_budget 반환값이 숫자 문자열인 경우 (예: "30000")
        import re
        m = re.search(r"([0-9.]+)\s*(억|백만|만)?", str(norm).replace(",", ""))
        if not m:
            return 0
        num, unit = float(m.group(1)), m.group(2) or ""
        if "억" in unit:   return int(num * 10000)
        if "백만" in unit: return int(num * 100)
        if "만" in unit:   return int(num)
        return max(0, int(num))
    except Exception:
        return 0


# ── 클러스터 색·레이블 ────────────────────────────────────────────────────────
_CLUSTER_COLORS = [
    "#f0c040", "#ff8c00", "#555577", "#8899aa",
    "#ff4444", "#778899", "#445566", "#4488cc",
]
_GRADE_COLORS = {"A": "#ff4444", "B": "#ff8c00", "C": "#f0c040", "D": "#445566"}


def run_auto_analysis(
    notices: List,
    score_cards: List,
    execution_id: str,
    out_dir: str = "data/analysis",
) -> str:
    """
    비지도학습 분석 + 시각화 PNG 저장.

    Returns
    -------
    str : 저장된 PNG 경로 (실패 시 빈 문자열)
    """
    if not _imports_ok():
        return ""

    import numpy as np
    import pandas as pd
    from collections import Counter
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib import font_manager
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import silhouette_score

    # ── 한글 폰트 ──────────────────────────────────────────────────────────────
    for fp in [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
    ]:
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            prop = font_manager.FontProperties(fname=fp)
            plt.rcParams["font.family"] = prop.get_name()
            break

    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"]   = "#0f1117"
    plt.rcParams["axes.facecolor"]     = "#1a1d2e"
    plt.rcParams["text.color"]         = "#e8eaf6"
    plt.rcParams["axes.labelcolor"]    = "#e8eaf6"
    plt.rcParams["xtick.color"]        = "#b0b8d0"
    plt.rcParams["ytick.color"]        = "#b0b8d0"
    plt.rcParams["axes.edgecolor"]     = "#2d3154"
    plt.rcParams["grid.color"]         = "#2d3154"
    plt.rcParams["grid.alpha"]         = 0.5

    try:
        # ── DataFrame 빌드 ─────────────────────────────────────────────────────
        score_map = {sc.notice_id: sc for sc in score_cards}
        rows = []
        for n in notices:
            sc = score_map.get(n.notice_id)
            rows.append({
                "title":    n.title or "",
                "site":     n.site or "",
                "agency":   n.agency or "",
                "grade":    getattr(sc, "priority_grade", "D") if sc else "D",
                "fitness":  float(getattr(sc, "fitness_score",  0) or 0),
                "budget":   _parse_budget(n.budget or ""),
                "l3":       1 if n.l3_strong == "Y" else 0,
                "partner":  1 if n.partner_candidate == "Y" else 0,
                "keywords": n.recommended_solution or "",
                "solution": getattr(sc, "recommended_solution", "-") if sc else "-",
                "dday": (
                    (date.fromisoformat(n.deadline_date[:10]) - date.today()).days
                    if n.deadline_date and not n.open_ended
                    else 999
                ),
            })

        if not rows:
            log.warning("[AutoAnalysis] 공고 없음 — 스킵")
            return ""

        df = pd.DataFrame(rows)
        grade_map_num = {"A": 4, "B": 3, "C": 2, "D": 1}
        df["grade_num"] = df["grade"].map(grade_map_num).fillna(1)
        df["dday_clip"] = df["dday"].clip(0, 365)
        df["budget_log"] = np.log1p(df["budget"])
        df["urgent"] = ((df["dday"] >= 0) & (df["dday"] <= 7)).astype(int)
        total = len(df)

        # ── K-Means ────────────────────────────────────────────────────────────
        feat_cols = ["fitness", "dday_clip", "budget_log", "l3", "partner", "grade_num", "urgent"]
        X = df[feat_cols].fillna(0).values
        scaler = StandardScaler()
        X_s = scaler.fit_transform(X)

        best_k, best_sil = 2, -1.0
        for k in range(2, min(9, total)):
            km_tmp = KMeans(n_clusters=k, random_state=42, n_init=10)
            lbl = km_tmp.fit_predict(X_s)
            sil = silhouette_score(X_s, lbl)
            if sil > best_sil:
                best_sil, best_k = sil, k

        km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        df["cluster"] = km.fit_predict(X_s)

        pca = PCA(n_components=2, random_state=42)
        X_2d = pca.fit_transform(X_s)
        df["pca1"], df["pca2"] = X_2d[:, 0], X_2d[:, 1]

        iso = IsolationForest(contamination=0.05, random_state=42)
        df["anomaly"] = iso.fit_predict(X_s)

        # ── 키워드 카운터 ──────────────────────────────────────────────────────
        kw_counter = Counter()
        for row in df["keywords"]:
            for kw in str(row).split("|"):
                for k2 in kw.strip().split(","):
                    k2 = k2.strip().lower()
                    if k2 and k2 not in ("", "-", "nan"):
                        kw_counter[k2] += 1

        # ── 시각화 그리기 ──────────────────────────────────────────────────────
        fig = plt.figure(figsize=(20, 16))
        fig.patch.set_facecolor("#0f1117")
        gs  = GridSpec(3, 3, figure=fig,
                       hspace=0.45, wspace=0.38,
                       left=0.06, right=0.97, top=0.92, bottom=0.05)
        TXT, DIM = "#e8eaf6", "#8892b0"
        BLUE, RED, YEL, GRN = "#7c83ff", "#ff7c7c", "#ffd07c", "#7cffa0"

        def _ax(ax, title):
            ax.set_facecolor("#1a1d2e")
            ax.set_title(title, color=TXT, fontsize=10, fontweight="bold", pad=7)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values(): sp.set_edgecolor("#2d3154")
            ax.grid(True, color="#2d3154", alpha=0.5, linestyle="--", linewidth=0.5)

        # ① 도넛 — 등급 분포
        ax0 = fig.add_subplot(gs[0, 0])
        ax0.set_facecolor("#1a1d2e")
        ax0.set_title("우선순위 등급 분포", color=TXT, fontsize=10, fontweight="bold", pad=7)
        grade_cnt = df["grade"].value_counts().reindex(["A","B","C","D"], fill_value=0)
        gvals     = [int(grade_cnt[g]) for g in ["A","B","C","D"]]
        gcols     = ["#ff4444","#ff8c00","#f0c040","#445566"]
        wedges, _, autotexts = ax0.pie(
            gvals, labels=["A","B","C","D"], colors=gcols,
            autopct="%1.0f%%", startangle=90, pctdistance=0.75,
            wedgeprops=dict(width=0.55, edgecolor="#0f1117", linewidth=2),
            textprops={"color": TXT, "fontsize": 9, "fontweight": "bold"},
        )
        for at in autotexts:
            at.set_color("#0f1117"); at.set_fontsize(7.5)
        ax0.text(0, 0, f"{total}\n건", ha="center", va="center",
                 fontsize=13, fontweight="bold", color=TXT)
        ax0.legend([f"{g}: {v}건" for g, v in zip(["A","B","C","D"], gvals)],
                   loc="lower right", fontsize=6.5, framealpha=0.2,
                   labelcolor=TXT, facecolor="#1a1d2e")

        # ② PCA 산점도
        ax1 = fig.add_subplot(gs[0, 1])
        _ax(ax1, f"PCA 2D — 클러스터 (K={best_k}, 실루엣={best_sil:.3f})")
        for c in range(best_k):
            m = df["cluster"] == c
            col = _CLUSTER_COLORS[c % len(_CLUSTER_COLORS)]
            ax1.scatter(df.loc[m, "pca1"], df.loc[m, "pca2"],
                        c=col, s=35, alpha=0.75, edgecolors="none", label=f"C{c}")
        anom = df[df["anomaly"] == -1]
        ax1.scatter(anom["pca1"], anom["pca2"],
                    c="none", s=100, edgecolors="#ff4444", linewidths=1.5, zorder=5, label="이상치")
        cx2d = pca.transform(km.cluster_centers_)
        ax1.scatter(cx2d[:, 0], cx2d[:, 1], marker="X", s=100, c="white",
                    edgecolors="#0f1117", linewidths=0.8, zorder=6)
        for c, (cx, cy) in enumerate(cx2d):
            ax1.annotate(str(c), (cx, cy), xytext=(4, 3),
                         textcoords="offset points", fontsize=7, color="white", fontweight="bold")
        ax1.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.0f}%)", color=DIM, fontsize=8)
        ax1.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.0f}%)", color=DIM, fontsize=8)
        ax1.legend(fontsize=6, framealpha=0.15, labelcolor=TXT,
                   facecolor="#1a1d2e", loc="upper left", ncol=3)

        # ③ 적합도 히스토그램
        ax2 = fig.add_subplot(gs[0, 2])
        _ax(ax2, "적합도 점수 분포")
        nz = df[df["fitness"] > 0]["fitness"]
        if len(nz) > 0:
            n_bins, bins, patches = ax2.hist(nz, bins=12, color=BLUE, alpha=0.8,
                                              edgecolor="#0f1117", linewidth=0.5)
            for i, patch in enumerate(patches):
                v = (bins[i] + bins[i+1]) / 2
                patch.set_facecolor(plt.cm.RdYlGn(0.2 + v / max(df["fitness"].max(), 1) * 0.8))
        ax2.axvline(x=18, color="#f0c040", linestyle="--", lw=1.2, label="C기준(18)")
        ax2.axvline(x=30, color="#ff8c00", linestyle="--", lw=1.2, label="B기준(30)")
        ax2.axvline(x=48, color="#ff4444", linestyle="--", lw=1.2, label="A기준(48)")
        ax2.text(0.03, 0.92, f"0점: {int((df['fitness']==0).sum())}건",
                 transform=ax2.transAxes, color=RED, fontsize=7.5, va="top",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#2a1a2e", alpha=0.7))
        ax2.set_xlabel("적합도 점수", color=DIM, fontsize=8)
        ax2.set_ylabel("공고 수", color=DIM, fontsize=8)
        ax2.legend(fontsize=7, framealpha=0.2, labelcolor=TXT, facecolor="#1a1d2e")

        # ④ 사이트별 수집
        ax3 = fig.add_subplot(gs[1, 0])
        _ax(ax3, "사이트별 수집 현황")
        sd = df.groupby("site").agg(
            total=("title","count"), l3=("l3","sum"),
            ab=("grade_num", lambda x: int((x>=3).sum()))
        ).sort_values("total", ascending=True)
        y = range(len(sd))
        ax3.barh(list(y), sd["total"].tolist(), color=BLUE, alpha=0.7, height=0.6)
        ax3.barh(list(y), sd["ab"].tolist(),    color=YEL,  alpha=0.9, height=0.6, label="AB등급")
        ax3.barh(list(y), sd["l3"].tolist(),    color=RED,  alpha=0.95, height=0.6, label="L3")
        ax3.set_yticks(list(y))
        ax3.set_yticklabels(sd.index.tolist(), fontsize=7.5, color=TXT)
        ax3.set_xlabel("공고 수", color=DIM, fontsize=8)
        for i, v in enumerate(sd["total"].tolist()):
            ax3.text(v + 0.2, i, str(v), va="center", fontsize=7, color=TXT)
        ax3.legend(fontsize=7, framealpha=0.2, labelcolor=TXT, facecolor="#1a1d2e")

        # ⑤ 솔루션 수요
        ax4 = fig.add_subplot(gs[1, 1])
        _ax(ax4, "솔루션 수요 분포")
        sol_c = Counter()
        for s in df["solution"]:
            for part in str(s).split("/"):
                p = part.strip()
                if p and p != "-":
                    sol_c[p] += 1
        if sol_c:
            snames = list(sol_c.keys())
            svals  = list(sol_c.values())
            scols  = [BLUE, RED, GRN, YEL, "#c07cff", "#7cdfff", "#ff9f7c", "#a0ff7c"]
            bars = ax4.bar(range(len(snames)), svals,
                           color=scols[:len(snames)], alpha=0.85,
                           edgecolor="#0f1117", linewidth=0.5)
            ax4.set_xticks(range(len(snames)))
            ax4.set_xticklabels(
                [s.replace("Manufacturing","Mfg.") for s in snames],
                rotation=35, ha="right", fontsize=7.5, color=TXT)
            ax4.set_ylabel("공고 수", color=DIM, fontsize=8)
            for bar, v in zip(bars, svals):
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                         str(v), ha="center", fontsize=8, color=TXT, fontweight="bold")

        # ⑥ 키워드 빈도
        ax5 = fig.add_subplot(gs[1, 2])
        _ax(ax5, "적합 키워드 빈도 Top-12")
        top_kws = kw_counter.most_common(12)
        if top_kws:
            knames = [k for k, _ in top_kws][::-1]
            kvals  = [v for _, v in top_kws][::-1]
            cmap_c = plt.cm.cool
            kcols  = [cmap_c(i / max(len(knames)-1, 1)) for i in range(len(knames))]
            ax5.barh(range(len(knames)), kvals, color=kcols, alpha=0.85, height=0.65)
            ax5.set_yticks(range(len(knames)))
            ax5.set_yticklabels(knames, fontsize=8, color=TXT)
            ax5.set_xlabel("등장 횟수", color=DIM, fontsize=8)
            for i, v in enumerate(kvals):
                ax5.text(v + 0.05, i, str(v), va="center", fontsize=7.5, color=TXT)

        # ⑦ 클러스터별 평균 적합도 막대
        ax6 = fig.add_subplot(gs[2, 0])
        _ax(ax6, f"클러스터별 평균 적합도 (K={best_k})")
        c_ids  = list(range(best_k))
        c_fits = [df[df["cluster"]==c]["fitness"].mean() for c in c_ids]
        c_cnt  = [int((df["cluster"]==c).sum()) for c in c_ids]
        c_l3   = [int(df[df["cluster"]==c]["l3"].sum()) for c in c_ids]
        ccols  = [_CLUSTER_COLORS[c % len(_CLUSTER_COLORS)] for c in c_ids]
        bars_c = ax6.bar(c_ids, c_fits, color=ccols, alpha=0.85,
                         edgecolor="#0f1117", linewidth=0.5)
        ax6.axhline(y=18, color="#f0c040", linestyle="--", lw=1, alpha=0.7, label="C기준")
        ax6.axhline(y=30, color="#ff8c00", linestyle="--", lw=1, alpha=0.7, label="B기준")
        ax6.set_xlabel("클러스터", color=DIM, fontsize=8)
        ax6.set_ylabel("평균 적합도", color=DIM, fontsize=8)
        for bar, v, cnt, l3c in zip(bars_c, c_fits, c_cnt, c_l3):
            ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                     f"{v:.1f}\n({cnt}건)", ha="center", fontsize=6.5, color=TXT)
        ax6.legend(fontsize=7, framealpha=0.2, labelcolor=TXT, facecolor="#1a1d2e")

        # ⑧ D-day 긴급도
        ax7 = fig.add_subplot(gs[2, 1])
        _ax(ax7, "D-day 긴급도 분포")
        dranges = [
            ("오늘", 0, 0), ("D1~3", 1, 3), ("D4~7", 4, 7),
            ("D8~14", 8, 14), ("D15~30", 15, 30), ("D31~90", 31, 90),
            ("D91~365", 91, 365), ("D365+", 366, 9999),
        ]
        dlabels = [r[0] for r in dranges]
        dvals   = []
        for _, lo, hi in dranges:
            if lo == hi == 0:
                dvals.append(int((df["dday"] == 0).sum()))
            else:
                dvals.append(int(((df["dday"] >= lo) & (df["dday"] <= hi)).sum()))
        dcols = ["#ff2222","#ff5544","#ff8833","#ffbb44","#88cc66","#44aacc","#4488ff","#334488"]
        bars7 = ax7.bar(range(len(dlabels)), dvals, color=dcols, alpha=0.85,
                        edgecolor="#0f1117", linewidth=0.5)
        ax7.set_xticks(range(len(dlabels)))
        ax7.set_xticklabels(dlabels, rotation=30, ha="right", fontsize=8, color=TXT)
        ax7.set_ylabel("공고 수", color=DIM, fontsize=8)
        for bar, v in zip(bars7, dvals):
            if v > 0:
                ax7.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                         str(v), ha="center", fontsize=8, color=TXT, fontweight="bold")

        # ⑨ Isolation Forest 산점도
        ax8 = fig.add_subplot(gs[2, 2])
        _ax(ax8, "Isolation Forest 이상치 탐지")
        normal = df[df["anomaly"] == 1]
        anomaly= df[df["anomaly"] == -1]
        ax8.scatter(normal["fitness"],  normal["dday_clip"],
                    c=BLUE, s=25, alpha=0.45, edgecolors="none", label=f"정상({len(normal)}건)")
        ax8.scatter(anomaly["fitness"], anomaly["dday_clip"],
                    c=RED, s=70, alpha=0.9, edgecolors="white", linewidths=0.7,
                    marker="*", zorder=5, label=f"이상치({len(anomaly)}건)")
        ax8.axvline(x=18, color="#f0c040", linestyle="--", lw=1, alpha=0.6)
        ax8.axvline(x=30, color="#ff8c00", linestyle="--", lw=1, alpha=0.6)
        ax8.set_xlabel("적합도 점수", color=DIM, fontsize=8)
        ax8.set_ylabel("D-day (일)", color=DIM, fontsize=8)
        ax8.legend(fontsize=7.5, framealpha=0.2, labelcolor=TXT, facecolor="#1a1d2e")

        # ── 타이틀 & 저장 ─────────────────────────────────────────────────────
        fig.suptitle(
            f"InterX 파이프라인 비지도학습 자동 분석 대시보드\n"
            f"{execution_id}  |  총 {total}건  |  K-Means K={best_k}(실루엣={best_sil:.3f})",
            fontsize=12, fontweight="bold", color=TXT, y=0.975,
        )

        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"dashboard_{execution_id}.png")
        plt.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor="#0f1117", edgecolor="none")
        plt.close(fig)
        log.info("[AutoAnalysis] 대시보드 저장: %s", out_path)

        # 최신 버전 심볼릭 복사
        latest = os.path.join(out_dir, "dashboard_latest.png")
        try:
            import shutil
            shutil.copy2(out_path, latest)
        except Exception:
            pass

        return out_path

    except Exception as e:
        log.warning("[AutoAnalysis] 분석 실패 (파이프라인 영향 없음): %s", e, exc_info=True)
        return ""
