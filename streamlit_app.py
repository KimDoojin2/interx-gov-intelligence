"""
InterX Government Intelligence Engine — Streamlit Team App
팀원 배포용 원클릭 파이프라인 실행 앱 (v2 — 9개 탭)
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

if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# ── InterX 브랜드 색상 (화이트 테마) ──────────────────────────────────────────
CYAN_400 = "#00CFFF"; CYAN_500 = "#00B8E6"; CYAN_600 = "#009FCC"
NAVY_900 = "#0A1628"; NAVY_800 = "#0F1E35"
GOLD_400 = "#FFD700"; GREEN_A = "#22C55E"; RED_D = "#EF4444"; MAGENTA = "#FF0064"
TEXT_DARK = "#1F2937"; TEXT_MID = "#6B7280"; TEXT_LIGHT = "#9CA3AF"
BG_WHITE = "#FFFFFF"; BG_GRAY = "#F9FAFB"; BORDER = "#E5E7EB"
GRADE_COLORS = {"A": GREEN_A, "B": CYAN_500, "C": "#F59E0B", "D": RED_D}

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InterX 정부지원사업 인텔리전스",
    page_icon="", layout="wide", initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .stApp {{ background: {BG_WHITE}; }}
    section[data-testid="stSidebar"] {{ display: none; }}
    .interx-topbar {{
        background: {NAVY_900}; padding: 1rem 2rem; border-radius: 12px;
        margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between;
    }}
    .interx-topbar h1 {{ color: {CYAN_400}; font-size: 1.5rem; margin: 0; font-weight: 800; }}
    .interx-topbar .subtitle {{ color: white; opacity: 0.5; font-size: 0.8rem; margin: 0; }}
    .kpi-card {{
        background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 12px;
        padding: 1.2rem; text-align: center; transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .kpi-card:hover {{ border-color: {CYAN_400}; box-shadow: 0 4px 12px rgba(0,207,255,0.12); transform: translateY(-2px); }}
    .kpi-value {{ font-size: 2rem; font-weight: 800; color: {NAVY_900}; line-height: 1.2; }}
    .kpi-label {{ font-size: 0.8rem; color: {TEXT_MID}; margin-top: 0.3rem; }}
    .grade-a {{ color: {GREEN_A}; font-weight: 800; }}
    .grade-b {{ color: {CYAN_500}; font-weight: 700; }}
    .grade-c {{ color: #F59E0B; font-weight: 600; }}
    .grade-d {{ color: {RED_D}; font-weight: 600; }}
    .notice-card {{
        background: {BG_WHITE}; border: 1px solid {BORDER}; border-radius: 10px;
        padding: 0.9rem 1.2rem; margin-bottom: 0.6rem; transition: all 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .notice-card:hover {{ border-color: {CYAN_400}; box-shadow: 0 2px 8px rgba(0,207,255,0.1); }}
    .notice-title {{ color: {TEXT_DARK}; font-weight: 600; font-size: 0.95rem; margin-bottom: 0.3rem; }}
    .notice-meta {{ color: {TEXT_LIGHT}; font-size: 0.78rem; }}
    .section-title {{
        color: {TEXT_DARK}; font-weight: 700; font-size: 1.1rem;
        margin: 1.5rem 0 0.8rem; padding-bottom: 0.5rem;
        border-bottom: 2px solid {CYAN_400}; display: inline-block;
    }}
    .stProgress > div > div > div > div {{ background: linear-gradient(90deg, {CYAN_400}, {GREEN_A}); }}
    .stButton > button {{
        background: linear-gradient(135deg, {CYAN_500}, {CYAN_400}); color: white;
        font-weight: 700; border: none; border-radius: 8px; padding: 0.6rem 2rem; transition: all 0.3s;
    }}
    .stButton > button:hover {{ box-shadow: 0 4px 15px rgba(0,207,255,0.35); transform: translateY(-1px); }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 0; background: {BG_GRAY}; border-radius: 10px; padding: 4px; border: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab"] {{ color: {TEXT_MID}; border-radius: 8px; padding: 8px 16px; font-weight: 600; font-size: 0.85rem; }}
    .stTabs [aria-selected="true"] {{ background: {BG_WHITE}; color: {CYAN_600}; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}}
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
    base = dict(paper_bgcolor=BG_WHITE, plot_bgcolor=BG_GRAY, font_color=TEXT_DARK,
                margin=dict(t=50, b=40, l=40, r=20))
    base.update(kw)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
#  헤더 + 탭
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="interx-topbar">
    <div><h1>InterX 정부지원사업 인텔리전스</h1><p class="subtitle">BD팀 공고 자동 수집 및 분석 플랫폼</p></div>
    <div style="color:white; opacity:0.3; font-size:0.75rem;">v4.5 | 16개 사이트 | 23개 분석</div>
</div>
""", unsafe_allow_html=True)

