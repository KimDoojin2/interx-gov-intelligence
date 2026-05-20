"""
InterX Government Intelligence Engine — Streamlit Team App
팀원 배포용 원클릭 파이프라인 실행 앱 (v3 — 11개 탭)
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd

# ── 프로젝트 경로 설정 ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:
    if hasattr(sys.stdout, "buffer") and not sys.stdout.buffer.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (ValueError, AttributeError):
    pass

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# ── InterX 브랜드 색상 (v4 — 화이트+오렌지 프리미엄) ─────────────────────────
# 로고 기준: INTER(다크그레이 #3C3C3C) + X(오렌지 #F5921B)
ORANGE_500 = "#F5921B"; ORANGE_400 = "#FF9F2E"; ORANGE_600 = "#E07D0A"
CHARCOAL = "#3C3C3C"; SLATE_700 = "#334155"; SLATE_800 = "#1E293B"
GREEN_A = "#10B981"; BLUE_B = "#3B82F6"; AMBER_C = "#F59E0B"; RED_D = "#EF4444"
TEXT_DARK = "#1E293B"; TEXT_MID = "#64748B"; TEXT_LIGHT = "#94A3B8"
BG_WHITE = "#FFFFFF"; BG_GRAY = "#F8FAFC"; BG_WARM = "#FFFBF5"; BORDER = "#E2E8F0"
GRADE_COLORS = {"A": GREEN_A, "B": BLUE_B, "C": AMBER_C, "D": RED_D}
# 하위 호환 alias
CYAN_400 = ORANGE_500; CYAN_500 = ORANGE_500; CYAN_600 = ORANGE_600
NAVY_900 = CHARCOAL; NAVY_800 = SLATE_700; GOLD_400 = "#FFD700"; MAGENTA = "#FF0064"

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InterX Gov Intelligence",
    page_icon="🔶",
    layout="wide", initial_sidebar_state="collapsed",
)

# ── 로고 인트로 애니메이션 ───────────────────────────────────────────────────
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = True
    st.markdown("""
    <style>
    @keyframes logoFadeIn {
        0% { opacity: 0; transform: scale(0.7) translateY(20px); }
        40% { opacity: 1; transform: scale(1.05) translateY(0); }
        60% { opacity: 1; transform: scale(1) translateY(0); }
        100% { opacity: 0; transform: scale(0.95) translateY(-10px); }
    }
    @keyframes bgFade { 0% { opacity: 1; } 80% { opacity: 1; } 100% { opacity: 0; pointer-events: none; } }
    .intro-overlay {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 99999;
        background: #FFFFFF; display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        animation: bgFade 2.8s ease-in-out forwards;
    }
    .intro-logo {
        animation: logoFadeIn 2.8s ease-in-out forwards;
        display: flex; flex-direction: column; align-items: center; gap: 16px;
    }
    .intro-logo .brand {
        font-size: 3rem; font-weight: 900; letter-spacing: -2px; font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    .intro-logo .brand .inter { color: #3C3C3C; }
    .intro-logo .brand .x { color: #F5921B; }
    .intro-logo .tagline { color: #94A3B8; font-size: 0.95rem; font-weight: 500; letter-spacing: 2px; }
    </style>
    <div class="intro-overlay">
        <div class="intro-logo">
            <div class="brand"><span class="inter">INTER</span><span class="x">X</span></div>
            <div class="tagline">GOVERNMENT INTELLIGENCE ENGINE</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── 프리미엄 CSS ─────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    .stApp {{ background: {BG_WHITE}; font-family: 'Inter', 'Segoe UI', sans-serif; }}
    section[data-testid="stSidebar"] {{ display: none; }}

    /* ── 톱바 ── */
    .interx-topbar {{
        background: linear-gradient(135deg, {CHARCOAL} 0%, {SLATE_800} 100%);
        padding: 1.1rem 2rem; border-radius: 16px; margin-bottom: 1.5rem;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }}
    .interx-topbar .brand {{ font-size: 1.4rem; font-weight: 900; letter-spacing: -1px; }}
    .interx-topbar .brand .inter {{ color: #FFFFFF; }}
    .interx-topbar .brand .x {{ color: {ORANGE_500}; }}
    .interx-topbar .subtitle {{ color: rgba(255,255,255,0.45); font-size: 0.78rem; margin: 0; font-weight: 500; }}
    .interx-topbar .version {{ color: rgba(255,255,255,0.25); font-size: 0.7rem; }}

    /* ── KPI 카드 ── */
    .kpi-card {{
        background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 16px;
        padding: 1.3rem 1rem; text-align: center; transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        position: relative; overflow: hidden;
    }}
    .kpi-card::before {{
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, {ORANGE_500}, {ORANGE_400});
        opacity: 0; transition: opacity 0.3s;
    }}
    .kpi-card:hover {{
        border-color: {ORANGE_500}; transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(245,146,27,0.12);
    }}
    .kpi-card:hover::before {{ opacity: 1; }}
    .kpi-value {{ font-size: 2rem; font-weight: 800; color: {CHARCOAL}; line-height: 1.2; }}
    .kpi-label {{ font-size: 0.75rem; color: {TEXT_MID}; margin-top: 0.4rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }}

    /* ── 등급 색상 ── */
    .grade-a {{ color: {GREEN_A}; font-weight: 800; }}
    .grade-b {{ color: {BLUE_B}; font-weight: 700; }}
    .grade-c {{ color: {AMBER_C}; font-weight: 600; }}
    .grade-d {{ color: {RED_D}; font-weight: 600; }}

    /* ── 공고 카드 ── */
    .notice-card {{
        background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 12px;
        padding: 1rem 1.3rem; margin-bottom: 0.6rem; transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        border-left: 3px solid transparent;
    }}
    .notice-card:hover {{
        border-left-color: {ORANGE_500}; transform: translateX(4px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
    }}
    .notice-title {{ color: {TEXT_DARK}; font-weight: 600; font-size: 0.95rem; margin-bottom: 0.3rem; }}
    .notice-meta {{ color: {TEXT_LIGHT}; font-size: 0.78rem; font-weight: 400; }}

    /* ── 섹션 타이틀 ── */
    .section-title {{
        color: {CHARCOAL}; font-weight: 800; font-size: 1.05rem;
        margin: 1.5rem 0 0.8rem; padding-bottom: 0.5rem;
        border-bottom: 3px solid {ORANGE_500}; display: inline-block;
        letter-spacing: -0.3px;
    }}

    /* ── 프로그레스 바 ── */
    .stProgress > div > div > div > div {{ background: linear-gradient(90deg, {ORANGE_500}, {ORANGE_400}); border-radius: 4px; }}

    /* ── 버튼 ── */
    .stButton > button {{
        background: linear-gradient(135deg, {ORANGE_600}, {ORANGE_500}); color: white;
        font-weight: 700; border: none; border-radius: 10px; padding: 0.65rem 2rem;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1); font-size: 0.9rem;
        letter-spacing: 0.3px;
    }}
    .stButton > button:hover {{
        box-shadow: 0 6px 20px rgba(245,146,27,0.35); transform: translateY(-2px);
        background: linear-gradient(135deg, {ORANGE_500}, {ORANGE_400});
    }}

    /* ── 탭 네비게이션 ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px; background: {BG_GRAY}; border-radius: 12px; padding: 5px;
        border: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT_MID}; border-radius: 10px; padding: 10px 18px;
        font-weight: 600; font-size: 0.82rem; transition: all 0.2s;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ color: {ORANGE_500}; background: rgba(245,146,27,0.04); }}
    .stTabs [aria-selected="true"] {{
        background: {BG_WHITE}; color: {ORANGE_600}; font-weight: 700;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}

    /* ── 숨김 ── */
    #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}}

    /* ── 데이터프레임 스타일 ── */
    .stDataFrame {{ border-radius: 12px; overflow: hidden; }}

    /* ── 토글/셀렉트박스 ── */
    .stSelectbox label, .stMultiSelect label, .stSlider label {{ font-weight: 600; color: {TEXT_DARK}; font-size: 0.85rem; }}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  유틸
# ═══════════════════════════════════════════════════════════════════════════════

def _calc_dday(deadline: str) -> int:
    try:
        return (datetime.strptime(deadline, "%Y-%m-%d").date() - date.today()).days
    except (ValueError, TypeError):
        return -1

def _kpi(value, label):
    return f'<div class="kpi-card"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>'

def _nodata():
    st.info("데이터가 없습니다. 먼저 수집 실행 탭에서 수집을 시작해주세요.")

def _get_result():
    return st.session_state.get("pipeline_result")

def _get_score_map(result):
    sc = result.get("score_cards", [])
    return {s.notice_id: s for s in sc}

# ── plotly 공통 레이아웃 ──────────────────────────────────────────────────────
def _layout(**kw):
    base = dict(
        paper_bgcolor=BG_WHITE, plot_bgcolor=BG_GRAY,
        font=dict(color=TEXT_DARK, family="Inter, Segoe UI, sans-serif", size=12),
        margin=dict(t=50, b=40, l=40, r=20),
        hoverlabel=dict(bgcolor=CHARCOAL, font_color="white", font_size=12),
    )
    base.update(kw)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
#  헤더 + 탭
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="interx-topbar">
    <div>
        <div class="brand"><span class="inter">INTER</span><span class="x">X</span></div>
        <p class="subtitle">Government Intelligence Engine</p>
    </div>
    <div class="version">v4.5 &nbsp;|&nbsp; 16 Sites &nbsp;|&nbsp; 23 Analytics</div>
</div>
""", unsafe_allow_html=True)

tab_dash, tab_run, tab_notices, tab_proposal, tab_compete, \
tab_predict, tab_calendar, tab_solution, tab_keyword, tab_manager, tab_history = st.tabs([
    "대시보드", "수집 실행", "공고 목록", "제안서", "경쟁사 분석",
    "수주 예측", "마감 캘린더", "솔루션 매칭", "키워드 트렌드", "담당자 현황", "수집 히스토리",
])

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "collection_history" not in st.session_state:
    st.session_state.collection_history = []  # [{timestamp, result_summary, notices_count, grades, sites}]
if "selected_notice_id" not in st.session_state:
    st.session_state.selected_notice_id = None

all_sites = [
    "bizinfo", "kiat", "nipa", "innopolis", "bipa", "uipa",
    "gicon", "ttp", "dicia", "gjtp", "kised", "ketep",
    "koiia", "jejutp", "smart_factory", "iitp",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 1: 대시보드
# ═══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    result = _get_result()
    if not result:
        st.markdown(f"""
        <div style="text-align:center; padding:5rem 0;">
            <div style="font-size:3.5rem; font-weight:900; letter-spacing:-2px; margin-bottom:1rem;">
                <span style="color:{CHARCOAL};">INTER</span><span style="color:{ORANGE_500};">X</span>
            </div>
            <p style="color:{TEXT_MID}; font-size:1.05rem;">아직 수집된 데이터가 없습니다</p>
            <p style="color:{TEXT_LIGHT}; font-size:0.85rem; margin-top:0.5rem;">
                <b style="color:{ORANGE_500};">수집 실행</b> 탭에서 공고 수집을 시작하세요
            </p>
        </div>""", unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", [])
        score_map = _get_score_map(result)
        total = len(notices)
        grades = {"A": 0, "B": 0, "C": 0, "D": 0}
        l3_count = urgent_count = 0
        for n in notices:
            sc = score_map.get(n.notice_id)
            if sc: grades[sc.priority_grade] = grades.get(sc.priority_grade, 0) + 1
            if getattr(n, "l3_strong", "N") == "Y": l3_count += 1
            dd = _calc_dday(n.deadline_date or "")
            if 0 <= dd <= 7: urgent_count += 1

        cols = st.columns(6)
        for col, (v, l) in zip(cols, [
            (total, "전체 공고"),
            (f'<span style="color:{GREEN_A}">{grades["A"]}</span>', "A등급"),
            (f'<span style="color:{CYAN_500}">{grades["B"]}</span>', "B등급"),
            (f'<span style="color:{MAGENTA}">{l3_count}</span>', "L3 강공고"),
            (f'<span style="color:{RED_D}">{urgent_count}</span>', "7일내 마감"),
            (len(result.get("proposal_files", [])), "제안서 생성"),
        ]): col.markdown(_kpi(v, l), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c_chart, c_list = st.columns([1, 2])
        with c_chart:
            fig = go.Figure(go.Pie(
                labels=["A등급", "B등급", "C등급", "D등급"],
                values=[grades["A"], grades["B"], grades["C"], grades["D"]],
                marker_colors=[GREEN_A, BLUE_B, AMBER_C, RED_D],
                hole=0.55, textinfo="label+value", textfont=dict(color=TEXT_DARK, size=13)))
            fig.update_layout(title=dict(text="등급 분포", font=dict(color=TEXT_DARK, size=16)),
                              showlegend=False, height=350, **_layout())
            st.plotly_chart(fig, use_container_width=True)
        with c_list:
            st.markdown(f'<div class="section-title">A등급 핵심 공고 ({grades["A"]}건)</div>', unsafe_allow_html=True)
            a_list = sorted([(n, score_map[n.notice_id]) for n in notices
                             if score_map.get(n.notice_id) and score_map[n.notice_id].priority_grade == "A"],
                            key=lambda x: -x[1].priority_score)
            for n, sc in a_list[:10]:
                dd = _calc_dday(n.deadline_date or "")
                l3 = ' <span style="color:#FF0064;font-weight:700;">[L3]</span>' if getattr(n, "l3_strong", "N") == "Y" else ""
                st.markdown(f'''<div class="notice-card"><div class="notice-title"><span class="grade-a">A</span> {n.title[:60]}{l3}</div>
                    <div class="notice-meta">{n.site} | {n.agency or n.ministry or "-"} | 점수: {sc.priority_score:.0f} | D-{dd} | {n.deadline_date or "-"}</div></div>''', unsafe_allow_html=True)

        st.markdown('<div class="section-title">사이트별 수집 현황</div>', unsafe_allow_html=True)
        sc_cnt = Counter(n.site for n in notices).most_common()
        if sc_cnt:
            fig2 = go.Figure(go.Bar(x=[s[0] for s in sc_cnt], y=[s[1] for s in sc_cnt],
                                    marker_color=ORANGE_500, marker_line_color=ORANGE_600, marker_line_width=1))
            fig2.update_layout(height=300, xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER, title="공고 수"), **_layout())
            st.plotly_chart(fig2, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 2: 수집 실행
# ═══════════════════════════════════════════════════════════════════════════════

with tab_run:
    st.markdown('<div class="section-title">수집 설정</div>', unsafe_allow_html=True)
    cs1, cs2, cs3 = st.columns(3)
    with cs1: run_mode = st.selectbox("실행 모드", ["일반 수집 (빠름)", "전체 분석 (클러스터+알림)", "테스트 (Mock 데이터)"])
    with cs2: max_pages = st.slider("사이트당 최대 페이지", 1, 10, 5)
    with cs3: enable_sheets = st.toggle("Google Sheets 업로드", value=True)
    with st.expander("수집 사이트 선택 (기본: 전체 16개)", expanded=False):
        selected_sites = st.multiselect("사이트", all_sites, default=all_sites, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(_kpi(len(selected_sites), "선택된 사이트"), unsafe_allow_html=True)
    c2.markdown(_kpi(max_pages, "최대 페이지"), unsafe_allow_html=True)
    ml = "일반 수집" if "일반" in run_mode else "전체 분석" if "전체" in run_mode else "테스트"
    c3.markdown(_kpi(ml, "실행 모드"), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    cb, cs = st.columns([1, 2])
    with cb: run_clicked = st.button("수집 시작", type="primary", use_container_width=True, disabled=st.session_state.pipeline_running)
    with cs:
        if st.session_state.pipeline_result:
            st.success(f"마지막 실행: {len(st.session_state.pipeline_result.get('notices',[]))}건 수집 완료")

    if run_clicked:
        st.session_state.pipeline_running = True
        sites_to_use = selected_sites if selected_sites else all_sites
        with st.status("공고 수집 중...", expanded=True) as status:
            st.write(f"실행 모드: **{run_mode}** | 사이트: **{len(sites_to_use)}**개 | 페이지: **{max_pages}**/site")
            st.write("---")
            progress = st.progress(0, text="엔진 초기화 중...")
            try:
                progress.progress(5, text="설정 로딩 중...")
                from interx_engine.infrastructure.config.settings_loader import settings
                settings.ensure_dirs()
                progress.progress(10, text="수집기 구성 중...")
                dry_run = "테스트" in run_mode; full = "전체" in run_mode
                from run_engine import build_collectors, build_sheet_gateway, MultiCollectorAdapter
                collectors = build_collectors(sites_to_use if len(sites_to_use) < 16 else None, max_pages, dry_run=dry_run)
                st.write(f"**{len(collectors)}**개 수집기 생성")
                multi = MultiCollectorAdapter(collectors, max_workers=8)
                sheet_gw = build_sheet_gateway(enable_sheets)
                progress.progress(20, text="파이프라인 실행 중...")
                execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")
                if full:
                    from interx_engine.application.orchestrators.full_pipeline import FullPipelineOrchestrator
                    orch = FullPipelineOrchestrator(collector=multi, base_dir=str(ROOT), sheet_gateway=sheet_gw)
                else:
                    from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
                    orch = DailyPipelineOrchestrator(collector=multi, sheet_gateway=sheet_gw)
                os.environ.pop("TELEGRAM_BOT_TOKEN", None); os.environ.pop("SLACK_WEBHOOK_URL", None)
                result = orch.run(execution_id)
                progress.progress(90, text="결과 정리 중...")
                nn = result.get("notices", []); scs = result.get("score_cards", [])
                gc = {"A":0,"B":0,"C":0,"D":0}; sm = {s.notice_id: s for s in scs}
                for n in nn:
                    sc = sm.get(n.notice_id)
                    if sc: gc[sc.priority_grade] = gc.get(sc.priority_grade,0)+1
                st.write(f"**{len(nn)}**건 수집 | A={gc['A']} B={gc['B']} C={gc['C']} D={gc['D']}")
                pp = result.get("proposal_files", [])
                if pp: st.write(f"**{len(pp)}**건 제안서 생성")
                progress.progress(100, text="완료!")
                st.session_state.pipeline_result = result
                st.session_state.pipeline_running = False
                # ── 수집 히스토리 저장 ──
                site_cnt = Counter(n.site for n in nn)
                history_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "execution_id": execution_id,
                    "total": len(nn),
                    "grades": dict(gc),
                    "sites": dict(site_cnt),
                    "proposals": len(pp),
                    "mode": ml,
                    "l3_count": sum(1 for n in nn if getattr(n, "l3_strong", "N") == "Y"),
                }
                st.session_state.collection_history.append(history_entry)
                status.update(label=f"완료! {len(nn)}건 수집", state="complete")
                time.sleep(1); st.rerun()
            except Exception as e:
                status.update(label=f"오류: {e}", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback; st.code(traceback.format_exc())
                st.session_state.pipeline_running = False


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 3: 공고 목록 + 상세 보기
# ═══════════════════════════════════════════════════════════════════════════════

with tab_notices:
    result = _get_result()
    if not result: _nodata()
    else:
        notices = result.get("notices", []); score_map = _get_score_map(result)
        st.markdown('<div class="section-title">필터</div>', unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        with f1: gf = st.multiselect("등급", ["A","B","C","D"], default=["A","B","C","D"])
        with f2: sf = st.multiselect("사이트", sorted(set(n.site for n in notices)))
        with f3: kw = st.text_input("검색", placeholder="키워드를 입력하세요...")
        filtered = []
        for n in notices:
            sc = score_map.get(n.notice_id); g = sc.priority_grade if sc else "D"
            if g not in gf: continue
            if sf and n.site not in sf: continue
            if kw and kw.lower() not in (n.title or "").lower(): continue
            filtered.append((n, sc))
        go_ = {"A":0,"B":1,"C":2,"D":3}
        filtered.sort(key=lambda x: (go_.get(x[1].priority_grade if x[1] else "D",3), -(x[1].priority_score if x[1] else 0)))
        st.markdown(f'<p style="color:{TEXT_MID};font-size:0.85rem;">필터 결과: {len(filtered)} / {len(notices)}건</p>', unsafe_allow_html=True)

        rows = []
        for n, sc in filtered:
            dd = _calc_dday(n.deadline_date or "")
            rows.append({"등급": sc.priority_grade if sc else "D", "점수": f"{sc.priority_score:.0f}" if sc else "-",
                         "공고명": n.title[:70] if n.title else "-", "주관기관": n.agency or n.ministry or "-",
                         "사이트": n.site, "마감일": n.deadline_date or "-", "D-day": dd if dd>=0 else "마감",
                         "L3": "Y" if getattr(n,"l3_strong","N")=="Y" else "", "예산": n.budget or "-"})
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, height=450)

            # ── 다운로드 버튼 (CSV + Excel) ──
            dl1, dl2, _ = st.columns([1,1,4])
            dl1.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                                f"interx_공고_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    df.to_excel(w, index=False, sheet_name="공고목록")
                    # 컬럼 너비 자동 조정
                    ws = w.sheets["공고목록"]
                    for col_idx, col_name in enumerate(df.columns, 1):
                        max_len = max(len(str(col_name)), df[col_name].astype(str).str.len().max())
                        ws.column_dimensions[chr(64+col_idx) if col_idx<=26 else "A"].width = min(max_len + 4, 40)
                dl2.download_button("Excel 다운로드 (.xlsx)", buf.getvalue(),
                                    f"interx_공고_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: pass

            # ── 공고 상세 보기 ──
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f'<div class="section-title">공고 상세 보기</div>', unsafe_allow_html=True)
            notice_titles = {f"[{sc.priority_grade if sc else 'D'}] {n.title[:60]} ({n.site})": (n, sc) for n, sc in filtered}
            selected_title = st.selectbox("공고를 선택하세요", ["선택하세요..."] + list(notice_titles.keys()),
                                           label_visibility="collapsed")
            if selected_title != "선택하세요..." and selected_title in notice_titles:
                sel_n, sel_sc = notice_titles[selected_title]
                dd = _calc_dday(sel_n.deadline_date or "")
                grade = sel_sc.priority_grade if sel_sc else "D"
                grade_color = GRADE_COLORS.get(grade, TEXT_MID)

                # 상세 헤더
                st.markdown(f"""
                <div style="background:{BG_GRAY}; border:2px solid {grade_color}; border-radius:12px; padding:1.5rem; margin:0.5rem 0;">
                    <div style="display:flex; align-items:center; gap:1rem; margin-bottom:1rem;">
                        <span style="background:{grade_color}; color:white; padding:0.3rem 0.8rem; border-radius:6px; font-weight:800; font-size:1.2rem;">{grade}등급</span>
                        <span style="font-size:1.1rem; font-weight:700; color:{TEXT_DARK};">{sel_n.title}</span>
                    </div>
                </div>""", unsafe_allow_html=True)

                # 기본 정보 + 점수 정보 2컬럼
                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("**기본 정보**")
                    info_items = [
                        ("주관기관", sel_n.agency or sel_n.ministry or "-"),
                        ("부처", getattr(sel_n, "ministry", "-") or "-"),
                        ("사이트", sel_n.site),
                        ("마감일", f"{sel_n.deadline_date or '-'}  (D-{dd})" if dd >= 0 else f"{sel_n.deadline_date or '-'} (마감)"),
                        ("예산", sel_n.budget or "-"),
                        ("공고일", getattr(sel_n, "notice_date", "-") or "-"),
                        ("신청기간", getattr(sel_n, "apply_period", "-") or "-"),
                        ("링크", sel_n.link or "-"),
                    ]
                    for label, val in info_items:
                        if label == "링크" and val != "-":
                            st.markdown(f"- **{label}**: [{val[:50]}...]({val})")
                        else:
                            st.markdown(f"- **{label}**: {val}")

                with dc2:
                    if sel_sc:
                        st.markdown("**점수 상세**")
                        st.markdown(f"- **적합도 (fitness)**: {sel_sc.fitness_score:.1f}")
                        st.markdown(f"- **우선순위 (priority)**: {sel_sc.priority_score:.1f}")
                        st.markdown(f"- **산업 적합도 (industry)**: {sel_sc.industry_score:.1f}")
                        st.markdown(f"- **L3 강공고**: {'Y' if getattr(sel_n, 'l3_strong', 'N') == 'Y' else 'N'}")

                        # 수주 확률 계산
                        fitness = sel_sc.fitness_score or 0
                        priority = sel_sc.priority_score or 0
                        industry = sel_sc.industry_score or 0
                        l3v = 1 if getattr(sel_n, "l3_strong", "N") == "Y" else 0
                        urg = max(0, min(100, (30 - dd) * 3.33)) if dd >= 0 else 0
                        wp = min(100, max(0, fitness*0.35 + priority*0.25 + 50*0.15 + urg*0.10 + l3v*10 + industry*0.05))
                        wp_color = GREEN_A if wp >= 60 else CYAN_500 if wp >= 40 else "#F59E0B" if wp >= 20 else RED_D
                        st.markdown(f"- **수주 확률**: <span style='color:{wp_color};font-weight:800;'>{wp:.0f}%</span>", unsafe_allow_html=True)

                        # 매칭 키워드
                        if sel_sc.positive_keywords:
                            kw_tags = " ".join(f'<span style="background:{CYAN_400};color:white;padding:2px 8px;border-radius:4px;font-size:0.8rem;margin:2px;">{k}</span>' for k in sel_sc.positive_keywords[:15])
                            st.markdown(f"**매칭 키워드**: {kw_tags}", unsafe_allow_html=True)

                        # 솔루션 점수
                        if sel_sc.solution_scores:
                            st.markdown("**솔루션별 점수**")
                            SOL_NAMES_D = {"ManufacturingDT":"제조DT", "RecipeAI":"레시피AI", "QualityAI":"품질AI",
                                          "InspectionAI":"비전검사", "SafetyAI":"안전AI", "GenAI":"GenAI",
                                          "InfraDS":"데이터인프라", "PdM":"예지보전"}
                            sol_items = [(SOL_NAMES_D.get(k,k), v) for k,v in sel_sc.solution_scores.items() if v > 0]
                            if sol_items:
                                sol_items.sort(key=lambda x: -x[1])
                                sol_text = " | ".join(f"**{name}** {score:.0f}" for name, score in sol_items)
                                st.markdown(sol_text)
                            else:
                                st.markdown("_매칭 솔루션 없음_")

                # 본문 (body_text)
                body = getattr(sel_n, "body_text", "") or ""
                if body:
                    with st.expander("공고 본문 보기", expanded=False):
                        st.text(body[:5000])
                        if len(body) > 5000:
                            st.caption(f"... (전체 {len(body):,}자 중 5,000자 표시)")

                # 구조화 정보
                structured = {}
                for field in ["purpose", "support_content", "target", "apply_method"]:
                    val = getattr(sel_n, field, None)
                    if val: structured[field] = val
                if structured:
                    field_labels = {"purpose": "사업 목적", "support_content": "지원 내용",
                                    "target": "지원 대상", "apply_method": "신청 방법"}
                    with st.expander("구조화 정보 보기", expanded=False):
                        for field, val in structured.items():
                            st.markdown(f"**{field_labels.get(field, field)}**")
                            st.text(val[:2000])
        else: st.warning("필터 조건에 맞는 공고가 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 4: 제안서
# ═══════════════════════════════════════════════════════════════════════════════

with tab_proposal:
    result = _get_result()
    if not result: _nodata()
    else:
        proposals = result.get("proposal_files", [])
        if not proposals: st.warning("생성된 제안서가 없습니다.")
        else:
            st.markdown(f'<div class="section-title">자동 생성 제안서 ({len(proposals)}건)</div>', unsafe_allow_html=True)
            for p in proposals:
                fp = Path(p)
                if fp.exists():
                    cn, cd = st.columns([5, 1])
                    cn.markdown(f'<div class="notice-card"><div class="notice-title">{fp.name}</div><div class="notice-meta">{fp.stat().st_size:,} bytes</div></div>', unsafe_allow_html=True)
                    with open(fp, "rb") as f:
                        cd.download_button("다운로드", f.read(), fp.name,
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           key=f"dl_{fp.name}")


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 5: 경쟁사 분석
# ═══════════════════════════════════════════════════════════════════════════════

with tab_compete:
    result = _get_result()
    if not result: _nodata()
    else:
        notices = result.get("notices", []); score_cards = result.get("score_cards", [])
        if notices:
            try:
                import plotly.graph_objects as go
                from interx_engine.application.use_cases.competitor_report import generate_competitor_report
                with st.spinner("경쟁사 리포트 생성 중..."):
                    cr = generate_competitor_report(notices, score_cards)
                s = cr.get("summary", {}); cn = cr.get("competitor_notices", [])
                c1,c2,c3,c4 = st.columns(4)
                c1.markdown(_kpi(s.get("total_notices",0),"전체 공고"), unsafe_allow_html=True)
                c2.markdown(_kpi(s.get("competitor_related",0),"경쟁사 관련"), unsafe_allow_html=True)
                c3.markdown(_kpi(f'{s.get("competitor_ratio",0)}%',"경쟁 비율"), unsafe_allow_html=True)
                c4.markdown(_kpi(s.get("tier1_count",0),"Tier1 탐지"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                tc = s.get("top_competitors", [])
                if tc:
                    fig = go.Figure(go.Bar(x=[c[1] for c in tc[:10]], y=[c[0] for c in tc[:10]], orientation='h', marker_color=CYAN_400))
                    fig.update_layout(title=dict(text="경쟁사 탐지 TOP 10", font=dict(color=TEXT_DARK)),
                                      height=400, yaxis=dict(autorange="reversed"), xaxis=dict(gridcolor=BORDER, title="탐지 횟수"), **_layout())
                    st.plotly_chart(fig, use_container_width=True)
                if cn:
                    st.markdown(f'<div class="section-title">경쟁사 관련 공고 ({len(cn)}건)</div>', unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame([{"등급":c["grade"],"공고명":c["title"][:60],"사이트":c["site"],
                                                "마감일":c["deadline"] or "-","경쟁사":" / ".join(c["competitors"]),
                                                "Tier":" / ".join(c["tiers"])} for c in cn]),
                                 use_container_width=True, height=400)
            except Exception as e: st.error(f"경쟁사 리포트 생성 실패: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 6: 수주 예측
# ═══════════════════════════════════════════════════════════════════════════════

with tab_predict:
    result = _get_result()
    if not result: _nodata()
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); score_map = _get_score_map(result)

        # 수주 예측 데이터 수집
        predictions = []
        for n in notices:
            sc = score_map.get(n.notice_id)
            if not sc: continue
            # 간단 수주 확률 계산 (엔진의 win_prediction 로직)
            fitness = sc.fitness_score or 0
            priority = sc.priority_score or 0
            industry = sc.industry_score or 0
            l3 = 1 if getattr(n, "l3_strong", "N") == "Y" else 0
            dd = _calc_dday(n.deadline_date or "")
            urgency = max(0, min(100, (30 - dd) * 3.33)) if dd >= 0 else 0
            budget_score = 50  # 기본값
            win_prob = (fitness * 0.35 + priority * 0.25 + budget_score * 0.15 +
                        urgency * 0.10 + l3 * 10 + industry * 0.05)
            win_prob = min(100, max(0, win_prob))
            predictions.append({"notice": n, "sc": sc, "win_prob": win_prob})

        predictions.sort(key=lambda x: -x["win_prob"])

        # KPI
        high_prob = sum(1 for p in predictions if p["win_prob"] >= 60)
        avg_prob = sum(p["win_prob"] for p in predictions) / max(1, len(predictions))
        k1,k2,k3 = st.columns(3)
        k1.markdown(_kpi(len(predictions), "예측 대상"), unsafe_allow_html=True)
        k2.markdown(_kpi(f'<span style="color:{GREEN_A}">{high_prob}</span>', "수주 유망 (60%+)"), unsafe_allow_html=True)
        k3.markdown(_kpi(f"{avg_prob:.0f}%", "평균 수주 확률"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # 수주 확률 분포 히스토그램
        col_hist, col_top = st.columns([1, 2])
        with col_hist:
            bins = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
            for p in predictions:
                wp = p["win_prob"]
                if wp < 20: bins["0-20%"] += 1
                elif wp < 40: bins["20-40%"] += 1
                elif wp < 60: bins["40-60%"] += 1
                elif wp < 80: bins["60-80%"] += 1
                else: bins["80-100%"] += 1
            fig = go.Figure(go.Bar(x=list(bins.keys()), y=list(bins.values()),
                                   marker_color=[RED_D, AMBER_C, "#FBBF24", BLUE_B, GREEN_A]))
            fig.update_layout(title=dict(text="수주 확률 분포", font=dict(color=TEXT_DARK)),
                              height=350, xaxis=dict(title="확률 구간"), yaxis=dict(title="공고 수", gridcolor=BORDER), **_layout())
            st.plotly_chart(fig, use_container_width=True)

        with col_top:
            st.markdown('<div class="section-title">수주 유망 TOP 10</div>', unsafe_allow_html=True)
            for p in predictions[:10]:
                n, sc, wp = p["notice"], p["sc"], p["win_prob"]
                color = GREEN_A if wp >= 60 else BLUE_B if wp >= 40 else AMBER_C
                st.markdown(f'''<div class="notice-card"><div class="notice-title">
                    <span style="color:{color};font-weight:800;">{wp:.0f}%</span> {n.title[:55]}
                    </div><div class="notice-meta">{sc.priority_grade}등급 | {n.site} | {n.agency or "-"} | {n.deadline_date or "-"}</div></div>''',
                    unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 7: 마감 캘린더
# ═══════════════════════════════════════════════════════════════════════════════

with tab_calendar:
    result = _get_result()
    if not result: _nodata()
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); score_map = _get_score_map(result)

        # 마감일별 공고 그룹
        deadline_groups = defaultdict(list)
        for n in notices:
            dd = n.deadline_date or ""
            if dd: deadline_groups[dd].append(n)

        # D-day 기준 정렬
        today = date.today()
        upcoming = []
        for dl, ns in sorted(deadline_groups.items()):
            dd = _calc_dday(dl)
            if dd < 0: continue  # 이미 마감
            for n in ns:
                sc = score_map.get(n.notice_id)
                upcoming.append({"date": dl, "dday": dd, "notice": n, "sc": sc})

        # KPI
        d3 = sum(1 for u in upcoming if u["dday"] <= 3)
        d7 = sum(1 for u in upcoming if u["dday"] <= 7)
        d30 = sum(1 for u in upcoming if u["dday"] <= 30)
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(_kpi(f'<span style="color:{RED_D}">{d3}</span>', "3일내 마감"), unsafe_allow_html=True)
        k2.markdown(_kpi(f'<span style="color:#F59E0B">{d7}</span>', "7일내 마감"), unsafe_allow_html=True)
        k3.markdown(_kpi(d30, "30일내 마감"), unsafe_allow_html=True)
        k4.markdown(_kpi(len(upcoming), "전체 미마감"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # 타임라인 차트
        if upcoming:
            dates = sorted(set(u["date"] for u in upcoming))[:30]
            date_counts = Counter(u["date"] for u in upcoming)
            fig = go.Figure(go.Bar(x=dates, y=[date_counts[d] for d in dates], marker_color=[
                RED_D if _calc_dday(d) <= 3 else AMBER_C if _calc_dday(d) <= 7 else ORANGE_500 for d in dates]))
            fig.update_layout(title=dict(text="마감일별 공고 수 (30일)", font=dict(color=TEXT_DARK)),
                              height=300, xaxis=dict(title="마감일"), yaxis=dict(title="공고 수", gridcolor=BORDER), **_layout())
            st.plotly_chart(fig, use_container_width=True)

        # 긴급 마감 리스트
        st.markdown(f'<div class="section-title">긴급 마감 공고 (D-7 이내, {d7}건)</div>', unsafe_allow_html=True)
        for u in upcoming:
            if u["dday"] > 7: break
            n, sc, dd = u["notice"], u["sc"], u["dday"]
            grade = sc.priority_grade if sc else "D"
            color = RED_D if dd <= 3 else AMBER_C
            st.markdown(f'''<div class="notice-card"><div class="notice-title">
                <span style="color:{color};font-weight:800;">D-{dd}</span>
                <span class="grade-{grade.lower()}">[{grade}]</span> {n.title[:55]}
                </div><div class="notice-meta">{n.site} | {n.agency or "-"} | 마감: {n.deadline_date}</div></div>''',
                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 8: 솔루션 매칭
# ═══════════════════════════════════════════════════════════════════════════════

with tab_solution:
    result = _get_result()
    if not result: _nodata()
    else:
        import plotly.graph_objects as go
        score_cards = result.get("score_cards", [])
        SOL_NAMES = {"ManufacturingDT":"제조 디지털트윈", "RecipeAI":"레시피 AI", "QualityAI":"품질 AI",
                     "InspectionAI":"비전 검사 AI", "SafetyAI":"안전 AI", "GenAI":"제조 GenAI",
                     "InfraDS":"데이터 인프라", "PdM":"예지보전"}

        # 솔루션별 평균 점수
        sol_totals = defaultdict(list)
        for sc in score_cards:
            if sc.solution_scores:
                for k, v in sc.solution_scores.items():
                    if v > 0: sol_totals[k].append(v)

        if sol_totals:
            sol_avg = {k: sum(v)/len(v) for k, v in sol_totals.items()}
            sol_count = {k: len(v) for k, v in sol_totals.items()}
            sorted_sols = sorted(sol_avg.items(), key=lambda x: -x[1])

            # KPI
            top_sol = sorted_sols[0] if sorted_sols else ("N/A", 0)
            k1, k2, k3 = st.columns(3)
            k1.markdown(_kpi(len(sol_totals), "매칭 솔루션"), unsafe_allow_html=True)
            k2.markdown(_kpi(SOL_NAMES.get(top_sol[0], top_sol[0]), "최고 매칭 솔루션"), unsafe_allow_html=True)
            k3.markdown(_kpi(f"{top_sol[1]:.0f}점", "최고 평균 점수"), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # 레이더 차트
            col_radar, col_bar = st.columns(2)
            with col_radar:
                cats = [SOL_NAMES.get(k, k) for k in sol_avg.keys()]
                vals = list(sol_avg.values())
                fig = go.Figure(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]],
                                                fill='toself', fillcolor='rgba(245,146,27,0.12)',
                                                line=dict(color=ORANGE_500, width=2.5),
                                                marker=dict(size=7, color=ORANGE_500)))
                fig.update_layout(title=dict(text="솔루션별 평균 적합도", font=dict(color=TEXT_DARK)),
                                  polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor=BORDER),
                                             bgcolor=BG_GRAY, angularaxis=dict(gridcolor=BORDER)),
                                  height=400, **_layout())
                st.plotly_chart(fig, use_container_width=True)

            with col_bar:
                names = [SOL_NAMES.get(k, k) for k, _ in sorted_sols]
                avgs = [v for _, v in sorted_sols]
                counts = [sol_count[k] for k, _ in sorted_sols]
                fig = go.Figure()
                fig.add_trace(go.Bar(x=names, y=avgs, name="평균 점수", marker_color=ORANGE_500))
                fig.add_trace(go.Bar(x=names, y=counts, name="매칭 공고 수", marker_color=BLUE_B))
                fig.update_layout(title=dict(text="솔루션별 점수 & 공고 수", font=dict(color=TEXT_DARK)),
                                  barmode='group', height=400, xaxis=dict(gridcolor=BORDER),
                                  yaxis=dict(gridcolor=BORDER), legend=dict(orientation="h", y=1.12), **_layout())
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("솔루션 점수 데이터가 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 9: 키워드 트렌드
# ═══════════════════════════════════════════════════════════════════════════════

with tab_keyword:
    result = _get_result()
    if not result: _nodata()
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); score_cards = result.get("score_cards", [])
        sc_map = {s.notice_id: s for s in score_cards}

        # 매칭된 키워드 수집
        kw_counter = Counter()
        for sc in score_cards:
            if sc.positive_keywords:
                for kw in sc.positive_keywords:
                    kw_counter[kw] += 1

        # 제목에서 자주 나오는 단어 (2글자 이상)
        title_words = Counter()
        stopwords = {"사업", "지원", "공고", "모집", "안내", "위한", "대한", "관련", "통한", "기반", "활용", "추진", "참여",
                     "신청", "접수", "대상", "분야", "과제", "수행", "기관", "선정", "계획", "결과", "변경", "연장"}
        for n in notices:
            words = (n.title or "").split()
            for w in words:
                clean = "".join(c for c in w if c.isalnum())
                if len(clean) >= 2 and clean not in stopwords:
                    title_words[clean] += 1

        k1, k2 = st.columns(2)
        k1.markdown(_kpi(len(kw_counter), "매칭 키워드 수"), unsafe_allow_html=True)
        k2.markdown(_kpi(kw_counter.most_common(1)[0][0] if kw_counter else "-", "최다 키워드"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col_kw, col_title = st.columns(2)
        with col_kw:
            if kw_counter:
                top20 = kw_counter.most_common(20)
                fig = go.Figure(go.Bar(y=[k[0] for k in reversed(top20)], x=[k[1] for k in reversed(top20)],
                                       orientation='h', marker_color=ORANGE_500))
                fig.update_layout(title=dict(text="매칭 키워드 TOP 20 (스코어링)", font=dict(color=TEXT_DARK)),
                                  height=500, xaxis=dict(title="출현 횟수", gridcolor=BORDER), **_layout(margin=dict(l=120,r=20,t=50,b=40)))
                st.plotly_chart(fig, use_container_width=True)

        with col_title:
            if title_words:
                top20t = title_words.most_common(20)
                fig = go.Figure(go.Bar(y=[k[0] for k in reversed(top20t)], x=[k[1] for k in reversed(top20t)],
                                       orientation='h', marker_color=BLUE_B))
                fig.update_layout(title=dict(text="공고 제목 빈출 단어 TOP 20", font=dict(color=TEXT_DARK)),
                                  height=500, xaxis=dict(title="출현 횟수", gridcolor=BORDER), **_layout(margin=dict(l=120,r=20,t=50,b=40)))
                st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 10: 담당자 현황
# ═══════════════════════════════════════════════════════════════════════════════

with tab_manager:
    result = _get_result()
    if not result: _nodata()
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); score_map = _get_score_map(result)

        # 담당자별 집계
        mgr_data = defaultdict(lambda: {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0, "notices": []})
        for n in notices:
            mgr = n.manager or "미배정"
            sc = score_map.get(n.notice_id)
            grade = sc.priority_grade if sc else "D"
            mgr_data[mgr]["total"] += 1
            mgr_data[mgr][grade] += 1
            mgr_data[mgr]["notices"].append((n, sc))

        # KPI
        total_mgrs = len([m for m in mgr_data if m != "미배정"])
        unassigned = mgr_data.get("미배정", {}).get("total", 0)
        k1,k2,k3 = st.columns(3)
        k1.markdown(_kpi(total_mgrs, "배정 담당자"), unsafe_allow_html=True)
        k2.markdown(_kpi(len(notices) - unassigned, "배정 완료"), unsafe_allow_html=True)
        k3.markdown(_kpi(f'<span style="color:{RED_D}">{unassigned}</span>', "미배정"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # 담당자별 등급 분포 스택 바 차트
        if mgr_data:
            mgrs = sorted(mgr_data.keys(), key=lambda m: -mgr_data[m]["total"])
            fig = go.Figure()
            for grade, color in [("A", GREEN_A), ("B", BLUE_B), ("C", AMBER_C), ("D", RED_D)]:
                fig.add_trace(go.Bar(name=f"{grade}등급", x=mgrs, y=[mgr_data[m][grade] for m in mgrs], marker_color=color))
            fig.update_layout(title=dict(text="담당자별 공고 등급 분포", font=dict(color=TEXT_DARK)),
                              barmode='stack', height=400, legend=dict(orientation="h", y=1.12),
                              xaxis=dict(gridcolor=BORDER), yaxis=dict(title="공고 수", gridcolor=BORDER), **_layout())
            st.plotly_chart(fig, use_container_width=True)

        # 담당자별 상세 테이블
        st.markdown('<div class="section-title">담당자별 상세</div>', unsafe_allow_html=True)
        mgr_rows = []
        for mgr, data in sorted(mgr_data.items(), key=lambda x: -x[1]["total"]):
            mgr_rows.append({
                "담당자": mgr, "전체": data["total"],
                "A등급": data["A"], "B등급": data["B"], "C등급": data["C"], "D등급": data["D"],
                "A비율": f'{data["A"]/max(1,data["total"])*100:.0f}%'
            })
        st.dataframe(pd.DataFrame(mgr_rows), use_container_width=True, height=400)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 11: 수집 히스토리
# ═══════════════════════════════════════════════════════════════════════════════

with tab_history:
    history = st.session_state.get("collection_history", [])
    if not history:
        st.markdown(f"""
        <div style="text-align:center; padding:5rem 0;">
            <div style="font-size:2.5rem; font-weight:900; letter-spacing:-1px; margin-bottom:1rem;">
                <span style="color:{CHARCOAL};">INTER</span><span style="color:{ORANGE_500};">X</span>
            </div>
            <p style="color:{TEXT_MID}; font-size:1.05rem;">수집 히스토리가 없습니다</p>
            <p style="color:{TEXT_LIGHT}; font-size:0.85rem;">수집을 실행하면 결과가 여기에 기록됩니다</p>
        </div>""", unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go

        st.markdown(f'<div class="section-title">수집 히스토리 ({len(history)}회)</div>', unsafe_allow_html=True)

        # KPI: 최근 수집 vs 이전 수집 비교
        latest = history[-1]
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(_kpi(len(history), "총 수집 횟수"), unsafe_allow_html=True)
        k2.markdown(_kpi(latest["total"], "최근 수집건수"), unsafe_allow_html=True)
        k3.markdown(_kpi(latest["grades"].get("A", 0), "최근 A등급"), unsafe_allow_html=True)

        if len(history) >= 2:
            prev = history[-2]
            diff = latest["total"] - prev["total"]
            diff_str = f'+{diff}' if diff >= 0 else str(diff)
            diff_color = GREEN_A if diff > 0 else RED_D if diff < 0 else TEXT_MID
            k4.markdown(_kpi(f'<span style="color:{diff_color}">{diff_str}</span>', "이전 대비 증감"), unsafe_allow_html=True)
        else:
            k4.markdown(_kpi("-", "이전 대비 증감"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 히스토리 테이블 ──
        hist_rows = []
        for i, h in enumerate(reversed(history), 1):
            hist_rows.append({
                "#": i,
                "수집일시": h["timestamp"],
                "모드": h.get("mode", "-"),
                "전체": h["total"],
                "A등급": h["grades"].get("A", 0),
                "B등급": h["grades"].get("B", 0),
                "C등급": h["grades"].get("C", 0),
                "D등급": h["grades"].get("D", 0),
                "L3": h.get("l3_count", 0),
                "제안서": h.get("proposals", 0),
                "사이트수": len(h.get("sites", {})),
            })
        st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, height=300)

        # ── Excel 다운로드 ──
        try:
            hist_df = pd.DataFrame(hist_rows)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                hist_df.to_excel(w, index=False, sheet_name="수집히스토리")
            st.download_button("히스토리 Excel 다운로드", buf.getvalue(),
                               f"interx_히스토리_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            pass

        # ── 수집 추이 차트 (2회 이상일 때) ──
        if len(history) >= 2:
            st.markdown("<br>", unsafe_allow_html=True)
            col_trend, col_grade = st.columns(2)

            with col_trend:
                timestamps = [h["timestamp"][:16] for h in history]
                totals = [h["total"] for h in history]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=timestamps, y=totals, mode='lines+markers',
                                          name='전체 공고', line=dict(color=CYAN_400, width=3),
                                          marker=dict(size=10, color=CYAN_400)))
                a_counts = [h["grades"].get("A", 0) for h in history]
                fig.add_trace(go.Scatter(x=timestamps, y=a_counts, mode='lines+markers',
                                          name='A등급', line=dict(color=GREEN_A, width=2),
                                          marker=dict(size=8, color=GREEN_A)))
                fig.update_layout(title=dict(text="수집 건수 추이", font=dict(color=TEXT_DARK)),
                                  height=350, xaxis=dict(title="수집 일시", gridcolor=BORDER),
                                  yaxis=dict(title="공고 수", gridcolor=BORDER),
                                  legend=dict(orientation="h", y=1.12), **_layout())
                st.plotly_chart(fig, use_container_width=True)

            with col_grade:
                # 최근 2회 등급 비교 바 차트
                latest_g = history[-1]["grades"]
                prev_g = history[-2]["grades"]
                grades_list = ["A", "B", "C", "D"]
                fig = go.Figure()
                fig.add_trace(go.Bar(name="이전 수집", x=grades_list,
                                      y=[prev_g.get(g, 0) for g in grades_list],
                                      marker_color=TEXT_LIGHT))
                fig.add_trace(go.Bar(name="최근 수집", x=grades_list,
                                      y=[latest_g.get(g, 0) for g in grades_list],
                                      marker_color=[GREEN_A, CYAN_500, "#F59E0B", RED_D]))
                fig.update_layout(title=dict(text="최근 vs 이전 등급 비교", font=dict(color=TEXT_DARK)),
                                  height=350, barmode='group',
                                  xaxis=dict(title="등급", gridcolor=BORDER),
                                  yaxis=dict(title="공고 수", gridcolor=BORDER),
                                  legend=dict(orientation="h", y=1.12), **_layout())
                st.plotly_chart(fig, use_container_width=True)

            # ── 사이트별 변화 비교 ──
            if len(history) >= 2:
                st.markdown(f'<div class="section-title">사이트별 수집 변화 (최근 vs 이전)</div>', unsafe_allow_html=True)
                latest_sites = history[-1].get("sites", {})
                prev_sites = history[-2].get("sites", {})
                all_site_names = sorted(set(list(latest_sites.keys()) + list(prev_sites.keys())))
                if all_site_names:
                    site_rows = []
                    for s in all_site_names:
                        cur = latest_sites.get(s, 0)
                        prv = prev_sites.get(s, 0)
                        diff = cur - prv
                        site_rows.append({
                            "사이트": s, "최근": cur, "이전": prv,
                            "변화": f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "0",
                        })
                    st.dataframe(pd.DataFrame(site_rows), use_container_width=True, height=300)
