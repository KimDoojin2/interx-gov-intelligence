"""
InterX BD Intelligence — 포트폴리오 분석 모듈
=================================================
4개 분석 컴포넌트:
  1. 시계열 트렌드    — 수집량·KPI 변화 추이
  2. 키워드 워드클라우드 — 공고명·키워드 빈도 시각화
  3. K-Means 클러스터링 — 공고 유사도 기반 자동 분류
  4. 수주가능성 예측   — 멀티팩터 스코어링 + 피처 중요도

Colab 실행 방법:
  import sys
  sys.path.insert(0, "/content/drive/MyDrive/interx_gov_intelligence/src")
  from interx_engine.interfaces.analysis.portfolio_analysis import run_all
  run_all(sheet_name="InterX_BD_CRM_v10", sa_path="service_account.json")
"""
from __future__ import annotations

import os
import re
import warnings
from collections import Counter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── 한글 폰트 설정 ────────────────────────────────────────────────────────────
def _setup_font():
    import matplotlib
    import matplotlib.pyplot as plt
    try:
        import subprocess
        subprocess.run(["apt-get", "install", "-y", "-q", "fonts-nanum"], capture_output=True)
        matplotlib.font_manager._load_fontmanager(try_read_cache=False)
    except Exception:
        pass
    for font in ["NanumGothic", "NanumBarunGothic", "Malgun Gothic", "AppleGothic", "sans-serif"]:
        try:
            matplotlib.rc("font", family=font)
            plt.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue

_setup_font()