tab_dash, tab_run, tab_notices, tab_proposal, tab_compete, \
tab_predict, tab_calendar, tab_solution, tab_keyword, tab_manager = st.tabs([
    "대시보드", "수집 실행", "공고 목록", "제안서", "경쟁사 분석",
    "수주 예측", "마감 캘린더", "솔루션 매칭", "키워드 트렌드", "담당자 현황",
])

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False

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
            <p style="font-size:3.5rem; margin:0;">&#x1F50D;</p>
            <p style="color:{TEXT_MID}; font-size:1.1rem; margin-top:1rem;">아직 데이터가 없습니다</p>
            <p style="color:{TEXT_LIGHT}; font-size:0.9rem;">위의 <b>수집 실행</b> 탭을 눌러 공고 수집을 시작하세요</p>
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
                marker_colors=[GREEN_A, CYAN_500, "#F59E0B", RED_D],
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
                                    marker_color=CYAN_400, marker_line_color=CYAN_500, marker_line_width=1))
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
                status.update(label=f"완료! {len(nn)}건 수집", state="complete")
                time.sleep(1); st.rerun()
            except Exception as e:
                status.update(label=f"오류: {e}", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback; st.code(traceback.format_exc())
                st.session_state.pipeline_running = False


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 3: 공고 목록
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
            st.dataframe(df, use_container_width=True, height=600)

            # 다운로드 버튼 (CSV + Excel)
            dl1, dl2, _ = st.columns([1,1,4])
            dl1.download_button("CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                                f"interx_공고_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w: df.to_excel(w, index=False, sheet_name="공고목록")
                dl2.download_button("Excel 다운로드", buf.getvalue(),
                                    f"interx_공고_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: pass
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
                                   marker_color=[RED_D, "#F59E0B", GOLD_400, CYAN_500, GREEN_A]))
            fig.update_layout(title=dict(text="수주 확률 분포", font=dict(color=TEXT_DARK)),
                              height=350, xaxis=dict(title="확률 구간"), yaxis=dict(title="공고 수", gridcolor=BORDER), **_layout())
            st.plotly_chart(fig, use_container_width=True)

        with col_top:
            st.markdown('<div class="section-title">수주 유망 TOP 10</div>', unsafe_allow_html=True)
            for p in predictions[:10]:
                n, sc, wp = p["notice"], p["sc"], p["win_prob"]
                color = GREEN_A if wp >= 60 else CYAN_500 if wp >= 40 else "#F59E0B"
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
                RED_D if _calc_dday(d) <= 3 else "#F59E0B" if _calc_dday(d) <= 7 else CYAN_400 for d in dates]))
            fig.update_layout(title=dict(text="마감일별 공고 수 (30일)", font=dict(color=TEXT_DARK)),
                              height=300, xaxis=dict(title="마감일"), yaxis=dict(title="공고 수", gridcolor=BORDER), **_layout())
            st.plotly_chart(fig, use_container_width=True)

        # 긴급 마감 리스트
        st.markdown(f'<div class="section-title">긴급 마감 공고 (D-7 이내, {d7}건)</div>', unsafe_allow_html=True)
        for u in upcoming:
            if u["dday"] > 7: break
            n, sc, dd = u["notice"], u["sc"], u["dday"]
            grade = sc.priority_grade if sc else "D"
            color = RED_D if dd <= 3 else "#F59E0B"
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
                                                fill='toself', fillcolor=f'rgba(0,207,255,0.15)',
                                                line=dict(color=CYAN_400, width=2),
                                                marker=dict(size=6, color=CYAN_400)))
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
                fig.add_trace(go.Bar(x=names, y=avgs, name="평균 점수", marker_color=CYAN_400))
                fig.add_trace(go.Bar(x=names, y=counts, name="매칭 공고 수", marker_color="#F59E0B"))
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
                                       orientation='h', marker_color=CYAN_400))
                fig.update_layout(title=dict(text="매칭 키워드 TOP 20 (스코어링)", font=dict(color=TEXT_DARK)),
                                  height=500, xaxis=dict(title="출현 횟수", gridcolor=BORDER), **_layout(margin=dict(l=120,r=20,t=50,b=40)))
                st.plotly_chart(fig, use_container_width=True)

        with col_title:
            if title_words:
                top20t = title_words.most_common(20)
                fig = go.Figure(go.Bar(y=[k[0] for k in reversed(top20t)], x=[k[1] for k in reversed(top20t)],
                                       orientation='h', marker_color="#F59E0B"))
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
            for grade, color in [("A", GREEN_A), ("B", CYAN_500), ("C", "#F59E0B"), ("D", RED_D)]:
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
