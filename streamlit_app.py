"""
InterX Government Intelligence Engine — Streamlit Team App
팀원 배포용 원클릭 파이프라인 실행 앱
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

import streamlit as st

# ── 프로젝트 경로 설정 ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Windows 콘솔 UTF-8
if hasattr(sys.stdout, "buffer") and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── .env 로드 ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# ── InterX 브랜드 색상 ────────────────────────────────────────────────────────
NAVY_900 = "#0A1628"
NAVY_800 = "#0F1E35"
NAVY_700 = "#152742"
CYAN_400 = "#00CFFF"
CYAN_500 = "#00B8E6"
GOLD_400 = "#FFD700"
GREEN_A  = "#00FF88"
RED_D    = "#FF6B6B"
MAGENTA  = "#FF0064"
TEXT     = "#E2E8F0"

GRADE_COLORS = {"A": GREEN_A, "B": CYAN_400, "C": GOLD_400, "D": RED_D}

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InterX 정부지원사업 인텔리전스",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 커스텀 CSS (InterX 다크 테마) ─────────────────────────────────────────────
st.markdown(f"""
<style>
    /* 메인 배경 */
    .stApp {{
        background: linear-gradient(180deg, {NAVY_900} 0%, {NAVY_800} 100%);
    }}

    /* 사이드바 */
    section[data-testid="stSidebar"] {{
        background: {NAVY_800};
        border-right: 1px solid {NAVY_700};
    }}

    /* 헤더 영역 */
    .interx-header {{
        background: linear-gradient(135deg, {NAVY_800}, {NAVY_700});
        border: 1px solid {NAVY_700};
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }}
    .interx-header h1 {{
        color: {CYAN_400};
        font-size: 2rem;
        margin: 0;
    }}
    .interx-header p {{
        color: {TEXT};
        opacity: 0.7;
        margin: 0.5rem 0 0;
    }}

    /* KPI 카드 */
    .kpi-card {{
        background: rgba(15,30,53,0.8);
        backdrop-filter: blur(12px);
        border: 1px solid {NAVY_700};
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        transition: all 0.3s ease;
    }}
    .kpi-card:hover {{
        border-color: {CYAN_400};
        box-shadow: 0 0 20px rgba(0,207,255,0.15);
    }}
    .kpi-value {{
        font-size: 2.2rem;
        font-weight: 800;
        color: {CYAN_400};
        line-height: 1.2;
    }}
    .kpi-label {{
        font-size: 0.85rem;
        color: {TEXT};
        opacity: 0.6;
        margin-top: 0.3rem;
    }}

    /* 등급 뱃지 */
    .grade-a {{ color: {GREEN_A}; font-weight: 800; }}
    .grade-b {{ color: {CYAN_400}; font-weight: 700; }}
    .grade-c {{ color: {GOLD_400}; font-weight: 600; }}
    .grade-d {{ color: {RED_D}; font-weight: 600; }}

    /* 공고 카드 */
    .notice-card {{
        background: rgba(15,30,53,0.6);
        border: 1px solid {NAVY_700};
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        transition: border-color 0.2s;
    }}
    .notice-card:hover {{
        border-color: {CYAN_400};
    }}
    .notice-title {{
        color: white;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.4rem;
    }}
    .notice-meta {{
        color: {TEXT};
        opacity: 0.5;
        font-size: 0.8rem;
    }}

    /* 프로그레스 */
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, {CYAN_400}, {GREEN_A});
    }}

    /* 버튼 */
    .stButton > button {{
        background: linear-gradient(135deg, {CYAN_500}, {CYAN_400});
        color: {NAVY_900};
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        transition: all 0.3s;
    }}
    .stButton > button:hover {{
        box-shadow: 0 0 25px rgba(0,207,255,0.4);
        transform: translateY(-1px);
    }}

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {NAVY_800};
        border-radius: 10px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT};
        border-radius: 8px;
        padding: 8px 20px;
    }}
    .stTabs [aria-selected="true"] {{
        background: {NAVY_700};
        color: {CYAN_400};
    }}

    /* 테이블 */
    .stDataFrame {{
        border-radius: 10px;
        overflow: hidden;
    }}

    /* 로그 영역 */
    .log-area {{
        background: {NAVY_900};
        border: 1px solid {NAVY_700};
        border-radius: 8px;
        padding: 1rem;
        font-family: 'Consolas', monospace;
        font-size: 0.8rem;
        color: {TEXT};
        max-height: 400px;
        overflow-y: auto;
    }}

    /* 숨김 */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  유틸 함수
