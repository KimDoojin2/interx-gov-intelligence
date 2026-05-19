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

# ── InterX 브랜드 색상 (화이트 테마) ──────────────────────────────────────────
CYAN_400 = "#00CFFF"
CYAN_500 = "#00B8E6"
CYAN_600 = "#009FCC"
NAVY_900 = "#0A1628"
NAVY_800 = "#0F1E35"
GOLD_400 = "#FFD700"
GREEN_A  = "#22C55E"
RED_D    = "#EF4444"
MAGENTA  = "#FF0064"
TEXT_DARK = "#1F2937"
TEXT_MID  = "#6B7280"
TEXT_LIGHT = "#9CA3AF"
BG_WHITE = "#FFFFFF"
BG_GRAY  = "#F9FAFB"
BORDER   = "#E5E7EB"

GRADE_COLORS = {"A": GREEN_A, "B": CYAN_500, "C": "#F59E0B", "D": RED_D}

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InterX 정부지원사업 인텔리전스",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 커스텀 CSS (화이트 + InterX 시안 포인트) ──────────────────────────────────
st.markdown(f"""
<style>
    /* 메인 배경 */
    .stApp {{
        background: {BG_WHITE};
    }}

    /* 사이드바 숨김 — 탭으로 대체 */
    section[data-testid="stSidebar"] {{
        display: none;
    }}

    /* 상단 헤더 바 */
    .interx-topbar {{
        background: {NAVY_900};
        padding: 1rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .interx-topbar h1 {{
        color: {CYAN_400};
        font-size: 1.5rem;
        margin: 0;
        font-weight: 800;
    }}
    .interx-topbar .subtitle {{
        color: white;
        opacity: 0.5;
        font-size: 0.8rem;
        margin: 0;
    }}

    /* KPI 카드 */
    .kpi-card {{
        background: {BG_WHITE};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}
    .kpi-card:hover {{
        border-color: {CYAN_400};
        box-shadow: 0 4px 12px rgba(0,207,255,0.12);
        transform: translateY(-2px);
    }}
    .kpi-value {{
        font-size: 2rem;
        font-weight: 800;
        color: {NAVY_900};
        line-height: 1.2;
    }}
    .kpi-label {{
        font-size: 0.8rem;
        color: {TEXT_MID};
        margin-top: 0.3rem;
    }}

    /* 등급 뱃지 */
    .grade-a {{ color: {GREEN_A}; font-weight: 800; }}
    .grade-b {{ color: {CYAN_500}; font-weight: 700; }}
    .grade-c {{ color: #F59E0B; font-weight: 600; }}
    .grade-d {{ color: {RED_D}; font-weight: 600; }}

    /* 공고 카드 */
    .notice-card {{
        background: {BG_WHITE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 0.9rem 1.2rem;
        margin-bottom: 0.6rem;
        transition: all 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .notice-card:hover {{
        border-color: {CYAN_400};
        box-shadow: 0 2px 8px rgba(0,207,255,0.1);
    }}
    .notice-title {{
        color: {TEXT_DARK};
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.3rem;
    }}
    .notice-meta {{
        color: {TEXT_LIGHT};
        font-size: 0.78rem;
    }}

    /* 섹션 타이틀 */
    .section-title {{
        color: {TEXT_DARK};
        font-weight: 700;
        font-size: 1.1rem;
        margin: 1.5rem 0 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid {CYAN_400};
        display: inline-block;
    }}

    /* 프로그레스 */
    .stProgress > div > div > div > div {{
        background: linear-gradient(90deg, {CYAN_400}, {GREEN_A});
    }}

    /* 버튼 */
    .stButton > button {{
        background: linear-gradient(135deg, {CYAN_500}, {CYAN_400});
        color: white;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        transition: all 0.3s;
    }}
    .stButton > button:hover {{
        box-shadow: 0 4px 15px rgba(0,207,255,0.35);
        transform: translateY(-1px);
    }}

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: {BG_GRAY};
        border-radius: 10px;
        padding: 4px;
        border: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT_MID};
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        background: {BG_WHITE};
        color: {CYAN_600};
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}

    /* 설정 패널 */
    .settings-panel {{
        background: {BG_GRAY};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
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
#  상단 헤더
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="interx-topbar">
    <div>
        <h1>InterX 정부지원사업 인텔리전스</h1>
        <p class="subtitle">BD팀 공고 자동 수집 및 분석 플랫폼</p>
    </div>
    <div style="color:white; opacity:0.3; font-size:0.75rem;">
        v4.5 | 16개 사이트 | 23개 분석
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 네비게이션 (사이드바 대체)
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "대시보드", "수집 실행", "공고 목록", "제안서", "경쟁사 분석"
])

# ═══════════════════════════════════════════════════════════════════════════════
#  세션 상태 초기화
# ═══════════════════════════════════════════════════════════════════════════════

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False

# 사이트 목록
all_sites = [
    "bizinfo", "kiat", "nipa", "innopolis", "bipa", "uipa",
    "gicon", "ttp", "dicia", "gjtp", "kised", "ketep",
    "koiia", "jejutp", "smart_factory", "iitp",
]


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 1: 대시보드
# ═══════════════════════════════════════════════════════════════════════════════

with tab1:
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
            (f'<span style="color:{CYAN_500}">{grades["B"]}</span>', "B등급"),
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
                marker_colors=[GREEN_A, CYAN_500, "#F59E0B", RED_D],
                hole=0.55,
                textinfo="label+value",
                textfont=dict(color=TEXT_DARK, size=13),
            )])
            fig.update_layout(
                title=dict(text="등급 분포", font=dict(color=TEXT_DARK, size=16)),
                paper_bgcolor=BG_WHITE,
                plot_bgcolor=BG_WHITE,
                font_color=TEXT_DARK,
                showlegend=False,
                height=350,
                margin=dict(t=50, b=20, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_list:
            st.markdown(f'<div class="section-title">A등급 핵심 공고 ({grades["A"]}건)</div>',
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
        st.markdown('<div class="section-title">사이트별 수집 현황</div>', unsafe_allow_html=True)

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
                paper_bgcolor=BG_WHITE,
                plot_bgcolor=BG_GRAY,
                font_color=TEXT_DARK,
                height=300,
                margin=dict(t=20, b=40, l=40, r=20),
                xaxis=dict(gridcolor=BORDER),
                yaxis=dict(gridcolor=BORDER, title="공고 수"),
            )
            st.plotly_chart(fig2, use_container_width=True)

    else:
        st.markdown(f"""
        <div style="text-align:center; padding:5rem 0;">
            <p style="font-size:3.5rem; margin:0;">&#x1F50D;</p>
            <p style="color:{TEXT_MID}; font-size:1.1rem; margin-top:1rem;">
                아직 데이터가 없습니다
            </p>
            <p style="color:{TEXT_LIGHT}; font-size:0.9rem;">
                위의 <b>수집 실행</b> 탭을 눌러 공고 수집을 시작하세요
            </p>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 2: 수집 실행
# ═══════════════════════════════════════════════════════════════════════════════

with tab2:
    # 설정 패널
    st.markdown('<div class="section-title">수집 설정</div>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        run_mode = st.selectbox("실행 모드", ["일반 수집 (빠름)", "전체 분석 (클러스터+알림)", "테스트 (Mock 데이터)"])
    with col_s2:
        max_pages = st.slider("사이트당 최대 페이지", 1, 10, 5)
    with col_s3:
        enable_sheets = st.toggle("Google Sheets 업로드", value=True)

    with st.expander("수집 사이트 선택 (기본: 전체 16개)", expanded=False):
        selected_sites = st.multiselect(
            "사이트",
            all_sites,
            default=all_sites,
            help="수집할 사이트를 선택하세요",
            label_visibility="collapsed",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 설정 요약 KPI
    col1, col2, col3 = st.columns(3)
    col1.markdown(_kpi_card(len(selected_sites) if 'selected_sites' in dir() else 16, "선택된 사이트"), unsafe_allow_html=True)
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
        sites_to_use = selected_sites if 'selected_sites' in dir() else all_sites

        with st.status("공고 수집 중...", expanded=True) as status:
            st.write(f"실행 모드: **{run_mode}**")
            st.write(f"수집 사이트: **{len(sites_to_use)}**개")
            st.write(f"사이트당 최대: **{max_pages}**페이지")
            st.write("---")

            progress = st.progress(0, text="엔진 초기화 중...")

            try:
                progress.progress(5, text="설정 로딩 중...")
                st.write("설정 및 구성 파일 로드...")

                from interx_engine.infrastructure.config.settings_loader import settings
                settings.ensure_dirs()

                progress.progress(10, text="수집기 구성 중...")
                st.write(f"{len(sites_to_use)}개 수집기 생성 중...")

                dry_run = "테스트" in run_mode
                full = "전체" in run_mode

                from run_engine import build_collectors, build_sheet_gateway, MultiCollectorAdapter

                collectors = build_collectors(
                    sites_to_use if len(sites_to_use) < 16 else None,
                    max_pages,
                    dry_run=dry_run,
                )
                st.write(f"**{len(collectors)}**개 수집기 생성 완료")

                multi = MultiCollectorAdapter(collectors, max_workers=8)
                sheet_gw = build_sheet_gateway(enable_sheets)

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

                os.environ.pop("TELEGRAM_BOT_TOKEN", None)
                os.environ.pop("SLACK_WEBHOOK_URL", None)

                result = orch.run(execution_id)

                progress.progress(90, text="결과 정리 중...")

                notices = result.get("notices", [])
                score_cards = result.get("score_cards", [])

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
                st.session_state.pipeline_running = False
                status.update(label=f"완료! {len(notices)}건 수집", state="complete")

                # 완료 후 페이지 새로고침 → 대시보드에 결과 표시
                time.sleep(1)
                st.rerun()

            except Exception as e:
                status.update(label=f"오류: {e}", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback
                st.code(traceback.format_exc())
    # 마지막 실행 결과 요약
    if st.session_state.pipeline_result and not run_clicked:
        result = st.session_state.pipeline_result
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])

        st.markdown(f"""
        <div style="background:{BG_GRAY}; border:1px solid {BORDER}; border-radius:12px;
             padding:1.5rem; margin-top:1rem;">
            <p style="color:{TEXT_DARK}; font-weight:700; font-size:1rem;">마지막 실행 요약</p>
            <p style="color:{TEXT_MID};">수집 공고: <b>{len(notices)}</b>건 | 스코어카드: <b>{len(score_cards)}</b>건</p>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  탭 3: 공고 목록
# ═══════════════════════════════════════════════════════════════════════════════

with tab3:
    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행 탭에서 수집을 시작해주세요.")
    else:
        notices = result.get("notices", [])
        score_cards = result.get("score_cards", [])
        sc_map = {s.notice_id: s for s in score_cards}

        # 필터
        st.markdown('<div class="section-title">필터</div>', unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            grade_filter = st.multiselect("등급", ["A", "B", "C", "D"], default=["A", "B", "C", "D"])
        with col_f2:
            site_filter = st.multiselect("사이트", sorted(set(n.site for n in notices)))
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

        grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
        filtered.sort(key=lambda x: (grade_order.get(x[1].priority_grade if x[1] else "D", 3),
                                      -(x[1].priority_score if x[1] else 0)))

        st.markdown(f'<p style="color:{TEXT_MID}; font-size:0.85rem;">필터 결과: {len(filtered)} / {len(notices)}건</p>',
                    unsafe_allow_html=True)

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
#  탭 4: 제안서
# ═══════════════════════════════════════════════════════════════════════════════

with tab4:
    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행 탭에서 수집을 시작해주세요.")
    else:
        proposals = result.get("proposal_files", [])

        if not proposals:
            st.warning("생성된 제안서가 없습니다. A/B 등급 공고가 포함된 수집을 실행해주세요.")
        else:
            st.markdown(f'<div class="section-title">자동 생성 제안서 ({len(proposals)}건)</div>',
                        unsafe_allow_html=True)

            for p in proposals:
                fp = Path(p)
                if fp.exists():
                    col_name, col_dl = st.columns([5, 1])
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
#  탭 5: 경쟁사 분석
# ═══════════════════════════════════════════════════════════════════════════════

with tab5:
    result = st.session_state.pipeline_result

    if not result:
        st.info("데이터가 없습니다. 먼저 수집 실행 탭에서 수집을 시작해주세요.")
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
                        title=dict(text="경쟁사 탐지 순위 TOP 10", font=dict(color=TEXT_DARK)),
                        paper_bgcolor=BG_WHITE,
                        plot_bgcolor=BG_GRAY,
                        font_color=TEXT_DARK,
                        height=400,
                        margin=dict(l=120, r=20, t=50, b=20),
                        yaxis=dict(autorange="reversed"),
                        xaxis=dict(gridcolor=BORDER, title="탐지 횟수"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                if comp_notices:
                    st.markdown(f'<div class="section-title">경쟁사 관련 공고 ({len(comp_notices)}건)</div>',
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

                chart_path = comp_result.get("chart_path", "")
                if chart_path and Path(chart_path).exists():
                    st.image(str(chart_path), caption="경쟁사 종합 분석 차트")

            except Exception as e:
                st.error(f"경쟁사 리포트 생성 실패: {e}")
