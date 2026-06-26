"""
InterX Government Intelligence Dashboard
실행: streamlit run src/interx_engine/interfaces/dashboard/app.py
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
import sys as _sys
ROOT       = Path(__file__).resolve().parents[4]  # project root
_src       = str(ROOT / "src")
if _src not in _sys.path:
    _sys.path.insert(0, _src)

DB_PATH    = os.getenv("INTERX_DB_PATH", str(ROOT / "data" / "interx_engine.db"))
ATTACH_DIR = ROOT / "data" / "attachments"


# ─── 첨부파일 헬퍼 ──────────────────────────────────────────────────────────
def _attach_dir(notice_id: str) -> Path:
    d = ATTACH_DIR / _safe_id(notice_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_id(notice_id: str) -> str:
    import re
    return re.sub(r"[^\w\-]", "_", str(notice_id))[:80]


def _list_attachments(notice_id: str) -> list:
    d = ATTACH_DIR / _safe_id(notice_id)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_file())


def _attach_count(notice_id: str) -> int:
    return len(_list_attachments(notice_id))

st.set_page_config(
    page_title="InterX BD Intelligence",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    border-radius: 12px; padding: 18px 22px; color: white; margin-bottom: 8px;
}
.metric-val { font-size: 2.2rem; font-weight: 700; }
.metric-label { font-size: 0.85rem; opacity: 0.85; }
.p1-badge { background: #e53935; color: white; border-radius: 6px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }
.p2-badge { background: #fb8c00; color: white; border-radius: 6px; padding: 2px 8px; font-size: 0.75rem; font-weight: 700; }
.urgent-badge { background: #e53935; color: white; border-radius: 6px; padding: 3px 10px; font-weight: 700; animation: pulse 1.2s infinite; }
@keyframes pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.6; } }
</style>
""", unsafe_allow_html=True)