# ── Google Sheets 로더 ────────────────────────────────────────────────────────
def _load_sheet(gc, sheet_name: str, ws_name: str) -> pd.DataFrame:
    try:
        ws   = gc.open(sheet_name).worksheet(ws_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        print(f"  ⚠️  {ws_name} 로드 실패: {e}")
        return pd.DataFrame()


def load_data(sheet_name: str, sa_path: str) -> dict:
    """Google Sheets에서 전체 데이터 로드."""
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        sa_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    gc = gspread.authorize(creds)
    return {
        "notices":    _load_sheet(gc, sheet_name, "01_영업기회_정보"),
        "kpi":        _load_sheet(gc, sheet_name, "22_KPI현황"),
        "site_stats": _load_sheet(gc, sheet_name, "93_사이트별수집통계"),
        "exec_log":   _load_sheet(gc, sheet_name, "94_실행로그"),
        "errors":     _load_sheet(gc, sheet_name, "96_수집에러로그"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 분석 1 — 시계열 트렌드
# ─────────────────────────────────────────────────────────────────────────────
def analysis_timeseries(data: dict) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    print("\n" + "="*55)
    print("📈 분석 1 — 시계열 수집 트렌드")
    print("="*55)

    stat_df = data.get("site_stats", pd.DataFrame())
    kpi_df  = data.get("kpi", pd.DataFrame())

    if stat_df.empty and kpi_df.empty:
        print("  ℹ️  누적 데이터 없음 — 2회 이상 실행 후 확인 가능")
        return

    fig = plt.figure(figsize=(16, 10))
    gs  = gridspec.GridSpec(2, 2, hspace=0.4, wspace=0.35)

    # ── 패널 1: 일별 전체 수집 건수 ─────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    if not stat_df.empty and "기준일" in stat_df.columns:
        stat_df["기준일"] = pd.to_datetime(stat_df["기준일"], errors="coerce")
        stat_df["수집건수"] = pd.to_numeric(stat_df["수집건수"], errors="coerce").fillna(0)
        daily = stat_df.groupby("기준일")["수집건수"].sum().reset_index()
        ax1.plot(daily["기준일"], daily["수집건수"], marker="o", linewidth=2.5,
                 color="#1565c0", markersize=6, label="전체 수집건수")
        ax1.fill_between(daily["기준일"], daily["수집건수"], alpha=0.15, color="#1565c0")
        ax1.set_title("일별 전체 수집 공고 수 트렌드", fontsize=14, fontweight="bold", pad=12)
        ax1.set_xlabel("날짜"); ax1.set_ylabel("수집 건수")
        ax1.grid(True, alpha=0.3); ax1.legend()
        # 최고점 표시
        if not daily.empty:
            idx = daily["수집건수"].idxmax()
            ax1.annotate(f"최대 {int(daily.loc[idx,'수집건수'])}건",
                         xy=(daily.loc[idx,"기준일"], daily.loc[idx,"수집건수"]),
                         xytext=(10, 10), textcoords="offset points",
                         arrowprops=dict(arrowstyle="->", color="red"), color="red")
    else:
        ax1.text(0.5, 0.5, "데이터 누적 중...", ha="center", va="center",
                 transform=ax1.transAxes, fontsize=13, color="gray")
        ax1.set_title("일별 수집 트렌드 (누적 대기)")

    # ── 패널 2: 사이트별 최근 수집 현황 ─────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    if not stat_df.empty and "사이트" in stat_df.columns:
        latest = stat_df[stat_df["실행ID"] == stat_df["실행ID"].iloc[-1]] if "실행ID" in stat_df.columns else stat_df
        site_sum = latest.groupby("사이트")["수집건수"].sum().sort_values(ascending=True)
        colors = ["#1565c0" if v > site_sum.mean() else "#90caf9" for v in site_sum.values]
        site_sum.plot(kind="barh", ax=ax2, color=colors)
        ax2.set_title("최근 실행 사이트별 수집 건수", fontsize=12, fontweight="bold")
        ax2.set_xlabel("수집 건수")
        for i, v in enumerate(site_sum.values):
            ax2.text(v + 0.3, i, str(int(v)), va="center", fontsize=9)
    else:
        ax2.text(0.5, 0.5, "데이터 없음", ha="center", va="center", transform=ax2.transAxes, color="gray")

    # ── 패널 3: KPI 추이 (전체공고수) ─────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    if not kpi_df.empty and "구분" in kpi_df.columns:
        total_kpi = kpi_df[(kpi_df["구분"] == "수집현황") & (kpi_df["지표"] == "전체공고수")].copy()
        if not total_kpi.empty:
            total_kpi["기준일"] = pd.to_datetime(total_kpi["기준일"], errors="coerce")
            total_kpi["값"] = pd.to_numeric(total_kpi["값"], errors="coerce")
            ax3.bar(range(len(total_kpi)), total_kpi["값"], color="#42a5f5", edgecolor="white")
            ax3.set_xticks(range(len(total_kpi)))
            ax3.set_xticklabels([str(d.date()) if pd.notna(d) else "" for d in total_kpi["기준일"]],
                                 rotation=30, ha="right", fontsize=8)
            ax3.set_title("실행별 전체 공고 수 KPI", fontsize=12, fontweight="bold")
            ax3.set_ylabel("건수")
            ax3.grid(True, alpha=0.3, axis="y")
    else:
        ax3.text(0.5, 0.5, "KPI 데이터 없음", ha="center", va="center", transform=ax3.transAxes, color="gray")

    plt.suptitle("InterX BD Intelligence — 시계열 트렌드 분석", fontsize=16, fontweight="bold", y=1.01)
    plt.savefig("analysis_1_timeseries.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("  💾 analysis_1_timeseries.png 저장 완료")


# ─────────────────────────────────────────────────────────────────────────────
# 분석 2 — 키워드 워드클라우드
# ─────────────────────────────────────────────────────────────────────────────
def analysis_wordcloud(data: dict) -> None:
    import matplotlib.pyplot as plt

    print("\n" + "="*55)
    print("🔤 분석 2 — 키워드 워드클라우드")
    print("="*55)

    df = data.get("notices", pd.DataFrame())
    if df.empty:
        print("  ℹ️  공고 데이터 없음"); return

    try:
        from wordcloud import WordCloud
    except ImportError:
        print("  ⚠️  wordcloud 미설치: !pip install wordcloud")
        return

    # 키워드 추출 (공고명 + 적합키워드)
    text_sources = {
        "공고명": df["공고명"].dropna().tolist() if "공고명" in df.columns else [],
        "적합키워드": [],
    }
    if "적합키워드" in df.columns:
        for kw in df["적합키워드"].dropna():
            text_sources["적합키워드"].extend([k.strip() for k in str(kw).split("|") if k.strip()])

    # 불용어
    stop_words = {"및","의","를","을","이","가","에","으로","으","와","과","년","월","지원","사업",
                  "공고","모집","선정","추진","운영","관련","해당","위한","통한","위해","대한",
                  "2024","2025","2026","접수","신청","제출","결과"}

    def _extract_nouns(texts):
        words = []
        for t in texts:
            # 2글자 이상 한글 단어 추출
            words.extend([w for w in re.findall(r"[가-힣]{2,}", str(t)) if w not in stop_words])
        return words

    title_words = _extract_nouns(text_sources["공고명"])
    kw_words    = text_sources["적합키워드"]

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    for ax, (words, label, color) in zip(axes, [
        (title_words, "공고명 핵심 키워드", "Blues"),
        (kw_words,    "적합 키워드",        "Oranges"),
    ]):
        if not words:
            ax.text(0.5, 0.5, f"{label} 없음", ha="center", va="center",
                    transform=ax.transAxes, fontsize=13, color="gray")
            ax.set_title(label); ax.axis("off"); continue

        freq = Counter(words)
        top  = dict(freq.most_common(80))

        # 한글 폰트 경로 탐색
        font_path = None
        for p in ["/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                  "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
                  "C:/Windows/Fonts/malgun.ttf"]:
            if Path(p).exists():
                font_path = p; break

        wc_kwargs = dict(
            width=900, height=450, background_color="white",
            colormap=color, max_words=80, prefer_horizontal=0.8,
        )
        if font_path:
            wc_kwargs["font_path"] = font_path

        wc = WordCloud(**wc_kwargs).generate_from_frequencies(top)
        ax.imshow(wc, interpolation="bilinear")
        ax.set_title(f"{label} (상위 {len(top)}개)", fontsize=13, fontweight="bold", pad=10)
        ax.axis("off")

        # 상위 10개 텍스트 출력
        top10 = freq.most_common(10)
        print(f"\n  [{label} Top 10]")
        for word, cnt in top10:
            bar = "█" * (cnt // max(1, top10[0][1] // 20))
            print(f"    {word:<12} {bar} {cnt}")

    plt.suptitle("InterX BD Intelligence — 키워드 워드클라우드", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig("analysis_2_wordcloud.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("\n  💾 analysis_2_wordcloud.png 저장 완료")


# ─────────────────────────────────────────────────────────────────────────────
# 분석 3 — K-Means 클러스터링
# ─────────────────────────────────────────────────────────────────────────────
def analysis_clustering(data: dict, n_clusters: int = 6) -> pd.DataFrame:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    print("\n" + "="*55)
    print("🔬 분석 3 — 공고 K-Means 클러스터링")
    print("="*55)

    df = data.get("notices", pd.DataFrame()).copy()
    if df.empty or "공고명" not in df.columns:
        print("  ℹ️  공고 데이터 없음"); return df

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        print("  ⚠️  scikit-learn 미설치"); return df

    titles  = df["공고명"].fillna("").tolist()
    n_clust = min(n_clusters, len(titles) - 1)

    # TF-IDF 벡터화
    vec   = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=2, max_features=2000)
    tfidf = vec.fit_transform(titles)

    # K-Means
    km = KMeans(n_clusters=n_clust, random_state=42, n_init=10)
    df["cluster"] = km.fit_predict(tfidf)

    # 클러스터별 대표 키워드 추출
    terms = vec.get_feature_names_out()
    cluster_labels = {}
    for i in range(n_clust):
        center   = km.cluster_centers_[i]
        top_idxs = center.argsort()[-5:][::-1]
        top_kw   = " / ".join([terms[j] for j in top_idxs if len(terms[j]) >= 2])
        cluster_labels[i] = f"C{i+1}: {top_kw}"

    df["cluster_label"] = df["cluster"].map(cluster_labels)

    # PCA 2D 시각화
    pca   = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(tfidf.toarray() if hasattr(tfidf, 'toarray') else tfidf)
    df["pca_x"] = coords[:, 0]
    df["pca_y"] = coords[:, 1]

    colors = plt.cm.tab10(np.linspace(0, 0.9, n_clust))
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # ── 패널 1: PCA 산점도 ──────────────────────────────────────────────────
    ax1 = axes[0]
    for i, (label, color) in enumerate(zip(cluster_labels.values(), colors)):
        mask = df["cluster"] == i
        ax1.scatter(df.loc[mask, "pca_x"], df.loc[mask, "pca_y"],
                    c=[color], alpha=0.6, s=40, label=label[:20])
    ax1.set_title("공고 클러스터 분포 (PCA 2D)", fontsize=13, fontweight="bold")
    ax1.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% 분산)")
    ax1.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% 분산)")
    ax1.legend(loc="upper right", fontsize=7, framealpha=0.8)
    ax1.grid(True, alpha=0.2)

    # ── 패널 2: 클러스터별 건수 + 등급 분포 ─────────────────────────────────
    ax2 = axes[1]
    grp = df.groupby("cluster").size().sort_values(ascending=False)
    bar_colors = [colors[i] for i in grp.index]
    bars = ax2.bar([cluster_labels[i][:15] for i in grp.index], grp.values, color=bar_colors, edgecolor="white")
    ax2.set_title("클러스터별 공고 수", fontsize=13, fontweight="bold")
    ax2.set_xlabel("클러스터"); ax2.set_ylabel("공고 수")
    ax2.tick_params(axis="x", rotation=25)
    for bar, val in zip(bars, grp.values):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 str(val), ha="center", fontsize=10, fontweight="bold")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.suptitle("InterX BD Intelligence — 공고 유사도 클러스터링", fontsize=16, fontweight="bold")
    plt.tight_layout()
    plt.savefig("analysis_3_clustering.png", dpi=150, bbox_inches="tight")
    plt.show()

    # 결과 요약 출력
    print("\n  [클러스터 요약]")
    for i in range(n_clust):
        mask     = df["cluster"] == i
        cnt      = mask.sum()
        l3_cnt   = (df.loc[mask, "L3강공고"] == "Y").sum() if "L3강공고" in df.columns else 0
        avg_fit  = pd.to_numeric(df.loc[mask, "적합도점수"], errors="coerce").mean() if "적합도점수" in df.columns else 0
        print(f"  {cluster_labels[i][:35]:<38} {cnt:>3}건 | L3={l3_cnt} | 평균적합도={avg_fit:.1f}")

    print(f"\n  💾 analysis_3_clustering.png 저장 완료")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 분석 4 — 수주가능성 예측 (멀티팩터 스코어링 + 피처 중요도)
# ─────────────────────────────────────────────────────────────────────────────
def analysis_win_prediction(data: dict) -> pd.DataFrame:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    print("\n" + "="*55)
    print("🎯 분석 4 — 수주가능성 예측 스코어링")
    print("="*55)

    df = data.get("notices", pd.DataFrame()).copy()
    if df.empty:
        print("  ℹ️  공고 데이터 없음"); return df

    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.preprocessing import LabelEncoder
        from sklearn.model_selection import cross_val_score
    except ImportError:
        print("  ⚠️  scikit-learn 미설치"); return df

    # ── 피처 엔지니어링 ──────────────────────────────────────────────────────
    feat = pd.DataFrame()

    # 적합도 점수 (0~100)
    feat["f_fitness"] = pd.to_numeric(df.get("적합도점수", 0), errors="coerce").fillna(0)

    # 우선순위 등급 → 수치 (A=4, B=3, C=2, D=1)
    grade_map = {"A": 4, "B": 3, "C": 2, "D": 1}
    feat["f_grade"] = df.get("우선순위등급", "D").map(grade_map).fillna(1)

    # L3 강공고 (1/0)
    feat["f_l3"] = (df.get("L3강공고", "N") == "Y").astype(int)

    # 파트너 후보 (1/0)
    feat["f_partner"] = (df.get("파트너후보", "N") == "Y").astype(int)

    # 예산 (억 단위)
    def _to_eok(s):
        m = re.search(r"([0-9.]+)억", str(s))
        return float(m.group(1)) if m else 0.0
    feat["f_budget"] = df.get("예산", "").apply(_to_eok).clip(0, 1000)

    # D-day (숫자, 상시=365)
    def _dday(s):
        s = str(s)
        if s == "상시": return 365
        try: return max(0, int(s))
        except: return 999
    feat["f_dday"] = df.get("D-day", "999").apply(_dday).clip(0, 365)

    # 마감여부 역수 (마감=0, 공개=1)
    feat["f_open"] = (df.get("마감여부", "N") != "Y").astype(int)

    # 사이트 신뢰도 가중치 (수집 품질 기반 휴리스틱)
    site_score = {
        "iris": 0.9, "kiat": 0.85, "nipa": 0.85, "innopolis": 0.8,
        "bizinfo": 0.75, "bipa": 0.7, "uipa": 0.7, "gicon": 0.65,
        "gjtp": 0.6, "gbtp": 0.6, "jntp": 0.6, "jbtp": 0.6,
        "smba": 0.8, "dicia": 0.65,
    }
    feat["f_site"] = df.get("사이트", "").map(site_score).fillna(0.5)

    # ── 수주가능성 점수 산출 (가중 합산) ─────────────────────────────────────
    weights = {
        "f_fitness": 0.30,
        "f_grade":   0.25,   # A~D
        "f_l3":      0.15,
        "f_partner": 0.10,
        "f_budget":  0.08,
        "f_open":    0.07,
        "f_site":    0.05,
    }

    # 정규화
    feat_norm = feat.copy()
    feat_norm["f_fitness"] = feat["f_fitness"] / 100
    feat_norm["f_grade"]   = feat["f_grade"]   / 4
    feat_norm["f_budget"]  = feat["f_budget"].clip(0, 50) / 50
    feat_norm["f_dday"]    = 1 - (feat["f_dday"].clip(0, 180) / 180)  # 빠를수록 높음

    score = sum(feat_norm[col] * w for col, w in weights.items())
    score = (score * 100).clip(0, 100).round(1)
    df["수주가능성"] = score

    # ── 등급 분류 ─────────────────────────────────────────────────────────
    def _win_grade(s):
        if s >= 75: return "🔥 최우선"
        if s >= 55: return "⚡ 우선"
        if s >= 35: return "📋 검토"
        return "💤 관망"
    df["수주등급"] = df["수주가능성"].apply(_win_grade)

    # ── 시각화 ────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 12))
    gs  = gridspec.GridSpec(2, 3, hspace=0.45, wspace=0.35)

    # 패널 1: 수주가능성 분포
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.hist(df["수주가능성"], bins=30, color="#1565c0", edgecolor="white", alpha=0.85)
    for thresh, color, label in [(75,"red","최우선(75+)"), (55,"orange","우선(55+)"), (35,"gold","검토(35+)")]:
        ax1.axvline(thresh, color=color, linestyle="--", linewidth=1.8, label=label)
    ax1.set_title("수주가능성 점수 분포", fontsize=13, fontweight="bold")
    ax1.set_xlabel("수주가능성 점수 (0~100)"); ax1.set_ylabel("공고 수")
    ax1.legend(fontsize=9); ax1.grid(True, alpha=0.3)

    # 패널 2: 수주등급 파이
    ax2 = fig.add_subplot(gs[0, 2])
    grade_cnt = df["수주등급"].value_counts()
    colors_pie = ["#e53935","#fb8c00","#fdd835","#90a4ae"]
    ax2.pie(grade_cnt.values, labels=grade_cnt.index, autopct="%1.1f%%",
            colors=colors_pie[:len(grade_cnt)], startangle=90,
            textprops={"fontsize": 10})
    ax2.set_title("수주등급 분포", fontsize=13, fontweight="bold")

    # 패널 3: 피처 중요도
    ax3 = fig.add_subplot(gs[1, 0])
    feat_names = {"f_fitness":"적합도점수", "f_grade":"우선순위등급", "f_l3":"L3강공고",
                  "f_partner":"파트너후보", "f_budget":"예산규모", "f_open":"공개여부", "f_site":"사이트신뢰도"}
    w_df = pd.Series({feat_names[k]: v for k, v in weights.items()}).sort_values()
    colors_bar = ["#ef9a9a" if v < 0.1 else "#1565c0" for v in w_df.values]
    w_df.plot(kind="barh", ax=ax3, color=colors_bar)
    ax3.set_title("피처 가중치 (중요도)", fontsize=12, fontweight="bold")
    ax3.set_xlabel("가중치")
    for i, v in enumerate(w_df.values):
        ax3.text(v + 0.002, i, f"{v:.0%}", va="center", fontsize=9)
    ax3.grid(True, alpha=0.3, axis="x")

    # 패널 4: 사이트별 평균 수주가능성
    ax4 = fig.add_subplot(gs[1, 1])
    if "사이트" in df.columns:
        site_win = df.groupby("사이트")["수주가능성"].mean().sort_values(ascending=True)
        colors_site = ["#1565c0" if v >= site_win.mean() else "#90caf9" for v in site_win.values]
        site_win.plot(kind="barh", ax=ax4, color=colors_site)
        ax4.axvline(site_win.mean(), color="red", linestyle="--", alpha=0.7, label=f"평균 {site_win.mean():.1f}")
        ax4.set_title("사이트별 평균 수주가능성", fontsize=12, fontweight="bold")
        ax4.set_xlabel("평균 수주가능성 점수")
        ax4.legend(fontsize=9); ax4.grid(True, alpha=0.3, axis="x")

    # 패널 5: 상위 10개 공고
    ax5 = fig.add_subplot(gs[1, 2])
    top10 = df.nlargest(10, "수주가능성")[["공고명","사이트","수주가능성","수주등급"]].reset_index(drop=True)
    ax5.axis("off")
    table_data = [[row["사이트"], row["공고명"][:18]+"…" if len(str(row["공고명"])) > 18 else row["공고명"],
                   f"{row['수주가능성']:.0f}점", row["수주등급"]]
                  for _, row in top10.iterrows()]
    tbl = ax5.table(cellText=table_data, colLabels=["사이트","공고명","점수","등급"],
                    loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.4)
    # 헤더 색상
    for j in range(4):
        tbl[0, j].set_facecolor("#1565c0")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    ax5.set_title("수주가능성 Top 10 공고", fontsize=12, fontweight="bold", pad=12)

    plt.suptitle("InterX BD Intelligence — 수주가능성 예측 분석", fontsize=16, fontweight="bold", y=1.01)
    plt.savefig("analysis_4_win_prediction.png", dpi=150, bbox_inches="tight")
    plt.show()

    # 결과 요약
    print(f"\n  [수주가능성 예측 요약]")
    print(f"  🔥 최우선 (75+점): {(df['수주등급']=='🔥 최우선').sum():>4}건")
    print(f"  ⚡ 우선   (55+점): {(df['수주등급']=='⚡ 우선').sum():>4}건")
    print(f"  📋 검토   (35+점): {(df['수주등급']=='📋 검토').sum():>4}건")
    print(f"  💤 관망   (35미만): {(df['수주등급']=='💤 관망').sum():>4}건")
    print(f"\n  [수주가능성 Top 5]")
    for _, row in df.nlargest(5, "수주가능성").iterrows():
        print(f"  {row.get('수주가능성',0):>5.1f}점  [{row.get('사이트','')}]  {str(row.get('공고명',''))[:50]}")
    print(f"\n  💾 analysis_4_win_prediction.png 저장 완료")

    return df[["공고명","사이트","적합도점수","우선순위등급","수주가능성","수주등급","상세URL"]].sort_values("수주가능성", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# 전체 실행
# ─────────────────────────────────────────────────────────────────────────────
def run_all(
    sheet_name: Optional[str] = None,
    sa_path: Optional[str] = None,
) -> dict:
    """4개 분석 전체 실행. 결과 dict 반환."""
    _project_root = Path(__file__).resolve().parents[4]
    sheet_name = sheet_name or os.getenv("INTERX_SHEET_NAME", "InterX_BD_CRM_v10_fresh_template")
    sa_path    = sa_path    or os.getenv("INTERX_SA_JSON",    str(_project_root / "service_account.json"))
    print("=" * 55)
    print("  InterX BD Intelligence — 포트폴리오 분석")
    print("=" * 55)
    print(f"  시트: {sheet_name}")
    print(f"  인증: {sa_path}")

    data    = load_data(sheet_name, sa_path)
    notices = data.get("notices", pd.DataFrame())
    print(f"\n  📦 로드 완료: 공고 {len(notices)}건\n")

    analysis_timeseries(data)
    analysis_wordcloud(data)
    clustered_df  = analysis_clustering(data)
    predicted_df  = analysis_win_prediction(data)

    print("\n" + "=" * 55)
    print("  ✅ 분석 완료 — 저장된 파일:")
    for f in ["analysis_1_timeseries.png", "analysis_2_wordcloud.png",
              "analysis_3_clustering.png",  "analysis_4_win_prediction.png"]:
        print(f"     📊 {f}")
    print("=" * 55)

    return {
        "data":         data,
        "clustered":    clustered_df,
        "predicted":    predicted_df,
    }