# ═══════════════════════════════════════════════════════════════════════════════

def _grade_badge(grade: str) -> str:
    css = f"grade-{grade.lower()}" if grade in "ABCD" else "grade-d"
    return f'<span class="{css}">{grade}</span>'


def _calc_dday(deadline: str) -> int:
    try:
        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
        return (dl - date.today()).days
    except (ValueError, TypeError):
        return -1


def _kpi_card(value, label):
    return f"""
    <div class="kpi-card">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """


# ═══════════════════════════════════════════════════════════════════════════════
#  사이드바
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 1rem 0;">
        <h2 style="color:{CYAN_400}; margin:0;">InterX</h2>
        <p style="color:{TEXT}; opacity:0.5; font-size:0.85rem;">정부지원사업 인텔리전스 엔진</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "메뉴",
        ["대시보드", "수집 실행", "공고 목록", "제안서", "경쟁사 분석"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # 실행 설정
    st.markdown(f'<p style="color:{CYAN_400}; font-weight:600;">파이프라인 설정</p>',
                unsafe_allow_html=True)

    run_mode = st.selectbox("실행 모드", ["일반 수집 (빠름)", "전체 분석 (클러스터+알림)", "테스트 (Mock 데이터)"])

    # 사이트 선택
    all_sites = [
        "bizinfo", "kiat", "nipa", "innopolis", "bipa", "uipa",
        "gicon", "ttp", "dicia", "gjtp", "kised", "ketep",
        "koiia", "jejutp", "smart_factory", "iitp",
    ]
    selected_sites = st.multiselect(
        "수집 사이트",
        all_sites,
        default=all_sites,
        help="수집할 사이트를 선택하세요",
    )

    max_pages = st.slider("사이트당 최대 페이지", 1, 10, 5)
    enable_sheets = st.toggle("Google Sheets 업로드", value=True)

    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center; opacity:0.4; font-size:0.75rem;">
        <p>InterX Engine v4.5</p>
        <p>16개 사이트 | 23개 분석 | 106개 테스트</p>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  세션 상태 초기화
# ═══════════════════════════════════════════════════════════════════════════════

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "run_log" not in st.session_state:
    st.session_state.run_log = []


# ═══════════════════════════════════════════════════════════════════════════════
#  파이프라인 실행 함수
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(sites, max_pg, mode, sheets_on):
    """파이프라인을 실행하고 결과를 session_state에 저장."""
    from interx_engine.infrastructure.config.settings_loader import settings
    settings.ensure_dirs()

    dry_run = "테스트" in mode
    full = "전체" in mode

    from run_engine import build_collectors, build_sheet_gateway, MultiCollectorAdapter, main as run_main

    result = run_main(
        site_keys=sites if len(sites) < len(all_sites) else None,
        max_pages=max_pg,
        enable_sheets=sheets_on,
        full_pipeline=full,
        dry_run=dry_run,
        no_alert=True,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  페이지: 대시보드
# ═══════════════════════════════════════════════════════════════════════════════

if page == "대시보드":
    st.markdown(f"""
    <div class="interx-header">
        <h1>InterX 정부지원사업 인텔리전스</h1>
        <p>BD팀을 위한 정부지원사업 공고 자동 수집 및 분석 플랫폼</p>
    </div>
    """, unsafe_allow_html=True)

    result = st.session_state.pipeline_result

    if result:
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])
        score_map = {s.notice_id: s for s in score_cards}

        # 통계 계산
        total = len(notices)
        grades = {"A": 0, "B": 0, "C": 0, "D": 0}
        l3_count = 0
        urgent_count = 0

        for n in notices:
            sc = score_map.get(n.notice_id)
            if sc:
                grades[sc.priority_grade] = grades.get(sc.priority_grade, 0) + 1
            if getattr(n, "l3_strong", "N") == "Y":
                l3_count += 1
            dday = _calc_dday(n.deadline_date or "")
            if 0 <= dday <= 7:
                urgent_count += 1

        # KPI 카드
        cols = st.columns(6)
        kpis = [
            (total, "전체 공고"),
            (f'<span style="color:{GREEN_A}">{grades["A"]}</span>', "A등급"),
            (f'<span style="color:{CYAN_400}">{grades["B"]}</span>', "B등급"),
            (f'<span style="color:{MAGENTA}">{l3_count}</span>', "L3 강공고"),
            (f'<span style="color:{RED_D}">{urgent_count}</span>', "7일내 마감"),
            (len(result.get("proposal_files", [])), "제안서 생성"),
        ]
        for col, (val, label) in zip(cols, kpis):
            col.markdown(_kpi_card(val, label), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 등급 분포 차트 + A등급 공고 리스트
        col_chart, col_list = st.columns([1, 2])

        with col_chart:
            import plotly.graph_objects as go

            fig = go.Figure(data=[go.Pie(
                labels=["A등급", "B등급", "C등급", "D등급"],
                values=[grades["A"], grades["B"], grades["C"], grades["D"]],
                marker_colors=[GREEN_A, CYAN_400, GOLD_400, RED_D],
                hole=0.55,
                textinfo="label+value",
                textfont=dict(color="white", size=14),
            )])
            fig.update_layout(
                title=dict(text="등급 분포", font=dict(color=CYAN_400, size=16)),
                paper_bgcolor=NAVY_800,
                plot_bgcolor=NAVY_800,
                font_color=TEXT,
                showlegend=False,
                height=350,
                margin=dict(t=50, b=20, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_list:
            st.markdown(f'<p style="color:{CYAN_400}; font-weight:700; font-size:1.1rem;">'
                        f'A등급 핵심 공고 ({grades["A"]}건)</p>',
                        unsafe_allow_html=True)

            a_notices = []
            for n in notices:
                sc = score_map.get(n.notice_id)
                if sc and sc.priority_grade == "A":
                    a_notices.append((n, sc))

            a_notices.sort(key=lambda x: x[1].priority_score, reverse=True)

            for n, sc in a_notices[:10]:
                dday = _calc_dday(n.deadline_date or "")
                dday_str = f"D-{dday}" if dday >= 0 else "마감"
                l3 = ' <span style="color:#FF0064; font-weight:700;">[L3]</span>' if getattr(n, "l3_strong", "N") == "Y" else ""

                st.markdown(f"""
                <div class="notice-card">
                    <div class="notice-title">
                        <span class="grade-a">A</span> {n.title[:60]}{l3}
                    </div>
                    <div class="notice-meta">
                        {n.site} | {n.agency or n.ministry or '-'} |
                        점수: {sc.priority_score:.0f} |
                        {dday_str} | {n.deadline_date or '-'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # 사이트별 수집 현황
        st.markdown(f'<p style="color:{CYAN_400}; font-weight:700; font-size:1.1rem; margin-top:1rem;">'
                    f'사이트별 수집 현황</p>', unsafe_allow_html=True)

        from collections import Counter
        site_counter = Counter(n.site for n in notices)
        sites_sorted = site_counter.most_common()

        if sites_sorted:
            fig2 = go.Figure(data=[go.Bar(
                x=[s[0] for s in sites_sorted],
                y=[s[1] for s in sites_sorted],
                marker_color=CYAN_400,
                marker_line_color=CYAN_500,
                marker_line_width=1,
            )])
            fig2.update_layout(
                paper_bgcolor=NAVY_800,
                plot_bgcolor=NAVY_900,
                font_color=TEXT,
                height=300,
                margin=dict(t=20, b=40, l=40, r=20),
                xaxis=dict(gridcolor=NAVY_700),
                yaxis=dict(gridcolor=NAVY_700, title="공고 수"),
            )
            st.plotly_chart(fig2, use_container_width=True)

    else:
        # 파이프라인 미실행 상태
        st.markdown(f"""
        <div style="text-align:center; padding:4rem 0;">
            <p style="font-size:4rem; margin:0;">&#x1F50D;</p>
            <p style="color:{TEXT}; font-size:1.2rem; opacity:0.6;">
                아직 데이터가 없습니다. 왼쪽 메뉴에서 <b>수집 실행</b>을 눌러 시작하세요
            </p>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  페이지: 수집 실행
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "수집 실행":
    st.markdown(f"""
    <div class="interx-header">
        <h1>공고 수집 실행</h1>
        <p>버튼을 누르면 정부지원사업 공고를 자동으로 수집합니다</p>
    </div>
    """, unsafe_allow_html=True)

    # 설정 요약
    col1, col2, col3 = st.columns(3)
    col1.markdown(_kpi_card(len(selected_sites), "선택된 사이트"), unsafe_allow_html=True)
    col2.markdown(_kpi_card(max_pages, "최대 페이지"), unsafe_allow_html=True)
    if "일반" in run_mode:
        mode_label = "일반 수집"
    elif "전체" in run_mode:
        mode_label = "전체 분석"
    else:
        mode_label = "테스트"
    col3.markdown(_kpi_card(mode_label, "실행 모드"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 실행 버튼
    col_btn, col_status = st.columns([1, 2])

    with col_btn:
        run_clicked = st.button(
            "수집 시작",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.pipeline_running,
        )

    with col_status:
        if st.session_state.pipeline_result:
            r = st.session_state.pipeline_result
            n_count = len(r.get("notices", []))
            st.success(f"마지막 실행: {n_count}건 수집 완료")

    if run_clicked:
        st.session_state.pipeline_running = True
        st.session_state.run_log = []

        with st.status("공고 수집 중...", expanded=True) as status:
            st.write(f"실행 모드: **{run_mode}**")
            st.write(f"수집 사이트: **{len(selected_sites)}**개 선택")
            st.write(f"사이트당 최대: **{max_pages}**페이지")
            st.write("---")

            progress = st.progress(0, text="엔진 초기화 중...")

            try:
                # Step 1: 초기화
                progress.progress(5, text="설정 로딩 중...")
                st.write("설정 및 구성 파일 로드...")

                from interx_engine.infrastructure.config.settings_loader import settings
                settings.ensure_dirs()

                # Step 2: 빌드
                progress.progress(10, text="수집기 구성 중...")
                st.write(f"{len(selected_sites)}개 수집기 생성 중...")

                dry_run = "테스트" in run_mode
                full = "전체" in run_mode

                from run_engine import build_collectors, build_sheet_gateway, MultiCollectorAdapter

                collectors = build_collectors(
                    selected_sites if len(selected_sites) < 16 else None,
                    max_pages,
                    dry_run=dry_run,
                )
                st.write(f"**{len(collectors)}**개 수집기 생성 완료")

                multi = MultiCollectorAdapter(collectors, max_workers=8)
                sheet_gw = build_sheet_gateway(enable_sheets)

                # Step 3: 파이프라인 실행
                progress.progress(20, text="파이프라인 실행 중...")
                st.write("파이프라인 실행 시작...")

                execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")

                if full:
                    from interx_engine.application.orchestrators.full_pipeline import FullPipelineOrchestrator
                    orch = FullPipelineOrchestrator(
                        collector=multi,
                        base_dir=str(ROOT),
                        sheet_gateway=sheet_gw,
                    )
                else:
                    from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
                    orch = DailyPipelineOrchestrator(
                        collector=multi,
                        sheet_gateway=sheet_gw,
                    )

                # 알림 비활성화
                os.environ.pop("TELEGRAM_BOT_TOKEN", None)
                os.environ.pop("SLACK_WEBHOOK_URL", None)

                result = orch.run(execution_id)

                progress.progress(90, text="결과 정리 중...")

                notices = result.get("notices", [])
                score_cards = result.get("score_cards", [])

                # 등급 카운트
                grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
                sc_map = {s.notice_id: s for s in score_cards}
                for n in notices:
                    sc = sc_map.get(n.notice_id)
                    if sc:
                        grade_counts[sc.priority_grade] = grade_counts.get(sc.priority_grade, 0) + 1

                st.write(f"**{len(notices)}**건 공고 수집 완료")
                st.write(f"등급: A={grade_counts['A']}건 | B={grade_counts['B']}건 "
                         f"| C={grade_counts['C']}건 | D={grade_counts['D']}건")

                proposals = result.get("proposal_files", [])
                if proposals:
                    st.write(f"**{len(proposals)}**건 제안서 초안 생성")

                progress.progress(100, text="완료!")
                st.session_state.pipeline_result = result
                status.update(label=f"완료! {len(notices)}건 수집", state="complete")

            except Exception as e:
                status.update(label=f"오류: {e}", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback
                st.code(traceback.format_exc())

            finally:
                st.session_state.pipeline_running = False

    # 마지막 실행 결과 요약
    if st.session_state.pipeline_result and not run_clicked:
        result = st.session_state.pipeline_result
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])

        st.markdown(f"""
        <div style="background:{NAVY_800}; border:1px solid {NAVY_700}; border-radius:12px;
             padding:1.5rem; margin-top:1rem;">
            <p style="color:{CYAN_400}; font-weight:700; font-size:1.1rem;">마지막 실행 요약</p>
            <p style="color:{TEXT};">수집 공고: <b>{len(notices)}</b>건 | 스코어카드: <b>{len(score_cards)}</b>건</p>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  페이지: 공고 목록
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "공고 목록":
    st.markdown(f"""
    <div class="interx-header">
        <h1>수집된 공고 목록</h1>
        <p>수집된 정부지원사업 공고를 필터링하고 검색할 수 있습니다</p>
    </div>
    """, unsafe_allow_html=True)

    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행을 해주세요.")
    else:
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])
        sc_map = {s.notice_id: s for s in score_cards}

        # 필터
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            grade_filter = st.multiselect("등급 필터", ["A", "B", "C", "D"], default=["A", "B", "C", "D"])
        with col_f2:
            site_filter = st.multiselect("사이트 필터", sorted(set(n.site for n in notices)))
        with col_f3:
            search = st.text_input("검색", placeholder="키워드를 입력하세요...")

        # 필터 적용
        filtered = []
        for n in notices:
            sc = sc_map.get(n.notice_id)
            grade = sc.priority_grade if sc else "D"
            if grade not in grade_filter:
                continue
            if site_filter and n.site not in site_filter:
                continue
            if search and search.lower() not in (n.title or "").lower():
                continue
            filtered.append((n, sc))

        # 정렬: 등급 → 점수 순
        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        filtered.sort(key=lambda x: (grade_order.get(x[1].priority_grade if x[1] else "D", 3),
                                      -(x[1].priority_score if x[1] else 0)))

        st.markdown(f'<p style="color:{TEXT}; opacity:0.6;">필터 결과: {len(filtered)} / {len(notices)}건</p>',
                    unsafe_allow_html=True)

        # 데이터프레임으로 표시
        import pandas as pd

        rows = []
        for n, sc in filtered:
            dday = _calc_dday(n.deadline_date or "")
            rows.append({
                "등급": sc.priority_grade if sc else "D",
                "점수": f"{sc.priority_score:.0f}" if sc else "-",
                "공고명": n.title[:70] if n.title else "-",
                "주관기관": n.agency or n.ministry or "-",
                "사이트": n.site,
                "마감일": n.deadline_date or "-",
                "D-day": dday if dday >= 0 else "마감",
                "L3": "Y" if getattr(n, "l3_strong", "N") == "Y" else "",
                "예산": n.budget or "-",
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                height=600,
                column_config={
                    "등급": st.column_config.TextColumn(width="small"),
                    "점수": st.column_config.TextColumn(width="small"),
                    "공고명": st.column_config.TextColumn(width="large"),
                    "L3": st.column_config.TextColumn(width="small"),
                },
            )

            # CSV 다운로드
            csv_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSV 다운로드",
                csv_data,
                file_name=f"interx_공고목록_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.warning("필터 조건에 맞는 공고가 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
#  페이지: 제안서
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "제안서":
    st.markdown(f"""
    <div class="interx-header">
        <h1>자동 생성 제안서</h1>
        <p>A/B 등급 공고에 대해 자동 생성된 제안서 초안을 다운로드하세요</p>
    </div>
    """, unsafe_allow_html=True)

    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행을 해주세요.")
    else:
        proposals = result.get("proposal_files", [])

        if not proposals:
            st.warning("생성된 제안서가 없습니다. A/B 등급 공고가 포함된 수집을 실행해주세요.")
        else:
            st.markdown(f'<p style="color:{CYAN_400}; font-weight:600;">'
                        f'총 {len(proposals)}건 제안서 생성 완료</p>',
                        unsafe_allow_html=True)

            for p in proposals:
                fp = Path(p)
                if fp.exists():
                    col_name, col_size, col_dl = st.columns([4, 1, 1])
                    col_name.markdown(f"""
                    <div class="notice-card">
                        <div class="notice-title">{fp.name}</div>
                        <div class="notice-meta">{fp.stat().st_size:,} bytes</div>
                    </div>
                    """, unsafe_allow_html=True)

                    with open(fp, "rb") as f:
                        col_dl.download_button(
                            "다운로드",
                            f.read(),
                            file_name=fp.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{fp.name}",
                        )


# ═══════════════════════════════════════════════════════════════════════════════
#  페이지: 경쟁사 분석
# ═══════════════════════════════════════════════════════════════════════════════

elif page == "경쟁사 분석":
    st.markdown(f"""
    <div class="interx-header">
        <h1>경쟁사 인텔리전스</h1>
        <p>정부지원사업 공고에서 경쟁사 활동을 추적하고 분석합니다</p>
    </div>
    """, unsafe_allow_html=True)

    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행을 해주세요.")
    else:
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])

        if notices:
            try:
                from interx_engine.application.use_cases.competitor_report import generate_competitor_report

                with st.spinner("경쟁사 리포트 생성 중..."):
                    comp_result = generate_competitor_report(notices, score_cards)

                summary = comp_result.get("summary", {})
                comp_notices = comp_result.get("competitor_notices", [])

                # KPI
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(_kpi_card(summary.get("total_notices", 0), "전체 공고"), unsafe_allow_html=True)
                c2.markdown(_kpi_card(summary.get("competitor_related", 0), "경쟁사 관련"), unsafe_allow_html=True)
                c3.markdown(_kpi_card(f'{summary.get("competitor_ratio", 0)}%', "경쟁 비율"), unsafe_allow_html=True)
                c4.markdown(_kpi_card(summary.get("tier1_count", 0), "Tier1 탐지"), unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # TOP 경쟁사
                top_comps = summary.get("top_competitors", [])
                if top_comps:
                    import plotly.graph_objects as go

                    names = [c[0] for c in top_comps[:10]]
                    counts = [c[1] for c in top_comps[:10]]

                    fig = go.Figure(data=[go.Bar(
                        x=counts,
                        y=names,
                        orientation='h',
                        marker_color=CYAN_400,
                    )])
                    fig.update_layout(
                        title=dict(text="경쟁사 탐지 순위 TOP 10", font=dict(color=CYAN_400)),
                        paper_bgcolor=NAVY_800,
                        plot_bgcolor=NAVY_900,
                        font_color=TEXT,
                        height=400,
                        margin=dict(l=120, r=20, t=50, b=20),
                        yaxis=dict(autorange="reversed"),
                        xaxis=dict(gridcolor=NAVY_700, title="탐지 횟수"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # 경쟁사 관련 공고 목록
                if comp_notices:
                    st.markdown(f'<p style="color:{CYAN_400}; font-weight:700; font-size:1.1rem;">'
                                f'경쟁사 관련 공고 ({len(comp_notices)}건)</p>',
                                unsafe_allow_html=True)

                    import pandas as pd
                    comp_rows = []
                    for cn in comp_notices:
                        comp_rows.append({
                            "등급": cn["grade"],
                            "공고명": cn["title"][:60],
                            "사이트": cn["site"],
                            "마감일": cn["deadline"] or "-",
                            "경쟁사": " / ".join(cn["competitors"]),
                            "Tier": " / ".join(cn["tiers"]),
                        })
                    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, height=400)

                # 차트 이미지
                chart_path = comp_result.get("chart_path", "")
                if chart_path and Path(chart_path).exists():
                    st.image(str(chart_path), caption="경쟁사 종합 분석 차트")

            except Exception as e:
                st.error(f"경쟁사 리포트 생성 실패: {e}")