# ─── Google Sheets 공통 헬퍼 ────────────────────────────────────────────────
def _open_gsheet_client():
    """인증된 gspread 클라이언트와 시트명을 반환. 인증 실패 시 (None, None)."""
    import gspread
    from google.oauth2.service_account import Credentials
    sa_path = os.getenv("INTERX_SA_JSON", str(ROOT / "service_account.json"))
    if not Path(sa_path).exists():
        return None, None
    creds = Credentials.from_service_account_file(
        sa_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    sheet_name = os.getenv("INTERX_SHEET_NAME", "InterX_BD_CRM_v10_fresh_template")
    return gc, sheet_name


def _read_worksheet(ws_name: str) -> pd.DataFrame:
    """지정한 워크시트를 DataFrame으로 반환. 실패 시 빈 DataFrame."""
    try:
        gc, sheet_name = _open_gsheet_client()
        if gc is None:
            return pd.DataFrame()
        ws = gc.open(sheet_name).worksheet(ws_name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.warning(f"{ws_name} 읽기 오류: {e}")
        return pd.DataFrame()


# ─── 데이터 로딩 ────────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_sqlite() -> pd.DataFrame:
    if not Path(DB_PATH).exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as con:
            df = pd.read_sql(
                "SELECT * FROM notices ORDER BY deadline_date ASC", con
            )
        return df
    except Exception as e:
        st.warning(f"DB 읽기 오류: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_gsheet() -> pd.DataFrame:
    return _read_worksheet("01_영업기회_정보")


def make_demo() -> pd.DataFrame:
    """시연용 더미 데이터"""
    import random
    sites = ["bizinfo", "bipa", "uipa", "iris", "kiat", "smba", "nipa"]
    solutions = ["ManufacturingDT", "RecipeAI", "QualityAI", "InspectionAI", "SafetyAI", "GenAI", "InfraDS", "PdM"]
    grades = ["A", "A", "B", "B", "B", "C", "C", "D"]
    statuses = ["검토중", "제안완료", "수주", "탈락", "보류"]
    rows = []
    for i in range(80):
        dl = f"2026-{random.randint(4,12):02d}-{random.randint(1,28):02d}"
        try:
            d_day = (date.fromisoformat(dl) - date.today()).days
        except Exception:
            d_day = 30
        rows.append({
            "site": random.choice(sites),
            "title": f"[{random.choice(['AI','스마트','디지털','제조'])}] 2026년 {random.choice(['실증','R&D','바우처','고도화'])} 사업 공고 {i+1}",
            "deadline_date": dl,
            "d_day": d_day,
            "priority_grade": random.choice(grades),
            "fitness_score": round(random.uniform(20, 98), 1),
            "priority_score": round(random.uniform(15, 95), 1),
            "recommended_solution": random.choice(solutions),
            "l3_strong": random.choice(["Y", "Y", "N", "N", "N"]),
            "partner_candidate": random.choice(["Y", "N", "N"]),
            "ministry": random.choice(["산업통상자원부", "중소벤처기업부", "과학기술정보통신부", "고용노동부"]),
            "budget": f"{random.randint(1, 50)}억원",
            "status": random.choice(statuses),
            "business_type": random.choice(["R&D", "실증(PoC)", "바우처", "인력양성", "수요조사"]),
            "신규여부":   random.choice(["Y", "N", "N", "N"]),
            "변경여부":   random.choice(["Y", "N", "N", "N", "N"]),
            "중복의심":   random.choice(["N", "N", "N", "Y"]),
        })
    return pd.DataFrame(rows)


# ─── 컬럼 정규화 ────────────────────────────────────────────────────────────
def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """시트/DB 컬럼명 → 내부 표준명 통일"""
    rename = {
        "사이트": "site", "공고명": "title", "마감일": "deadline_date",
        "D-day": "d_day", "우선순위등급": "priority_grade",
        "적합도점수": "fitness_score", "우선순위점수": "priority_score",
        "추천솔루션": "recommended_solution", "L3강공고": "l3_strong",
        "파트너후보": "partner_candidate", "주무부처": "ministry",
        "예산": "budget", "검토상태": "status",
        "사업유형": "business_type", "상세URL": "detail_url",
        # 신규 컬럼은 한글 그대로 유지 (신규여부, 변경여부, 중복의심)
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    # d_day 계산
    if "d_day" not in df.columns and "deadline_date" in df.columns:
        def _dd(v):
            try:
                return (date.fromisoformat(str(v)[:10]) - date.today()).days
            except Exception:
                return 999
        df["d_day"] = df["deadline_date"].apply(_dd)
    for col in ["fitness_score", "priority_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ─── 사이드바 ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏭 InterX BD")
    st.title("🏭 InterX BD 인텔리전스")
    st.markdown("---")

    data_src = st.radio(
        "📡 데이터 소스",
        ["SQLite (로컬)", "Google Sheets", "데모 데이터"],
        index=0,
    )
    st.markdown("---")
    st.markdown("**필터**")
    grade_filter  = st.multiselect(
        "우선순위 등급", ["A", "B", "C", "D"], default=["A", "B"]
    )
    l3_only       = st.checkbox("L3 강공고만",   value=False)
    partner_only  = st.checkbox("파트너 후보만", value=False)
    new_only      = st.checkbox("신규 공고만",   value=False)
    days_filter   = st.slider("마감 D-day 이내", 7, 180, 90)
    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("**🤖 ML 모델 학습**")
    if st.button("🎓 수주예측 모델 학습", use_container_width=True, help="SQLite DB + CRM 메모로 LogisticRegression 학습"):
        import subprocess, sys as _sys
        _train_script = str(ROOT / "run_engine.py")
        _train_cmd = [_sys.executable, "-c",
            "import sys; sys.path.insert(0, r'" + str(ROOT / 'src') + "');"
            "from interx_engine.application.use_cases.win_prediction import WinPredictionTrainer;"
            "t = WinPredictionTrainer();"
            "r = t.train();"
            "print('OK', r)"
        ]
        with st.spinner("모델 학습 중..."):
            try:
                res = subprocess.run(_train_cmd, capture_output=True, text=True, timeout=120, cwd=str(ROOT))
                if res.returncode == 0:
                    st.success(f"✅ 학습 완료!\n{res.stdout[-500:]}")
                else:
                    err = (res.stderr or res.stdout or "")[-800:]
                    if "부족" in err or "min_samples" in err:
                        st.warning("⚠️ 학습 데이터 부족 — 파이프라인을 더 실행하거나 CRM 메모에 수주/탈락 상태를 입력하세요.")
                    else:
                        st.error(f"학습 실패:\n{err}")
            except subprocess.TimeoutExpired:
                st.error("타임아웃 (120초 초과)")
            except Exception as _te:
                st.error(f"오류: {_te}")

    st.markdown("---")
    st.markdown("**🚀 파이프라인 실행**")
    run_sites   = st.text_input("대상 사이트 (비우면 전체)", "", placeholder="예: bipa,gicon,nipa")
    run_dryrun  = st.checkbox("드라이런 (Mock 데이터)", value=False)
    run_nosheet = st.checkbox("시트 업로드 건너뜀",      value=False)

    if st.button("▶️ 실행", type="primary", use_container_width=True):
        import subprocess, sys as _sys
        cmd = [_sys.executable, str(ROOT / "run_engine.py"), "--no-alert"]
        if run_sites.strip():
            cmd += ["--sites", run_sites.strip()]
        if run_dryrun:
            cmd += ["--dry-run"]
        if run_nosheet:
            cmd += ["--no-sheets"]
        with st.spinner("파이프라인 실행 중... (수집 사이트 수에 따라 1~5분 소요)"):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=600, cwd=str(ROOT),
                )
                if result.returncode == 0:
                    st.success("✅ 파이프라인 완료! 데이터 새로고침됩니다.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("파이프라인 실패")
                    with st.expander("에러 로그"):
                        st.code((result.stderr or "")[-2000:])
            except subprocess.TimeoutExpired:
                st.error("타임아웃 (600초 초과)")
            except Exception as _e:
                st.error(f"실행 오류: {_e}")


# ─── 데이터 로드 ────────────────────────────────────────────────────────────
with st.spinner("데이터 로딩 중..."):
    if data_src == "SQLite (로컬)":
        raw = load_sqlite()
    elif data_src == "Google Sheets":
        raw = load_gsheet()
    else:
        raw = make_demo()

if raw.empty:
    st.warning("📭 수집된 데이터가 없습니다. `python run_engine.py` 를 먼저 실행해 주세요.")
    st.stop()

df = normalize(raw)

# 필터 적용
filtered = df.copy()
if grade_filter and "priority_grade" in filtered.columns:
    filtered = filtered[filtered["priority_grade"].isin(grade_filter)]
if l3_only and "l3_strong" in filtered.columns:
    filtered = filtered[filtered["l3_strong"] == "Y"]
if partner_only and "partner_candidate" in filtered.columns:
    filtered = filtered[filtered["partner_candidate"] == "Y"]
if new_only and "신규여부" in filtered.columns:
    filtered = filtered[filtered["신규여부"] == "Y"]
if "d_day" in filtered.columns:
    filtered = filtered[filtered["d_day"] <= days_filter]

# ─── 상단 메트릭 ────────────────────────────────────────────────────────────
st.markdown("## 📊 종합 현황")
c1, c2, c3, c4, c5, c6 = st.columns(6)
total        = len(df)
l3_cnt       = int((df.get("l3_strong", pd.Series()) == "Y").sum())
p1_cnt       = int((df.get("priority_grade", pd.Series()) == "A").sum())
p2_cnt       = int((df.get("priority_grade", pd.Series()) == "B").sum())
urgent_cnt   = int((df.get("d_day", pd.Series(dtype=float)) <= 7).sum()) if "d_day" in df.columns else 0
partner_cnt  = int((df.get("partner_candidate", pd.Series()) == "Y").sum())

for col, label, val, color in [
    (c1, "전체 공고",   total,       "#1e3c72"),
    (c2, "L3 강공고",   l3_cnt,      "#c62828"),
    (c3, "A 등급",      p1_cnt,      "#b71c1c"),
    (c4, "B 등급",      p2_cnt,      "#e65100"),
    (c5, "D-7 긴급",    urgent_cnt,  "#880e4f"),
    (c6, "파트너 후보", partner_cnt, "#1b5e20"),
]:
    col.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {color} 0%, #2a5298 100%)">
      <div class="metric-val">{val}</div>
      <div class="metric-label">{label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ─── 탭 ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15 = st.tabs([
    "📋 공고 목록", "📈 시각화", "🔥 A 등급 상세",
    "⚠️ 긴급 마감", "📊 수집 트렌드", "💰 예산 분석", "🏅 사이트 품질",
    "📎 사업공고 첨부", "🧠 포트폴리오 분석",
    "📝 CRM 메모", "📅 마감 캘린더", "🎯 BD 파이프라인", "📤 보고서 다운로드",
    "🤖 ML 수주예측",
])

# ══ TAB1: 공고 목록 ══════════════════════════════════════════════════════════
with tab1:
    st.markdown(f"### 필터된 공고 목록 ({len(filtered)}건)")

    display_cols = [c for c in [
        "site", "title", "deadline_date", "d_day",
        "priority_grade", "fitness_score", "recommended_solution",
        "l3_strong", "partner_candidate", "budget", "ministry",
    ] if c in filtered.columns]

    if not filtered.empty:
        col_rename = {
            "site": "사이트", "title": "공고명", "deadline_date": "마감일",
            "d_day": "D-day", "priority_grade": "등급",
            "fitness_score": "적합도", "recommended_solution": "추천솔루션",
            "l3_strong": "L3", "partner_candidate": "파트너",
            "budget": "예산", "ministry": "주무부처",
        }
        show = filtered[display_cols].rename(columns=col_rename)
        st.dataframe(
            show,
            use_container_width=True,
            height=450,
            column_config={
                "D-day": st.column_config.NumberColumn(format="%d일"),
                "적합도": st.column_config.ProgressColumn(min_value=0, max_value=100),
                "등급": st.column_config.TextColumn(width="small"),
            },
        )

        # 엑셀 다운로드
        @st.cache_data
        def to_excel(d: pd.DataFrame) -> bytes:
            from io import BytesIO
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                d.to_excel(w, index=False)
            return buf.getvalue()

        st.download_button(
            "📥 엑셀 다운로드",
            data=to_excel(filtered),
            file_name=f"interx_notices_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ══ TAB2: 시각화 ═════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📈 데이터 시각화")
    row1_l, row1_r = st.columns(2)

    # 사이트별 원형 차트
    with row1_l:
        if "site" in df.columns:
            site_cnt = df["site"].value_counts().reset_index()
            site_cnt.columns = ["사이트", "건수"]
            fig = px.pie(
                site_cnt, values="건수", names="사이트",
                title="📡 사이트별 공고 분포",
                color_discrete_sequence=px.colors.qualitative.Set3,
                hole=0.35,
            )
            fig.update_traces(textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    # 등급별 막대 차트
    with row1_r:
        if "priority_grade" in df.columns:
            grade_cnt = df["priority_grade"].value_counts().reset_index()
            grade_cnt.columns = ["등급", "건수"]
            color_map = {"A": "#e53935", "B": "#fb8c00", "C": "#fdd835", "D": "#81c784"}
            fig2 = px.bar(
                grade_cnt, x="등급", y="건수",
                title="🏆 우선순위 등급 분포",
                color="등급", color_discrete_map=color_map,
                text="건수",
            )
            fig2.update_traces(textposition="outside")
            st.plotly_chart(fig2, use_container_width=True)

    row2_l, row2_r = st.columns(2)

    # 적합도 히스토그램
    with row2_l:
        if "fitness_score" in df.columns:
            fig3 = px.histogram(
                df, x="fitness_score", nbins=20,
                title="📊 적합도 점수 분포",
                color_discrete_sequence=["#1565c0"],
                labels={"fitness_score": "적합도 점수"},
            )
            fig3.add_vline(x=74, line_dash="dash", line_color="red", annotation_text="L3 임계값(74)")
            st.plotly_chart(fig3, use_container_width=True)

    # 사업유형 파이 차트
    with row2_r:
        if "business_type" in df.columns:
            btype_cnt = df["business_type"].value_counts().nlargest(8).reset_index()
            btype_cnt.columns = ["사업유형", "건수"]
            fig4 = px.pie(
                btype_cnt, values="건수", names="사업유형",
                title="📁 사업유형별 분포",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            st.plotly_chart(fig4, use_container_width=True)

    # 솔루션별 집계 막대
    if "recommended_solution" in df.columns:
        sol_series = df["recommended_solution"].dropna()
        sol_flat   = []
        for s in sol_series:
            sol_flat.extend([x.strip() for x in str(s).split("/") if x.strip() and x.strip() != "-"])
        if sol_flat:
            sol_df = pd.Series(sol_flat).value_counts().reset_index()
            sol_df.columns = ["솔루션", "건수"]
            fig5 = px.bar(
                sol_df, x="솔루션", y="건수",
                title="🔧 추천 솔루션별 공고 수",
                color="건수",
                color_continuous_scale="Blues",
                text="건수",
            )
            fig5.update_traces(textposition="outside")
            st.plotly_chart(fig5, use_container_width=True)

    # D-day 분포
    if "d_day" in df.columns:
        dday_df = df[df["d_day"].between(-30, 180)].copy()
        if not dday_df.empty:
            fig6 = px.histogram(
                dday_df, x="d_day", nbins=30,
                title="📅 마감 D-day 분포",
                labels={"d_day": "남은 일수"},
                color_discrete_sequence=["#2a5298"],
            )
            fig6.add_vline(x=7, line_dash="dash", line_color="red", annotation_text="7일 긴급")
            fig6.add_vline(x=30, line_dash="dash", line_color="orange", annotation_text="30일")
            st.plotly_chart(fig6, use_container_width=True)


# ══ TAB4: P1 상세 ════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🔥 A 등급 공고 상세")
    p1_df = df[df.get("priority_grade", pd.Series()) == "A"] if "priority_grade" in df.columns else pd.DataFrame()

    if p1_df.empty:
        st.info("A 등급 공고가 없습니다.")
    else:
        for _, row in p1_df.iterrows():
            title    = row.get("title", "")
            site     = row.get("site", "")
            deadline = row.get("deadline_date", "")
            d_day    = row.get("d_day", "?")
            fit      = row.get("fitness_score", 0)
            sol      = row.get("recommended_solution", "-")
            budget   = row.get("budget", "-")
            url      = row.get("detail_url", row.get("notice_link", ""))

            nid_a      = str(row.get("notice_id", row.get("공고ID", "")))
            atc_a      = _attach_count(nid_a)
            urgency    = "🚨" if (isinstance(d_day, (int, float)) and d_day <= 7) else "⚡"
            atc_badge  = f"  📎{atc_a}" if atc_a else ""
            with st.expander(f"{urgency} [{site}] {title[:55]}{'…' if len(str(title)) > 55 else ''}{atc_badge}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("마감일", deadline)
                c2.metric("D-day", f"{d_day}일" if isinstance(d_day, (int, float)) else d_day)
                c3.metric("적합도", f"{fit:.0f}점")
                st.markdown(f"**추천 솔루션:** {sol}")
                st.markdown(f"**예산:** {budget}")
                if url:
                    st.markdown(f"🔗 [공고 바로가기]({url})")
                # 첨부파일 미리보기
                existing_a = _list_attachments(nid_a) if nid_a else []
                if existing_a:
                    st.markdown(f"**📎 첨부파일 ({len(existing_a)}개)**")
                    for fp in existing_a:
                        with open(fp, "rb") as _fh:
                            st.download_button(
                                f"⬇️ {fp.name}",
                                data=_fh.read(),
                                file_name=fp.name,
                                key=f"a4dl_{nid_a}_{fp.name}",
                            )


# ══ TAB5: 긴급 마감 ══════════════════════════════════════════════════════════
with tab5:
    st.markdown("### ⚠️ D-7 이내 긴급 마감 공고")
    if "d_day" not in df.columns:
        st.info("마감일 데이터가 없습니다.")
    else:
        urgent = df[df["d_day"] <= 7].sort_values("d_day") if "d_day" in df.columns else pd.DataFrame()
        if urgent.empty:
            st.success("✅ 7일 이내 긴급 공고가 없습니다.")
        else:
            for _, row in urgent.iterrows():
                d_day = row.get("d_day", 0)
                title = row.get("title", "")
                site  = row.get("site", "")
                grade = row.get("priority_grade", "?")
                url   = row.get("detail_url", row.get("notice_link", ""))
                color = "#e53935" if d_day <= 3 else "#fb8c00"
                badge = f'<span class="urgent-badge" style="background:{color}">D-{d_day}</span>'
                grade_badge = f'<span class="p1-badge">{grade}</span>' if grade == "A" else f'<span class="p2-badge">{grade}</span>'
                st.markdown(
                    f"{badge} &nbsp; {grade_badge} &nbsp; **[{site}]** {title[:70]}"
                    + (f" &nbsp; [🔗]({url})" if url else ""),
                    unsafe_allow_html=True,
                )
            st.markdown(f"\n총 **{len(urgent)}건** 긴급 마감 공고")

# ══ TAB6: 수집 트렌드 ════════════════════════════════════════════════════════
with tab6:
    st.markdown("### 📊 수집 트렌드 (93_사이트별수집통계)")

    @st.cache_data(ttl=300)
    def load_site_stats() -> pd.DataFrame:
        return _read_worksheet("93_사이트별수집통계")

    @st.cache_data(ttl=300)
    def load_kpi() -> pd.DataFrame:
        return _read_worksheet("22_KPI현황")

    stats_df = load_site_stats()
    kpi_df   = load_kpi()

    if stats_df.empty and kpi_df.empty:
        st.info("데이터 없음 — 왼쪽 소스를 'Google Sheets'로 선택하거나 run_engine.py를 실행하세요.")
    else:
        if not stats_df.empty:
            stats_df["기준일"] = pd.to_datetime(stats_df["기준일"], errors="coerce")
            for col in ["수집건수","L3건수","A건수","B건수","마감임박건수"]:
                if col in stats_df.columns:
                    stats_df[col] = pd.to_numeric(stats_df[col], errors="coerce").fillna(0)

            # 날짜별 전체 수집건수 트렌드
            daily = stats_df.groupby("기준일")["수집건수"].sum().reset_index()
            if not daily.empty:
                fig_trend = px.line(daily, x="기준일", y="수집건수",
                                    title="📈 일별 전체 수집 건수 트렌드",
                                    markers=True, line_shape="spline")
                fig_trend.update_traces(line_color="#1565c0")
                st.plotly_chart(fig_trend, use_container_width=True)

            # 사이트별 최근 수집 현황 (최신 실행 기준)
            latest_exec = stats_df["실행ID"].iloc[-1] if "실행ID" in stats_df.columns else None
            if latest_exec:
                latest_df = stats_df[stats_df["실행ID"] == latest_exec]
                if not latest_df.empty:
                    c1, c2 = st.columns(2)
                    with c1:
                        fig_site = px.bar(latest_df.sort_values("수집건수", ascending=False),
                                          x="사이트", y="수집건수",
                                          title=f"최근 실행 사이트별 수집 건수 ({latest_exec})",
                                          color="수집건수", color_continuous_scale="Blues", text="수집건수")
                        fig_site.update_traces(textposition="outside")
                        st.plotly_chart(fig_site, use_container_width=True)
                    with c2:
                        melt_cols = [c for c in ["L3건수","A건수","B건수","마감임박건수"] if c in latest_df.columns]
                        if melt_cols:
                            melt_df = latest_df.melt(id_vars=["사이트"], value_vars=melt_cols,
                                                      var_name="구분", value_name="건수")
                            fig_stack = px.bar(melt_df, x="사이트", y="건수", color="구분",
                                               title="사이트별 품질 지표", barmode="stack")
                            st.plotly_chart(fig_stack, use_container_width=True)

        if not kpi_df.empty:
            st.markdown("#### KPI 현황 누적")
            # 전체공고수 트렌드
            total_kpi = kpi_df[(kpi_df.get("구분","") == "수집현황") &
                                (kpi_df.get("지표","") == "전체공고수")] if "구분" in kpi_df.columns else pd.DataFrame()
            if not total_kpi.empty:
                total_kpi = total_kpi.copy()
                total_kpi["값"] = pd.to_numeric(total_kpi["값"], errors="coerce")
                fig_kpi = px.bar(total_kpi, x="기준일", y="값",
                                 title="날짜별 전체공고수 KPI", color_discrete_sequence=["#1565c0"])
                st.plotly_chart(fig_kpi, use_container_width=True)

            # 원본 테이블
            with st.expander("KPI 원본 데이터 보기"):
                st.dataframe(kpi_df, use_container_width=True)


# ══ TAB7: 예산 분석 ══════════════════════════════════════════════════════════
with tab7:
    st.markdown("### 💰 예산 규모 분석")
    st.caption("공고의 예산 정보를 파싱해 규모별 분포·합계·솔루션 매핑을 제공합니다.")

    import re as _re

    def _parse_budget_num(val: str) -> float:
        """'30억원', '500백만원', '1,200백만' 등 → 억 단위 float."""
        if not val or str(val).strip() in ("-", "", "nan"):
            return 0.0
        s = str(val).replace(",", "").replace(" ", "")
        m_eok = _re.search(r"([\d.]+)\s*억", s)
        m_baek = _re.search(r"([\d.]+)\s*백만", s)
        m_man  = _re.search(r"([\d.]+)\s*만", s)
        if m_eok:
            return float(m_eok.group(1))
        if m_baek:
            return round(float(m_baek.group(1)) / 100, 2)
        if m_man:
            return round(float(m_man.group(1)) / 10000, 4)
        bare = _re.search(r"([\d.]+)", s)
        if bare:
            v = float(bare.group(1))
            return v if v < 10000 else round(v / 100_000_000, 2)
        return 0.0

    bud_col = next((c for c in ["budget", "예산"] if c in df.columns), None)

    if bud_col is None:
        st.info("예산 컬럼이 없습니다. 파이프라인을 실행하거나 데모 데이터를 사용해 보세요.")
    else:
        bud_df = df.copy()
        bud_df["_eok"] = bud_df[bud_col].apply(_parse_budget_num)
        bud_filled = bud_df[bud_df["_eok"] > 0].copy()

        # ── 요약 메트릭 ───────────────────────────────────────────────────
        total_eok = bud_filled["_eok"].sum()
        avg_eok   = bud_filled["_eok"].mean() if not bud_filled.empty else 0
        filled_rt = len(bud_filled) / len(bud_df) * 100 if len(bud_df) else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("예산 정보 공고",     f"{len(bud_filled)}건")
        m2.metric("총 예산 규모 추정",  f"{total_eok:,.1f}억원")
        m3.metric("평균 사업 예산",     f"{avg_eok:,.1f}억원")
        m4.metric("예산 기재율",        f"{filled_rt:.1f}%")

        st.markdown("---")

        if bud_filled.empty:
            st.info("파싱 가능한 예산 정보가 없습니다.")
        else:
            # ── 규모별 버킷 ───────────────────────────────────────────────
            def _bucket(v: float) -> str:
                if v <= 0:    return "미기재"
                if v < 1:     return "1억 미만"
                if v < 5:     return "1~5억"
                if v < 10:    return "5~10억"
                if v < 30:    return "10~30억"
                if v < 100:   return "30~100억"
                return "100억+"

            bud_filled["규모"] = bud_filled["_eok"].apply(_bucket)
            bucket_order = ["1억 미만","1~5억","5~10억","10~30억","30~100억","100억+"]

            col_l, col_r = st.columns(2)
            with col_l:
                bc = bud_filled["규모"].value_counts().reindex(bucket_order).dropna().reset_index()
                bc.columns = ["규모", "건수"]
                fig_b = px.bar(bc, x="규모", y="건수",
                               title="예산 규모별 공고 건수",
                               color="규모",
                               color_discrete_sequence=px.colors.sequential.Blues_r,
                               text="건수")
                fig_b.update_traces(textposition="outside")
                st.plotly_chart(fig_b, use_container_width=True)

            with col_r:
                # 규모별 총 예산 합계
                eok_sum = bud_filled.groupby("규모")["_eok"].sum().reindex(bucket_order).dropna().reset_index()
                eok_sum.columns = ["규모", "합계(억원)"]
                fig_s = px.bar(eok_sum, x="규모", y="합계(억원)",
                               title="규모별 총 예산 합계",
                               color="합계(억원)",
                               color_continuous_scale="Oranges",
                               text="합계(억원)")
                fig_s.update_traces(texttemplate="%{text:.1f}억", textposition="outside")
                st.plotly_chart(fig_s, use_container_width=True)

            # ── 솔루션 × 예산 버블 차트 ──────────────────────────────────
            if "recommended_solution" in bud_filled.columns:
                sol_bud = (bud_filled.groupby("recommended_solution")
                           .agg(건수=("_eok", "count"), 총예산=("_eok", "sum"),
                                평균예산=("_eok", "mean"))
                           .reset_index())
                sol_bud = sol_bud[sol_bud["recommended_solution"].notna() &
                                  (sol_bud["recommended_solution"] != "-") &
                                  (sol_bud["recommended_solution"] != "")]
                if not sol_bud.empty:
                    fig_bub = px.scatter(
                        sol_bud, x="건수", y="평균예산",
                        size="총예산", color="recommended_solution",
                        hover_name="recommended_solution",
                        title="솔루션별 건수 × 평균예산 (버블=총예산)",
                        labels={"건수": "공고 건수", "평균예산": "평균 예산(억원)"},
                    )
                    st.plotly_chart(fig_bub, use_container_width=True)

            # ── 상세 테이블 ───────────────────────────────────────────────
            with st.expander("예산 원본 데이터 보기"):
                show_b = [c for c in ["site","title",bud_col,"_eok","priority_grade","규모"]
                          if c in bud_filled.columns]
                st.dataframe(
                    bud_filled[show_b].rename(columns={"_eok":"억원(환산)"})
                    .sort_values("억원(환산)", ascending=False),
                    use_container_width=True, height=350,
                )


# ══ TAB8: 사이트 품질 등급 ═══════════════════════════════════════════════════
with tab8:
    st.markdown("### 🏅 사이트별 수집 품질 등급")
    st.caption("평가 기준: L3전환율(30%) + AB등급비율(25%) + 예산정보율(20%) + 마감일정보율(15%) + 수집건수(10%)")

    if "site" not in df.columns:
        st.info("사이트 정보가 없습니다.")
    else:
        # 사이트별 품질 지표 계산
        quality_rows = []
        for site, grp in df.groupby("site"):
            total  = len(grp)
            l3     = int((grp.get("l3_strong", pd.Series()) == "Y").sum())
            p1p2   = int(grp.get("priority_grade", pd.Series()).isin(["A","B"]).sum())
            budget_filled  = int((grp.get("예산",   pd.Series()).notna() & (grp.get("예산",   pd.Series()) != "") & (grp.get("예산",   pd.Series()) != "-")).sum()) if "예산"   in grp.columns else 0
            dl_filled      = int((grp.get("deadline_date", pd.Series()).notna() & (grp.get("deadline_date", pd.Series()) != "")).sum()) if "deadline_date" in grp.columns else 0

            l3_r    = l3    / total if total else 0
            p1p2_r  = p1p2  / total if total else 0
            bud_r   = budget_filled / total if total else 0
            dl_r    = dl_filled     / total if total else 0
            vol_r   = min(total, 50) / 50

            score = (l3_r*30 + p1p2_r*25 + bud_r*20 + dl_r*15 + vol_r*10) * 100

            if   score >= 70: grade = "A"
            elif score >= 50: grade = "B"
            elif score >= 30: grade = "C"
            elif score >= 10: grade = "D"
            else:             grade = "F"

            quality_rows.append({
                "사이트":     site,
                "등급":       grade,
                "품질점수":   round(score, 1),
                "수집건수":   total,
                "L3율(%)":   round(l3_r   * 100, 1),
                "AB등급율(%)": round(p1p2_r * 100, 1),
                "예산정보율(%)": round(bud_r  * 100, 1),
                "마감일정보율(%)": round(dl_r * 100, 1),
            })

        q_df = pd.DataFrame(quality_rows).sort_values("품질점수", ascending=False)

        grade_color = {"A": "#2e7d32", "B": "#1565c0", "C": "#f9a825", "D": "#e65100", "F": "#b71c1c"}

        # 등급 요약 배지
        badge_cols = st.columns(len(q_df) if len(q_df) <= 8 else 8)
        for i, (_, row) in enumerate(q_df.iterrows()):
            if i >= 8:
                break
            gc = grade_color.get(row["등급"], "#555")
            badge_cols[i].markdown(
                f"<div style='background:{gc};color:white;border-radius:10px;"
                f"padding:10px;text-align:center'>"
                f"<b>{row['사이트']}</b><br/>"
                f"<span style='font-size:1.6rem;font-weight:700'>{row['등급']}</span><br/>"
                f"<small>{row['품질점수']}점</small></div>",
                unsafe_allow_html=True,
            )

        st.markdown("")

        # 품질 점수 막대 차트
        col_chart, col_radar = st.columns(2)
        with col_chart:
            fig_q = px.bar(
                q_df, x="사이트", y="품질점수",
                title="사이트별 품질 점수",
                color="등급",
                color_discrete_map=grade_color,
                text="품질점수",
            )
            fig_q.update_traces(textposition="outside")
            fig_q.add_hline(y=70, line_dash="dash", line_color="#2e7d32", annotation_text="A등급(70)")
            fig_q.add_hline(y=50, line_dash="dash", line_color="#1565c0", annotation_text="B등급(50)")
            fig_q.add_hline(y=30, line_dash="dash", line_color="#f9a825", annotation_text="C등급(30)")
            st.plotly_chart(fig_q, use_container_width=True)

        with col_radar:
            # 상위 5개 사이트 레이더 차트
            top5 = q_df.head(5)
            radar_cats = ["L3율(%)", "AB등급율(%)", "예산정보율(%)", "마감일정보율(%)"]
            radar_cats_closed = radar_cats + [radar_cats[0]]
            fig_radar = go.Figure()
            for _, row in top5.iterrows():
                vals = [row[c] for c in radar_cats]
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]], theta=radar_cats_closed,
                    fill="toself", name=row["사이트"],
                ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(range=[0, 100])),
                title="Top5 사이트 품질 레이더",
                showlegend=True,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # 상세 테이블
        st.markdown("#### 상세 품질 지표 테이블")
        st.dataframe(
            q_df,
            use_container_width=True,
            column_config={
                "품질점수":       st.column_config.ProgressColumn(min_value=0, max_value=100),
                "L3율(%)":       st.column_config.NumberColumn(format="%.1f%%"),
                "AB등급율(%)":   st.column_config.NumberColumn(format="%.1f%%"),
                "예산정보율(%)":  st.column_config.NumberColumn(format="%.1f%%"),
                "마감일정보율(%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

        # 개선 가이드
        low_sites = q_df[q_df["등급"].isin(["D", "F"])]
        if not low_sites.empty:
            st.warning(f"⚠️ 품질 D/F 사이트: **{', '.join(low_sites['사이트'].tolist())}** — 콜렉터 점검 필요")


# ══ TAB9: 사업공고 첨부파일 ═══════════════════════════════════════════════════
with tab9:
    st.markdown("### 📎 사업공고 파일 첨부 관리")
    st.caption("A/B 등급 공고에 사업공고문·RFP·첨부파일을 업로드해 보관합니다.")

    _ALLOWED_EXT = ["pdf", "hwp", "hwpx", "docx", "xlsx", "pptx", "zip", "png", "jpg", "jpeg"]

    # 대상: A/B 등급 전체 (필터 무관)
    attach_target = df[df.get("priority_grade", pd.Series()).isin(["A", "B"])].copy() \
        if "priority_grade" in df.columns else pd.DataFrame()

    if attach_target.empty:
        st.info("A/B 등급 공고가 없습니다. 파이프라인을 실행하거나 필터를 조정하세요.")
    else:
        # 검색창
        search_q = st.text_input("🔍 공고명 검색", "", placeholder="키워드 입력...")
        if search_q.strip() and "title" in attach_target.columns:
            attach_target = attach_target[
                attach_target["title"].str.contains(search_q.strip(), case=False, na=False)
            ]

        # 등급 순 정렬 (A 우선)
        grade_order = {"A": 0, "B": 1}
        if "priority_grade" in attach_target.columns:
            attach_target = attach_target.copy()
            attach_target["_grade_ord"] = attach_target["priority_grade"].map(grade_order).fillna(9)
            attach_target = attach_target.sort_values(["_grade_ord", "fitness_score"],
                                                       ascending=[True, False])

        st.markdown(f"**{len(attach_target)}건** 표시 중")

        for _, row in attach_target.iterrows():
            nid      = str(row.get("notice_id", row.get("공고ID", "")))
            title    = str(row.get("title", row.get("공고명", "제목 없음")))
            site     = str(row.get("site",  row.get("사이트", "")))
            grade    = str(row.get("priority_grade", row.get("우선순위등급", "?")))
            deadline = str(row.get("deadline_date", row.get("마감일", "")))
            url      = str(row.get("detail_url", row.get("상세URL", "")))
            fit      = row.get("fitness_score", row.get("적합도점수", 0))

            existing   = _list_attachments(nid) if nid else []
            attach_cnt = len(existing)
            badge_color = "#b71c1c" if grade == "A" else "#1565c0"
            expander_label = (
                f"[{grade}] [{site}] {title[:55]}{'…' if len(title) > 55 else ''}"
                + (f"  📎{attach_cnt}" if attach_cnt else "")
            )

            with st.expander(expander_label):
                info_c1, info_c2, info_c3 = st.columns(3)
                info_c1.markdown(
                    f"<span style='background:{badge_color};color:white;"
                    f"border-radius:5px;padding:2px 8px;font-weight:700'>{grade}</span>",
                    unsafe_allow_html=True,
                )
                info_c2.markdown(f"**마감** {deadline}")
                info_c3.markdown(f"**적합도** {fit:.0f}점")
                if url and url != "nan":
                    st.markdown(f"🔗 [원본 공고 바로가기]({url})")

                st.markdown("---")

                # ── 기존 첨부파일 표시 ────────────────────────────────────
                if existing:
                    st.markdown(f"**첨부된 파일 ({attach_cnt}개)**")
                    for fp in existing:
                        fc1, fc2, fc3 = st.columns([5, 1, 1])
                        fc1.markdown(f"📄 `{fp.name}`  ({fp.stat().st_size // 1024} KB)")
                        with open(fp, "rb") as _fh:
                            fc2.download_button(
                                "⬇️",
                                data=_fh.read(),
                                file_name=fp.name,
                                key=f"dl_{nid}_{fp.name}",
                            )
                        if fc3.button("🗑️", key=f"del_{nid}_{fp.name}",
                                      help=f"{fp.name} 삭제"):
                            fp.unlink(missing_ok=True)
                            st.rerun()
                else:
                    st.markdown("*첨부된 파일 없음*")

                st.markdown("")

                # ── 파일 업로드 ───────────────────────────────────────────
                uploaded_files = st.file_uploader(
                    "파일 첨부 (복수 선택 가능)",
                    accept_multiple_files=True,
                    type=_ALLOWED_EXT,
                    key=f"up_{nid}",
                    help=f"지원 형식: {', '.join(_ALLOWED_EXT)}",
                )
                if uploaded_files and nid:
                    save_dir = _attach_dir(nid)
                    saved = []
                    for uf in uploaded_files:
                        dest = save_dir / uf.name
                        dest.write_bytes(uf.getvalue())
                        saved.append(uf.name)
                    if saved:
                        st.success(f"✅ 저장 완료: {', '.join(saved)}")
                        st.rerun()

    # ── 전체 첨부파일 현황 요약 ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 첨부파일 현황 요약")
    if ATTACH_DIR.exists():
        summary = []
        for d in sorted(ATTACH_DIR.iterdir()):
            if d.is_dir():
                files = [f for f in d.iterdir() if f.is_file()]
                if files:
                    total_kb = sum(f.stat().st_size for f in files) // 1024
                    summary.append({
                        "공고ID":    d.name,
                        "파일 수":   len(files),
                        "용량(KB)":  total_kb,
                        "파일목록":  ", ".join(f.name for f in files[:3])
                                     + ("..." if len(files) > 3 else ""),
                    })
        if summary:
            st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
        else:
            st.info("아직 첨부된 파일이 없습니다.")
    else:
        st.info("아직 첨부된 파일이 없습니다.")


# ─── 분석 대시보드 탭 ─────────────────────────────────────────────────────
def _render_analysis_tab():
    st.markdown("## 📊 포트폴리오 분석 & 수주 예측")

    # DB에서 공고 로드
    try:
        conn = sqlite3.connect(DB_PATH)
        notices_df = pd.read_sql("SELECT * FROM notices ORDER BY posted_date DESC LIMIT 500",
                                 conn, params=[])
        conn.close()
    except Exception:
        notices_df = pd.DataFrame()

    if notices_df.empty:
        st.info("분석할 데이터가 없습니다. 먼저 파이프라인을 실행하세요.")
        return

    # ── 월별 트렌드 ──────────────────────────────────────────────────────────
    st.markdown("### 📈 월별 수집 트렌드")
    if "posted_date" in notices_df.columns:
        notices_df["월"] = notices_df["posted_date"].str[:7]
        trend = notices_df.groupby("월").size().reset_index(name="건수")
        if not trend.empty:
            fig = px.bar(trend, x="월", y="건수", color_discrete_sequence=["#2a5298"],
                         title="월별 공고 수집 건수")
            st.plotly_chart(fig, use_container_width=True)

    # ── 부처별 비중 ──────────────────────────────────────────────────────────
    st.markdown("### 🏛️ 부처별 공고 비중")
    if "ministry" in notices_df.columns:
        ministry_cnt = (notices_df["ministry"].fillna("미분류")
                        .value_counts().head(10).reset_index())
        ministry_cnt.columns = ["부처", "건수"]
        fig2 = px.pie(ministry_cnt, names="부처", values="건수",
                      title="부처별 공고 분포", hole=0.35)
        st.plotly_chart(fig2, use_container_width=True)

    # ── 수주 예측 섹션 ───────────────────────────────────────────────────────
    st.markdown("### 🎯 수주 가능성 예측 (Rule-based v1)")
    st.caption("fitness_score · priority_score · 예산 · D-day · L3여부 · industry_score 가중합 모델")

    if "fitness_score" in notices_df.columns:
        pred_df = notices_df[["notice_id", "site", "title",
                               "fitness_score", "priority_score",
                               "budget", "deadline_date", "l3_strong",
                               "industry_score"]].dropna(subset=["fitness_score"])

        if not pred_df.empty:
            # 간이 수주확률 계산 (WinPredictionUseCase 없이 직접)
            pred_df = pred_df.copy()
            pred_df["수주확률"] = (
                pred_df["fitness_score"].clip(0, 100) * 0.35 / 100 +
                pred_df.get("priority_score", pd.Series(50, index=pred_df.index)).clip(0, 100) * 0.25 / 100 +
                (pred_df["l3_strong"] == "Y").astype(float) * 0.10
            ).round(3)
            pred_df["등급"] = pred_df["수주확률"].apply(
                lambda p: "A" if p >= 0.75 else ("B" if p >= 0.55 else ("C" if p >= 0.35 else "D"))
            )

            col1, col2, col3, col4 = st.columns(4)
            for col, grade, color in [
                (col1, "A", "#e53935"), (col2, "B", "#fb8c00"),
                (col3, "C", "#43a047"), (col4, "D", "#757575"),
            ]:
                cnt = (pred_df["등급"] == grade).sum()
                col.metric(f"{grade}등급", f"{cnt}건")

            fig3 = px.histogram(pred_df, x="수주확률", nbins=20,
                                 color_discrete_sequence=["#1e3c72"],
                                 title="수주확률 분포")
            st.plotly_chart(fig3, use_container_width=True)

            top5 = pred_df.nlargest(5, "수주확률")[["title", "수주확률", "등급", "site"]]
            st.markdown("#### Top 5 수주 기회")
            st.dataframe(top5, use_container_width=True, hide_index=True)


# ══ TAB10: 포트폴리오 분석 ═══════════════════════════════════════════════════
with tab10:
    try:
        _render_analysis_tab()
    except Exception as _e:
        st.error(f"분석 탭 로드 실패: {_e}")


# ══ TAB11: CRM 메모 ═══════════════════════════════════════════════════════════
_MEMO_FILE = ROOT / "data" / "crm_memos.json"

def _load_memos() -> dict:
    try:
        if _MEMO_FILE.exists():
            import json
            return json.loads(_MEMO_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_memos(memos: dict) -> None:
    import json
    _MEMO_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MEMO_FILE.write_text(json.dumps(memos, ensure_ascii=False, indent=2), encoding="utf-8")

with tab11:
    st.markdown("### 📝 CRM 메모 & 액션 아이템")
    st.caption("공고별 영업 노트, 다음 액션, 담당 메모를 로컬에 저장합니다.")

    memos = _load_memos()

    # 대상 공고: A/B 등급 또는 전체 filtered
    memo_target = df[df.get("priority_grade", pd.Series()).isin(["A","B","C"])].copy() \
        if "priority_grade" in df.columns else filtered.copy()
    memo_target = memo_target.head(50)  # 성능상 50건 제한

    if memo_target.empty:
        st.info("대상 공고가 없습니다.")
    else:
        # 검색
        memo_search = st.text_input("🔍 공고 검색", "", key="memo_search")
        if memo_search.strip() and "title" in memo_target.columns:
            memo_target = memo_target[
                memo_target["title"].str.contains(memo_search.strip(), case=False, na=False)
            ]

        # 메모 있는 공고 먼저 표시
        memo_target = memo_target.copy()
        memo_target["_has_memo"] = memo_target.apply(
            lambda r: bool(memos.get(str(r.get("notice_id", r.get("title", ""))))), axis=1
        )
        memo_target = memo_target.sort_values(["_has_memo", "fitness_score"], ascending=[False, False])

        for _, row in memo_target.iterrows():
            nid     = str(row.get("notice_id", row.get("title", "unknown")))
            title   = str(row.get("title", "제목 없음"))
            grade   = str(row.get("priority_grade", "?"))
            site    = str(row.get("site", ""))
            existing_memo = memos.get(nid, {})
            has_m   = bool(existing_memo)
            label   = f"{'✏️' if has_m else '📌'} [{grade}][{site}] {title[:55]}{'…' if len(title)>55 else ''}"

            with st.expander(label, expanded=False):
                cur_note   = existing_memo.get("note", "")
                cur_action = existing_memo.get("action", "")
                cur_status = existing_memo.get("status", "검토중")

                c1, c2 = st.columns([3, 1])
                new_note = c1.text_area(
                    "영업 노트", value=cur_note,
                    key=f"note_{nid}", height=100,
                    placeholder="고객사 반응, 경쟁 상황, 특이사항 등..."
                )
                new_action = c1.text_input(
                    "다음 액션", value=cur_action,
                    key=f"act_{nid}",
                    placeholder="예: 2026-05-03 RFP 확인"
                )
                status_opts = ["검토중", "제안준비", "제안완료", "수주", "탈락", "보류"]
                cur_idx = status_opts.index(cur_status) if cur_status in status_opts else 0
                new_status = c2.selectbox("진행 상태", status_opts, index=cur_idx, key=f"st_{nid}")

                col_save, col_del = c2.columns(2)
                if col_save.button("💾", key=f"save_{nid}", help="저장"):
                    memos[nid] = {"note": new_note, "action": new_action, "status": new_status,
                                  "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
                    _save_memos(memos)
                    st.success("저장됨")
                    st.rerun()
                if has_m and col_del.button("🗑️", key=f"del_m_{nid}", help="삭제"):
                    memos.pop(nid, None)
                    _save_memos(memos)
                    st.rerun()

                if existing_memo.get("updated"):
                    st.caption(f"최종 수정: {existing_memo['updated']}")

    # 전체 메모 요약 테이블
    if memos:
        st.markdown("---")
        st.markdown("#### 📋 전체 메모 현황")
        memo_rows = [{"공고ID": k, **v} for k, v in memos.items()]
        memo_sum_df = pd.DataFrame(memo_rows)
        st.dataframe(memo_sum_df, use_container_width=True, hide_index=True)

        # 메모 Excel 다운로드
        from io import BytesIO as _BytesIO
        _buf = _BytesIO()
        with pd.ExcelWriter(_buf, engine="openpyxl") as _w:
            memo_sum_df.to_excel(_w, index=False, sheet_name="CRM메모")
        st.download_button(
            "📥 메모 엑셀 다운로드", data=_buf.getvalue(),
            file_name=f"crm_memos_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ══ TAB12: 마감 캘린더 ════════════════════════════════════════════════════════
with tab12:
    st.markdown("### 📅 마감 캘린더 (주차별)")
    st.caption("앞으로 90일 내 마감 공고를 주차별로 시각화합니다.")

    if "deadline_date" not in df.columns or "d_day" not in df.columns:
        st.info("마감일 데이터가 없습니다.")
    else:
        cal_df = df[df["d_day"].between(0, 90)].copy()
        if cal_df.empty:
            st.success("90일 이내 마감 공고가 없습니다.")
        else:
            cal_df["_dl"] = pd.to_datetime(cal_df["deadline_date"], errors="coerce")
            cal_df = cal_df.dropna(subset=["_dl"])
            cal_df["주차"] = cal_df["_dl"].dt.to_period("W").astype(str)

            grade_color_map = {"A": "#e53935", "B": "#fb8c00", "C": "#fdd835", "D": "#bdbdbd"}

            # 주차별 타임라인 bar
            week_grp = cal_df.groupby(["주차", "priority_grade"]).size().reset_index(name="건수")
            if not week_grp.empty and "priority_grade" in week_grp.columns:
                fig_cal = px.bar(
                    week_grp, x="주차", y="건수", color="priority_grade",
                    color_discrete_map=grade_color_map,
                    title="주차별 마감 공고 건수",
                    barmode="stack",
                    labels={"주차": "주차", "건수": "마감 건수", "priority_grade": "등급"},
                )
                fig_cal.update_xaxes(tickangle=45)
                st.plotly_chart(fig_cal, use_container_width=True)

            # D-day scatter
            fig_sc = px.scatter(
                cal_df.sort_values("d_day"),
                x="d_day", y="fitness_score" if "fitness_score" in cal_df.columns else cal_df.index,
                color="priority_grade" if "priority_grade" in cal_df.columns else None,
                color_discrete_map=grade_color_map,
                hover_data=["title", "site"] if "site" in cal_df.columns else ["title"],
                title="D-day × 적합도 산점도",
                labels={"d_day": "남은 일수(D-day)", "fitness_score": "적합도 점수"},
                size_max=18,
            )
            fig_sc.add_vline(x=7,  line_dash="dash", line_color="red",    annotation_text="D-7")
            fig_sc.add_vline(x=30, line_dash="dash", line_color="orange", annotation_text="D-30")
            st.plotly_chart(fig_sc, use_container_width=True)

            # 주차별 공고 목록
            for week, wdf in cal_df.sort_values("_dl").groupby("주차", sort=False):
                with st.expander(f"📅 {week}  —  {len(wdf)}건"):
                    for _, r in wdf.sort_values("d_day").iterrows():
                        g     = r.get("priority_grade", "?")
                        gc    = grade_color_map.get(g, "#888")
                        title = str(r.get("title", ""))
                        dday  = r.get("d_day", "?")
                        site  = r.get("site", "")
                        url   = r.get("detail_url", r.get("notice_link", ""))
                        badge = f"<span style='background:{gc};color:white;border-radius:4px;padding:1px 6px;font-size:0.75rem'>{g}</span>"
                        st.markdown(
                            f"{badge} D-{dday} &nbsp; **[{site}]** {title[:65]}"
                            + (f" &nbsp;[🔗]({url})" if url else ""),
                            unsafe_allow_html=True,
                        )


# ══ TAB13: BD 파이프라인 보드 ═════════════════════════════════════════════════
with tab13:
    st.markdown("### 🎯 BD 파이프라인 보드")
    st.caption("공고별 영업 진행 상태를 퍼널·칸반 뷰로 확인합니다. 메모 탭에서 상태 업데이트 가능.")

    memos_pipe = _load_memos()
    stages     = ["검토중", "제안준비", "제안완료", "수주", "탈락", "보류"]

    # df에 status 컬럼이 있으면 우선, 없으면 메모에서 조회
    pipe_df = df.copy()
    if "status" not in pipe_df.columns:
        pipe_df["status"] = pipe_df.apply(
            lambda r: memos_pipe.get(
                str(r.get("notice_id", r.get("title",""))), {}
            ).get("status", "검토중"),
            axis=1,
        )

    # ── 퍼널 차트 ─────────────────────────────────────────────────────────
    funnel_counts = pipe_df["status"].value_counts().reindex(stages, fill_value=0).reset_index()
    funnel_counts.columns = ["단계", "건수"]
    col_f, col_p = st.columns([1, 1])
    with col_f:
        fig_fn = px.funnel(funnel_counts, x="건수", y="단계",
                           title="영업 파이프라인 퍼널",
                           color_discrete_sequence=["#1565c0"])
        st.plotly_chart(fig_fn, use_container_width=True)

    with col_p:
        # 등급별 × 상태 히트맵
        if "priority_grade" in pipe_df.columns:
            heat_df = pipe_df.groupby(["priority_grade", "status"]).size().reset_index(name="건수")
            fig_heat = px.density_heatmap(
                heat_df, x="status", y="priority_grade", z="건수",
                title="등급 × 상태 히트맵",
                color_continuous_scale="Blues",
                category_orders={"status": stages, "priority_grade": ["A","B","C","D"]},
            )
            st.plotly_chart(fig_heat, use_container_width=True)

    # ── 칸반 스타일 컬럼 ─────────────────────────────────────────────────
    st.markdown("#### 칸반 보드")
    board_stages = ["검토중", "제안준비", "제안완료", "수주"]
    board_cols   = st.columns(len(board_stages))
    stage_colors = {"검토중":"#1565c0","제안준비":"#6a1b9a","제안완료":"#e65100","수주":"#2e7d32"}

    for sc, stage in zip(board_cols, board_stages):
        stage_notices = pipe_df[pipe_df["status"] == stage]
        sc.markdown(
            f"<div style='background:{stage_colors[stage]};color:white;"
            f"border-radius:8px;padding:6px 10px;text-align:center;"
            f"font-weight:700;margin-bottom:8px'>{stage} {len(stage_notices)}건</div>",
            unsafe_allow_html=True,
        )
        for _, r in stage_notices.sort_values("fitness_score", ascending=False).head(8).iterrows():
            title = str(r.get("title",""))[:40]
            grade = str(r.get("priority_grade","?"))
            fit   = r.get("fitness_score", 0)
            sc.markdown(
                f"<div style='border:1px solid #ddd;border-radius:6px;padding:6px 8px;"
                f"margin-bottom:4px;font-size:0.78rem'>"
                f"<b>[{grade}]</b> {title}<br/>"
                f"<span style='color:#888'>적합도 {fit:.0f}</span></div>",
                unsafe_allow_html=True,
            )

    # 탈락/보류 접기
    fallen = pipe_df[pipe_df["status"].isin(["탈락","보류"])]
    if not fallen.empty:
        with st.expander(f"탈락/보류 {len(fallen)}건"):
            show_c = [c for c in ["site","title","priority_grade","fitness_score","status"] if c in fallen.columns]
            st.dataframe(fallen[show_c], use_container_width=True, hide_index=True)


# ══ TAB14: 보고서 다운로드 ════════════════════════════════════════════════════
with tab14:
    st.markdown("### 📤 통합 보고서 다운로드")
    st.caption("현재 로드된 데이터를 기반으로 다중 시트 Excel 보고서를 생성합니다.")

    report_date = st.date_input("보고서 기준일", value=date.today())
    incl_all    = st.checkbox("전체 공고 시트 포함 (데이터가 많으면 느릴 수 있음)", value=True)

    if st.button("📊 보고서 생성", type="primary"):
        from io import BytesIO as _BIO
        _rbuf = _BIO()
        try:
            with pd.ExcelWriter(_rbuf, engine="openpyxl") as _xw:

                # 1) 요약 시트
                summary_data = {
                    "항목": ["기준일", "전체 공고 수", "A등급", "B등급", "C등급", "D등급",
                              "L3 강공고", "파트너 후보", "D-7 긴급"],
                    "값": [
                        str(report_date),
                        len(df),
                        int((df.get("priority_grade", pd.Series()) == "A").sum()),
                        int((df.get("priority_grade", pd.Series()) == "B").sum()),
                        int((df.get("priority_grade", pd.Series()) == "C").sum()),
                        int((df.get("priority_grade", pd.Series()) == "D").sum()),
                        int((df.get("l3_strong", pd.Series()) == "Y").sum()),
                        int((df.get("partner_candidate", pd.Series()) == "Y").sum()),
                        int((df.get("d_day", pd.Series(dtype=float)) <= 7).sum()) if "d_day" in df.columns else 0,
                    ],
                }
                pd.DataFrame(summary_data).to_excel(_xw, index=False, sheet_name="요약")

                # 2) A등급 공고
                a_df = df[df.get("priority_grade", pd.Series()) == "A"] if "priority_grade" in df.columns else pd.DataFrame()
                if not a_df.empty:
                    a_df.to_excel(_xw, index=False, sheet_name="A등급공고")

                # 3) B등급 공고
                b_df = df[df.get("priority_grade", pd.Series()) == "B"] if "priority_grade" in df.columns else pd.DataFrame()
                if not b_df.empty:
                    b_df.to_excel(_xw, index=False, sheet_name="B등급공고")

                # 4) 긴급마감 (D-30 이내)
                if "d_day" in df.columns:
                    urg30 = df[df["d_day"] <= 30].sort_values("d_day")
                    if not urg30.empty:
                        urg30.to_excel(_xw, index=False, sheet_name="긴급마감D30")

                # 5) 사이트 품질 요약
                if "site" in df.columns:
                    q_rows = []
                    for _site, _grp in df.groupby("site"):
                        _total = len(_grp)
                        _l3    = int((_grp.get("l3_strong", pd.Series()) == "Y").sum())
                        _ab    = int(_grp.get("priority_grade", pd.Series()).isin(["A","B"]).sum())
                        _dl    = int((_grp.get("deadline_date", pd.Series()).notna() &
                                      (_grp.get("deadline_date", pd.Series()) != "")).sum()) if "deadline_date" in _grp.columns else 0
                        q_rows.append({
                            "사이트": _site, "수집건수": _total,
                            "A건수": int((_grp.get("priority_grade", pd.Series()) == "A").sum()),
                            "B건수": int((_grp.get("priority_grade", pd.Series()) == "B").sum()),
                            "L3건수": _l3, "AB등급률(%)": round(_ab/_total*100, 1) if _total else 0,
                            "마감일기재율(%)": round(_dl/_total*100, 1) if _total else 0,
                        })
                    pd.DataFrame(q_rows).sort_values("수집건수", ascending=False).to_excel(
                        _xw, index=False, sheet_name="사이트품질"
                    )

                # 6) CRM 메모
                _memos_r = _load_memos()
                if _memos_r:
                    memo_rows = [{"공고ID": k, **v} for k, v in _memos_r.items()]
                    pd.DataFrame(memo_rows).to_excel(_xw, index=False, sheet_name="CRM메모")

                # 7) 전체 공고 (선택)
                if incl_all:
                    df.to_excel(_xw, index=False, sheet_name="전체공고")

            st.success("✅ 보고서 생성 완료!")
            st.download_button(
                "📥 Excel 보고서 다운로드",
                data=_rbuf.getvalue(),
                file_name=f"InterX_BD_Report_{report_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as _re:
            st.error(f"보고서 생성 실패: {_re}")

    st.markdown("---")
    st.markdown("#### 포함 시트 구성")
    st.markdown("""
| 시트명 | 내용 |
|--------|------|
| 요약 | 전체 KPI 수치 |
| A등급공고 | A등급 공고 전체 |
| B등급공고 | B등급 공고 전체 |
| 긴급마감D30 | D-30 이내 마감 공고 |
| 사이트품질 | 사이트별 수집 품질 요약 |
| CRM메모 | 저장된 메모 전체 |
| 전체공고 | 전체 공고 Raw 데이터 (선택) |
""")

# ══ TAB15: ML 수주예측 ════════════════════════════════════════════════════════
_ARTIFACTS_DIR = ROOT / "data" / "artifacts"
_WIN_REPORT_PATH = _ARTIFACTS_DIR / "win_report_latest.json"
_CLUSTERS_PATH   = _ARTIFACTS_DIR / "clusters_latest.json"
_MODEL_PATH      = ROOT / "data" / "models" / "win_pred_lr.pkl"


@st.cache_data(ttl=120)
def _load_win_report() -> dict:
    if not _WIN_REPORT_PATH.exists():
        return {}
    try:
        import json as _json
        return _json.loads(_WIN_REPORT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(ttl=120)
def _load_clusters_json() -> dict:
    if not _CLUSTERS_PATH.exists():
        return {}
    try:
        import json as _json
        return _json.loads(_CLUSTERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


with tab15:
    st.markdown("### 🤖 ML 수주예측 & 클러스터 분석")
    st.caption(
        "파이프라인 실행 후 생성되는 `data/artifacts/win_report_latest.json` 및 "
        "`clusters_latest.json` 을 기반으로 표시합니다."
    )

    # ── 모델 상태 배지 ────────────────────────────────────────────────────
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        if _MODEL_PATH.exists():
            try:
                import pickle as _pkl
                with open(_MODEL_PATH, "rb") as _mf:
                    _mb = _pkl.load(_mf)
                st.success(
                    f"✅ **sklearn 모델 로드됨**\n\n"
                    f"- Accuracy: `{_mb.get('accuracy', 0):.3f}`\n"
                    f"- CV ROC-AUC: `{_mb.get('cv_roc_auc', 0):.3f}`\n"
                    f"- 학습 샘플: `{_mb.get('n_samples', 0)}건`\n"
                    f"- Win 샘플: `{_mb.get('n_win', 0)}건`"
                )
            except Exception:
                st.warning("⚠️ 모델 파일 손상 — 재학습 필요")
        else:
            st.info("📭 학습된 모델 없음 — 사이드바에서 **ML 모델 학습** 버튼 클릭")

    with col_m2:
        win_rep = _load_win_report()
        if win_rep:
            st.info(
                f"📊 **최신 수주예측 리포트**\n\n"
                f"- 실행ID: `{win_rep.get('execution_id', '-')}`\n"
                f"- 생성일: `{win_rep.get('created_at', '-')[:19]}`\n"
                f"- 분석 건수: `{win_rep.get('total', 0)}건`\n"
                f"- A등급: `{win_rep.get('a_count', 0)}건`"
            )
        else:
            st.info("📭 수주예측 리포트 없음 — 파이프라인 실행 후 생성됩니다.")

    st.markdown("---")

    # ── 수주예측 결과 ─────────────────────────────────────────────────────
    st.markdown("#### 🎯 수주 확률 예측 결과")

    if win_rep and win_rep.get("predictions"):
        preds = win_rep["predictions"]
        pred_df = pd.DataFrame(preds)

        # 등급 색상 매핑
        grade_color_ml = {"A": "#e53935", "B": "#fb8c00", "C": "#43a047", "D": "#9e9e9e"}

        # 요약 메트릭
        mc1, mc2, mc3, mc4 = st.columns(4)
        for _col, _grade in zip([mc1, mc2, mc3, mc4], ["A", "B", "C", "D"]):
            _cnt = (pred_df["win_grade"] == _grade).sum() if "win_grade" in pred_df.columns else 0
            _col.metric(f"{_grade}등급", f"{_cnt}건")

        # 수주 확률 히스토그램
        col_h, col_b = st.columns(2)
        with col_h:
            if "win_probability" in pred_df.columns:
                fig_wp = px.histogram(
                    pred_df, x="win_probability", nbins=20,
                    color_discrete_sequence=["#1565c0"],
                    title="수주 확률 분포",
                    labels={"win_probability": "수주 확률"},
                )
                fig_wp.add_vline(x=0.75, line_dash="dash", line_color="#e53935", annotation_text="A(0.75)")
                fig_wp.add_vline(x=0.55, line_dash="dash", line_color="#fb8c00", annotation_text="B(0.55)")
                fig_wp.add_vline(x=0.35, line_dash="dash", line_color="#43a047", annotation_text="C(0.35)")
                st.plotly_chart(fig_wp, use_container_width=True)

        with col_b:
            if "win_grade" in pred_df.columns:
                grade_cnt = pred_df["win_grade"].value_counts().reset_index()
                grade_cnt.columns = ["등급", "건수"]
                fig_gb = px.bar(
                    grade_cnt, x="등급", y="건수",
                    color="등급",
                    color_discrete_map=grade_color_ml,
                    title="등급별 공고 수",
                    text="건수",
                )
                fig_gb.update_traces(textposition="outside")
                st.plotly_chart(fig_gb, use_container_width=True)

        # 피처 기여도 차트 (평균)
        if "feature_contributions" in pred_df.columns:
            try:
                contrib_records = pred_df["feature_contributions"].dropna().tolist()
                if contrib_records and isinstance(contrib_records[0], dict):
                    contrib_avg = {
                        k: round(sum(r.get(k, 0) for r in contrib_records) / len(contrib_records), 4)
                        for k in contrib_records[0]
                    }
                    contrib_df = pd.DataFrame([
                        {"피처": k, "평균 기여도": v}
                        for k, v in sorted(contrib_avg.items(), key=lambda x: -x[1])
                    ])
                    fig_feat = px.bar(
                        contrib_df, x="피처", y="평균 기여도",
                        title="피처별 평균 기여도 (전체 공고)",
                        color="평균 기여도",
                        color_continuous_scale="Blues",
                        text="평균 기여도",
                    )
                    fig_feat.update_traces(texttemplate="%{text:.3f}", textposition="outside")
                    st.plotly_chart(fig_feat, use_container_width=True)
            except Exception:
                pass

        # Top 10 수주 기회 테이블
        st.markdown("#### 🏆 Top 10 수주 기회")
        top10_cols = [c for c in ["title", "site", "win_probability", "win_grade", "recommended_priority"] if c in pred_df.columns]
        top10 = pred_df.nlargest(10, "win_probability")[top10_cols] if "win_probability" in pred_df.columns else pred_df.head(10)[top10_cols]
        rename_ml = {
            "title": "공고명", "site": "사이트",
            "win_probability": "수주확률", "win_grade": "등급",
            "recommended_priority": "권장액션",
        }
        st.dataframe(
            top10.rename(columns=rename_ml),
            use_container_width=True,
            hide_index=True,
            column_config={
                "수주확률": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.3f"),
            },
        )

        # 전체 결과 접기
        with st.expander(f"전체 수주예측 결과 ({len(pred_df)}건)"):
            all_cols = [c for c in ["title", "site", "win_probability", "win_grade", "recommended_priority"] if c in pred_df.columns]
            st.dataframe(pred_df[all_cols].rename(columns=rename_ml).sort_values("수주확률", ascending=False),
                         use_container_width=True, hide_index=True)
    else:
        st.info("수주예측 데이터가 없습니다. 파이프라인 실행 후 자동 생성됩니다.")

    st.markdown("---")

    # ── 클러스터 분석 ─────────────────────────────────────────────────────
    st.markdown("#### 🔗 공고 클러스터 분석")

    clus_data = _load_clusters_json()
    if clus_data and clus_data.get("clusters"):
        clusters_list = clus_data["clusters"]
        st.caption(
            f"클러스터 {clus_data.get('count', 0)}개 "
            f"| 알고리즘: {clus_data.get('clusterer', '-')} "
            f"| 생성: {clus_data.get('created_at', '-')[:19]}"
        )

        # 클러스터 크기 분포
        clus_df = pd.DataFrame([
            {
                "cluster_id":          c.get("cluster_id", ""),
                "크기":                len(c.get("notice_ids", [])),
                "대표공고":            c.get("representative_title", "")[:50],
                "상위솔루션":          c.get("top_solution", "-"),
                "공통키워드":          ", ".join(c.get("common_keywords", [])[:3]),
            }
            for c in clusters_list
        ])

        col_cl, col_cr = st.columns(2)
        with col_cl:
            fig_cs = px.bar(
                clus_df.sort_values("크기", ascending=False).head(15),
                x="cluster_id", y="크기",
                color="크기",
                color_continuous_scale="Teal",
                title="클러스터별 공고 수 (상위 15개)",
                text="크기",
            )
            fig_cs.update_traces(textposition="outside")
            fig_cs.update_xaxes(tickangle=45)
            st.plotly_chart(fig_cs, use_container_width=True)

        with col_cr:
            if "상위솔루션" in clus_df.columns:
                sol_cnt = clus_df["상위솔루션"].value_counts().reset_index()
                sol_cnt.columns = ["솔루션", "클러스터수"]
                fig_sol = px.pie(
                    sol_cnt, names="솔루션", values="클러스터수",
                    title="클러스터별 상위 솔루션 분포",
                    hole=0.35,
                )
                st.plotly_chart(fig_sol, use_container_width=True)

        # 클러스터 상세 테이블
        st.dataframe(clus_df, use_container_width=True, hide_index=True)

        # 클러스터 상세 펼치기
        st.markdown("##### 클러스터 상세 (대표공고 + 포함 공고)")
        for c in sorted(clusters_list, key=lambda x: -len(x.get("notice_ids", []))):
            size = len(c.get("notice_ids", []))
            label = (
                f"[{c.get('cluster_id','')}] {c.get('representative_title','')[:55]} "
                f"— {size}건 묶음 | {c.get('top_solution','-')}"
            )
            with st.expander(label):
                st.markdown(f"**공통 키워드:** {', '.join(c.get('common_keywords', [])) or '없음'}")
                st.markdown(f"**포함 공고 ID 목록 ({size}건):**")
                st.code("\n".join(c.get("notice_ids", [])))
    else:
        st.info("클러스터 데이터가 없습니다. 파이프라인 실행 후 자동 생성됩니다.")

    # ── EmbeddingClusterer 안내 ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🚀 EmbeddingClusterer 활성화 방법")
    st.markdown("""
`full_pipeline.py` 에서 `TfidfClusterer` → `EmbeddingClusterer` 로 교체하면
의미 기반 클러스터링이 활성화됩니다.

```python
# full_pipeline.py __init__ 수정
from interx_engine.infrastructure.clustering.embedding_clusterer import EmbeddingClusterer

self.cluster_uc = ClusterNoticesUseCase(EmbeddingClusterer(threshold=0.70))
```

```bash
# sentence-transformers 설치 (1회)
pip install sentence-transformers
```

> 첫 실행 시 `paraphrase-multilingual-MiniLM-L12-v2` 모델 (~420MB) 자동 다운로드.
> 이후 로컬 캐시 사용. 무료 / 인터넷 연결 없이 추론 가능.
""")


# ─── 하단 ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center; color:#888; font-size:0.8rem'>"
    f"InterX BD Intelligence Engine &nbsp;|&nbsp; {datetime.now().strftime('%Y-%m-%d %H:%M')} 기준</div>",
    unsafe_allow_html=True,
)
