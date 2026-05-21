"""
InterX Government Intelligence Engine — Enterprise Dashboard v5
"""
from __future__ import annotations

import io, json, os, re, sys, time
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# NOTE: sys.stdout TextIOWrapper 교체 제거
# Streamlit Cloud (Python 3.14) 에서 교체 시 로깅 핸들러가
# closed stream 참조하여 "I/O operation on closed file" 에러 발생

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════════════════════
#  Design System — interxlab.com 공식 팔레트 기반
# ═══════════════════════════════════════════════════════════════════════════════
P = "#FF8000"       # --accent-color (interxlab.com 공식 오렌지)
P_L = "#FF9F2E"     # accent light
P_D = "#E67300"     # accent dark
P_BG = "rgba(255,128,0,0.05)"
A2 = "#3A7BEE"      # --accent2-color (interxlab.com 공식 블루)
BK = "#000000"      # --primary-color (블랙)
CH = "#333333"      # --secondary-color
S8 = "#1A1A1A"      # near-black
S7 = "#444444"
S5 = "#666666"      # muted text
S4 = "#999999"
S3 = "#CCCCCC"
S2 = "#DDDDDD"      # border
S1 = "#F5F5F5"      # --bg-sub-color 근사
S0 = "#F7F7F7"      # --bg-sub-color
W = "#FFFFFF"
GA = "#059669"; GB = "#2563EB"; GC = "#D97706"; GD = "#DC2626"
GRADE = {"A": GA, "B": GB, "C": GC, "D": GD}

# ── Page Config ──
st.set_page_config(page_title="InterX Intelligence", page_icon="🔶", layout="wide", initial_sidebar_state="collapsed")

# ── Intro (CSS only — Streamlit은 <script> 미실행) ──
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = True
    st.markdown('<style>@keyframes ix-fade{0%{opacity:0;transform:scale(.85) translateY(14px)}15%{opacity:1;transform:scale(1.02)}40%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(.97) translateY(-8px)}}@keyframes ix-bg{0%,70%{opacity:1}100%{opacity:0;pointer-events:none;visibility:hidden}}.ix-intro{position:fixed;inset:0;z-index:99999;background:#000;display:flex;align-items:center;justify-content:center;animation:ix-bg 2.4s ease forwards}.ix-intro .logo{animation:ix-fade 2.4s ease forwards;text-align:center}.ix-intro .mark{font-size:3rem;font-weight:900;letter-spacing:-2px;font-family:Inter,system-ui,sans-serif}.ix-intro .mark b{color:#FF8000}.ix-intro .mark span{color:#fff}.ix-intro .sub{color:rgba(255,255,255,.4);font-size:.78rem;letter-spacing:4px;margin-top:10px;font-weight:500}</style><div class="ix-intro"><div class="logo"><div class="mark"><span>INTER</span><b>X</b></div><div class="sub">INTELLIGENCE ENGINE</div></div></div>', unsafe_allow_html=True)

# ── Enterprise CSS ──
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Global ── */
.stApp{{background:{W};font-family:'Inter',system-ui,-apple-system,sans-serif}}
section[data-testid="stSidebar"]{{display:none}}
#MainMenu,footer,header{{visibility:hidden}}

/* ── Top Navigation Bar — interxlab.com 스타일 ── */
.nav-bar{{
    background:{BK};border-radius:0;padding:16px 32px;margin:-1rem -1rem 28px;
    display:flex;align-items:center;justify-content:space-between;
}}
.nav-bar .brand{{font-size:1.3rem;font-weight:900;letter-spacing:-1px}}
.nav-bar .brand span{{color:#fff}} .nav-bar .brand b{{color:{P}}}
.nav-bar .meta{{color:rgba(255,255,255,.3);font-size:.72rem;font-weight:500;letter-spacing:.8px}}

/* ── Metric Card — interxlab.com 호버 글로우 ── */
.m-card{{
    background:{W};border:1px solid {S2};border-radius:12px;padding:20px 18px;
    box-shadow:0 1px 2px rgba(0,0,0,.03);position:relative;overflow:hidden;
    transition:all .3s ease;
}}
.m-card::after{{
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:{P};transform:scaleX(0);transform-origin:left;transition:transform .3s ease;
}}
.m-card:hover{{border-color:{P};box-shadow:2px 2px 20px rgba(255,128,0,.15);transform:translateY(-2px)}}
.m-card:hover::after{{transform:scaleX(1)}}
.m-val{{font-size:1.75rem;font-weight:800;color:{CH};line-height:1.15;letter-spacing:-.5px}}
.m-label{{font-size:.7rem;color:{S5};margin-top:6px;font-weight:600;text-transform:uppercase;letter-spacing:.8px}}

/* ── Section Header ── */
.sec-h{{
    display:flex;align-items:center;gap:10px;margin:28px 0 16px;
}}
.sec-h .dot{{width:4px;height:20px;border-radius:2px;background:{P}}}
.sec-h .txt{{font-size:.92rem;font-weight:700;color:{CH};letter-spacing:-.2px}}

/* ── Notice Row ── */
.n-row{{
    background:{W};border:1px solid {S2};border-radius:12px;padding:14px 18px;margin-bottom:8px;
    border-left:3px solid transparent;transition:all .2s ease;cursor:default;
    display:flex;align-items:center;gap:14px;
}}
.n-row:hover{{border-left-color:{P};background:{S0};box-shadow:0 2px 8px rgba(0,0,0,.03)}}
.n-badge{{
    min-width:36px;height:28px;display:inline-flex;align-items:center;justify-content:center;
    border-radius:6px;font-size:.78rem;font-weight:800;color:{W};flex-shrink:0;
}}
.n-title{{font-size:.88rem;font-weight:600;color:{S8};flex:1;line-height:1.35}}
.n-meta{{font-size:.73rem;color:{S4};font-weight:500}}

/* ── Status Pill ── */
.pill{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600}}
.pill-a{{background:#ECFDF5;color:#065F46}} .pill-b{{background:#EFF6FF;color:#1E40AF}}
.pill-c{{background:#FFFBEB;color:#92400E}} .pill-d{{background:#FEF2F2;color:#991B1B}}
.pill-l3{{background:#FDF2F8;color:#9D174D}}
.pill-urgent{{background:#FEF2F2;color:#DC2626;border:1px solid #FECACA}}

/* ── Data Table Override ── */
.stDataFrame{{border-radius:12px;overflow:hidden;border:1px solid {S2}}}
.stDataFrame [data-testid="stDataFrameResizable"]{{border-radius:12px}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{{gap:2px;background:{S0};border-radius:12px;padding:4px;border:1px solid {S2}}}
.stTabs [data-baseweb="tab"]{{color:{S5};border-radius:10px;padding:10px 20px;font-weight:600;font-size:.8rem;transition:all .15s}}
.stTabs [data-baseweb="tab"]:hover{{color:{P};background:{P_BG}}}
.stTabs [aria-selected="true"]{{background:{W};color:{P_D};font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.06)}}

/* ── Button — interxlab.com 스타일 ── */
.stButton>button{{
    background:{BK};color:{W};font-weight:700;border:none;border-radius:8px;
    padding:.65rem 2rem;font-size:.85rem;letter-spacing:.3px;transition:all .3s ease;
}}
.stButton>button:hover{{background:{P};box-shadow:2px 2px 20px rgba(255,128,0,.3);transform:translateY(-1px)}}

/* ── Progress ── */
.stProgress>div>div>div>div{{background:linear-gradient(90deg,{P},{P_L});border-radius:4px}}

/* ── Inputs ── */
.stSelectbox label,.stMultiSelect label,.stSlider label{{font-weight:600;color:{S8};font-size:.82rem}}

/* ── Empty State ── */
.empty{{text-align:center;padding:4.5rem 0}}
.empty .icon{{font-size:2.2rem;margin-bottom:12px;opacity:.6}}
.empty .heading{{font-size:1rem;font-weight:700;color:{CH};margin-bottom:6px}}
.empty .desc{{font-size:.85rem;color:{S5};line-height:1.5}}
.empty .action{{display:inline-block;margin-top:16px;padding:8px 20px;background:{P};color:{W};border-radius:8px;font-size:.82rem;font-weight:600;text-decoration:none}}

/* ── Hero Banner ── */
.hero-banner{{
    position:relative;margin:-28px -1rem 28px;overflow:hidden;
    height:220px;background:#000;
}}
.hero-banner img{{
    width:100%;height:100%;object-fit:cover;object-position:center 60%;
    opacity:.85;display:block;
}}
.hero-overlay{{
    position:absolute;inset:0;display:flex;flex-direction:column;
    align-items:center;justify-content:center;
    background:linear-gradient(180deg,rgba(0,0,0,.25) 0%,rgba(0,0,0,.55) 100%);
}}
.hero-overlay .hero-brand{{
    font-size:3.2rem;font-weight:900;letter-spacing:-2px;
    font-family:'Inter',system-ui,sans-serif;
    text-shadow:0 2px 24px rgba(0,0,0,.6);
}}
.hero-overlay .hero-brand span{{color:#fff}}
.hero-overlay .hero-brand b{{color:{P}}}
.hero-overlay .hero-sub{{
    color:rgba(255,255,255,.55);font-size:.82rem;letter-spacing:5px;
    margin-top:8px;font-weight:500;text-shadow:0 1px 8px rgba(0,0,0,.5);
}}
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _dday(dl: str) -> int:
    try: return (datetime.strptime(dl, "%Y-%m-%d").date() - date.today()).days
    except: return -1

def _metric(val, label, accent=""):
    ac = f' style="color:{accent}"' if accent else ""
    return f'<div class="m-card"><div class="m-val"{ac}>{val}</div><div class="m-label">{label}</div></div>'

def _section(title):
    return f'<div class="sec-h"><div class="dot"></div><div class="txt">{title}</div></div>'

def _badge(grade):
    c = GRADE.get(grade, S5)
    return f'<span class="n-badge" style="background:{c}">{grade}</span>'

def _pill(text, variant="a"):
    return f'<span class="pill pill-{variant}">{text}</span>'

def _notice_row(grade, title, meta, extra=""):
    return f'<div class="n-row">{_badge(grade)}<div style="flex:1"><div class="n-title">{title}</div><div class="n-meta">{meta}</div></div>{extra}</div>'

def _empty(icon, heading, desc, action_label="", action_hint=""):
    a = f'<div class="action">{action_label}</div>' if action_label else ""
    return f'<div class="empty"><div class="icon">{icon}</div><div class="heading">{heading}</div><div class="desc">{desc}</div>{a}</div>'

def _result():
    return st.session_state.get("pipeline_result")

def _smap(result):
    return {s.notice_id: s for s in result.get("score_cards", [])}

def _layout(**kw):
    base = dict(paper_bgcolor=W, plot_bgcolor=S0, font=dict(color=S8, family="Inter,system-ui,sans-serif", size=12),
                margin=dict(t=40, b=36, l=36, r=16), hoverlabel=dict(bgcolor=CH, font_color=W, font_size=12))
    base.update(kw); return base

# ═══════════════════════════════════════════════════════════════════════════════
#  Navigation
# ═══════════════════════════════════════════════════════════════════════════════

HERO_IMG = "https://raw.githubusercontent.com/KimDoojin2/interx-gov-intelligence/master/assets/hero_earth.png"

st.markdown(f"""<div class="nav-bar">
    <div><div class="brand"><span>INTER</span><b>X</b></div></div>
    <div class="meta">INTELLIGENCE ENGINE &nbsp;·&nbsp; v5.5 &nbsp;·&nbsp; 25 SITES &nbsp;·&nbsp; 23 ANALYTICS</div>
</div>
<div class="hero-banner">
    <img src="{HERO_IMG}" alt="InterX Hero">
    <div class="hero-overlay">
        <div class="hero-brand"><span>INTER</span><b>X</b></div>
        <div class="hero-sub">GOVERNMENT INTELLIGENCE ENGINE</div>
    </div>
</div>""", unsafe_allow_html=True)

tab_dash, tab_run, tab_notices, tab_proposal, tab_compete, \
tab_predict, tab_calendar, tab_solution, tab_keyword, tab_manager, tab_history, tab_news = st.tabs([
    "📊 대시보드", "⚡ 수집 실행", "📋 공고 목록", "📝 제안서", "🏢 경쟁사",
    "🎯 수주 예측", "📅 마감 캘린더", "🔧 솔루션", "📈 키워드", "👤 담당자", "🕐 히스토리", "🤖 AI 뉴스",
])

for key, default in [("pipeline_result", None), ("pipeline_running", False),
                      ("collection_history", []), ("selected_notice_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

ALL_SITES = ["bizinfo","kiat","nipa","innopolis","bipa","uipa","gicon","ttp","gjtp","kised","ketep","koiia","jejutp","smart_factory","iitp",
             "seoultp","gdtp","gwtp","sjtp","cbtp","ctp","btp","utp","gntp","ptp"]

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 · Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    result = _result()
    if not result:
        st.markdown(_empty("📡", "데이터를 수집해주세요",
                           "⚡ 수집 실행 탭에서 파이프라인을 실행하면<br>정부지원사업 공고를 자동으로 분석합니다.",
                           "수집 실행 →"), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); smap = _smap(result)
        total = len(notices)
        gr = {"A":0,"B":0,"C":0,"D":0}
        l3c = urg = 0
        for n in notices:
            sc = smap.get(n.notice_id)
            if sc: gr[sc.priority_grade] = gr.get(sc.priority_grade, 0) + 1
            if getattr(n, "l3_strong", "N") == "Y": l3c += 1
            dd = _dday(n.deadline_date or "")
            if 0 <= dd <= 7: urg += 1

        # ── 🔴 D-day 긴급 배너 (D-3 이내) ──
        _urgent3 = [(n, smap.get(n.notice_id)) for n in notices
                     if 0 <= _dday(n.deadline_date or "") <= 3 and smap.get(n.notice_id)]
        if _urgent3:
            _urgent3.sort(key=lambda x: _dday(x[0].deadline_date or ""))
            _urg_html = ''.join(f'<span style="margin-right:18px">🔴 <b>{n.title[:40]}</b> <span style="color:#DC2626;font-weight:800">D-{_dday(n.deadline_date or "")}</span> ({n.site})</span>' for n, sc in _urgent3[:5])
            st.markdown(f'<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:12px;padding:14px 20px;margin-bottom:16px;font-size:.84rem;color:#991B1B;overflow-x:auto;white-space:nowrap"><b>⚠️ 긴급 마감 공고</b>&nbsp;&nbsp;{_urg_html}</div>', unsafe_allow_html=True)

        c1,c2,c3,c4,c5,c6 = st.columns(6)
        for col, (v, l, ac) in zip([c1,c2,c3,c4,c5,c6], [
            (total, "전체 공고", ""), (gr["A"], "A등급 · 핵심", GA), (gr["B"], "B등급 · 검토", GB),
            (l3c, "L3 강공고", "#DB2777"), (urg, "7일내 마감", GD),
            (len(result.get("proposal_files", [])), "제안서 생성", ""),
        ]): col.markdown(_metric(v, l, ac), unsafe_allow_html=True)

        # ── 🔍 키워드 빠른 검색 ──
        _qk = st.text_input("🔍 공고 키워드 검색", placeholder="AI, 스마트공장, 디지털트윈 ...", key="dash_search")
        if _qk:
            _qr = [(n, smap[n.notice_id]) for n in notices
                    if _qk.lower() in (n.title or "").lower() and smap.get(n.notice_id)]
            _qr.sort(key=lambda x: -x[1].priority_score)
            if _qr:
                st.markdown(f'<p style="font-size:.82rem;color:{S5}">검색 결과 <b style="color:{CH}">{len(_qr)}</b>건</p>', unsafe_allow_html=True)
                for n, sc in _qr[:10]:
                    dd = _dday(n.deadline_date or "")
                    pills = _pill(sc.priority_grade, sc.priority_grade.lower())
                    if 0 <= dd <= 3: pills += " " + _pill(f"D-{dd}", "urgent")
                    meta = f"{n.site} · {sc.priority_score:.0f}점 · {n.deadline_date or '-'} · {n.budget or '-'}"
                    st.markdown(_notice_row(sc.priority_grade, n.title[:60], meta, pills), unsafe_allow_html=True)
            else:
                st.info(f"'{_qk}' 관련 공고가 없습니다.")

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        col_chart, col_list = st.columns([1, 2])

        with col_chart:
            fig = go.Figure(go.Pie(
                labels=["A등급","B등급","C등급","D등급"], values=[gr["A"],gr["B"],gr["C"],gr["D"]],
                marker_colors=[GA,GB,GC,GD], hole=.6, textinfo="label+value",
                textfont=dict(color=S8, size=12), hoverinfo="label+percent+value"))
            fig.update_layout(title=dict(text="등급 분포", font=dict(size=14, color=S8)),
                              showlegend=False, height=340, **_layout())
            st.plotly_chart(fig, width="stretch")

        with col_list:
            st.markdown(_section(f"A등급 핵심 공고 ({gr['A']}건)"), unsafe_allow_html=True)
            a_sorted = sorted([(n, smap[n.notice_id]) for n in notices
                               if smap.get(n.notice_id) and smap[n.notice_id].priority_grade == "A"],
                              key=lambda x: -x[1].priority_score)
            for _ai, (n, sc) in enumerate(a_sorted[:8]):
                dd = _dday(n.deadline_date or "")
                extra_pills = ""
                if getattr(n, "l3_strong", "N") == "Y": extra_pills += _pill("L3", "l3") + " "
                if 0 <= dd <= 3: extra_pills += _pill(f"D-{dd}", "urgent")
                meta = f"{n.site} · {n.agency or n.ministry or '-'} · 점수 {sc.priority_score:.0f} · {n.deadline_date or '-'}"
                st.markdown(_notice_row("A", n.title[:65], meta, extra_pills), unsafe_allow_html=True)
                # ── 공고 요약 펼쳐보기 ──
                with st.expander("📄 공고 요약 보기", expanded=False):
                    # ── 예산 + 진행 판단 ──
                    _budget_raw = getattr(n, "budget", "") or ""
                    _budget_val = None
                    if _budget_raw:
                        try:
                            _bm = re.search(r'(\d[\d,.]*)\s*억', _budget_raw)
                            if _bm: _budget_val = float(_bm.group(1).replace(",",""))
                            else:
                                _bm2 = re.search(r'(\d[\d,.]*)\s*백만', _budget_raw)
                                if _bm2: _budget_val = float(_bm2.group(1).replace(",","")) / 100
                                else:
                                    _bm3 = re.search(r'(\d[\d,.]*)\s*만', _budget_raw)
                                    if _bm3: _budget_val = float(_bm3.group(1).replace(",","")) / 10000
                        except: pass
                    if _budget_val is not None:
                        if _budget_val >= 2.1:
                            _bdg_label = f"💰 **예산: {_budget_raw}**"
                            _bdg_action = '<span style="background:#059669;color:#fff;padding:2px 10px;border-radius:12px;font-size:.78rem;font-weight:700">🏢 인터엑스 직접 진행</span>'
                        else:
                            _bdg_label = f"💰 **예산: {_budget_raw}**"
                            _bdg_action = '<span style="background:#D97706;color:#fff;padding:2px 10px;border-radius:12px;font-size:.78rem;font-weight:700">🤝 파트너사 이관</span>'
                    elif _budget_raw:
                        _bdg_label = f"💰 **예산: {_budget_raw}**"
                        _bdg_action = ""
                    else:
                        _bdg_label = "💰 **예산: 미확인**"
                        _bdg_action = ""

                    _ec1, _ec2 = st.columns(2)
                    _ec1.markdown(f"**기관**: {n.agency or n.ministry or '-'}")
                    _ec2.markdown(f"**마감**: {n.deadline_date or '-'}" + (f" (D-{dd})" if dd >= 0 else ""))
                    _ec3, _ec4 = st.columns(2)
                    _ec3.markdown(f"**적합도**: {sc.fitness_score:.0f}점 · **우선순위**: {sc.priority_score:.0f}점")
                    _ec4.markdown(f"**수주확률**: {getattr(sc,'win_probability','-')}")
                    # 예산 + 진행방식
                    st.markdown(f"{_bdg_label} {_bdg_action}", unsafe_allow_html=True)
                    # 매칭 키워드
                    if sc.positive_keywords:
                        st.markdown("**매칭 키워드**: " + " ".join(f"`{k}`" for k in sc.positive_keywords[:15]))
                    # 솔루션 점수
                    sol_hits = [(s, v) for s, v in (sc.solution_scores or {}).items() if v > 0]
                    if sol_hits:
                        st.markdown("**추천 솔루션**: " + " · ".join(f"{s} ({v:.0f})" for s, v in sorted(sol_hits, key=lambda x:-x[1])[:4]))
                    # 구조화 요약 (사업목적/지원내용)
                    _struct = getattr(n, "structured", None) or {}
                    for _sk, _sl in [("사업목적","🎯 사업목적"), ("지원내용","💰 지원내용"), ("지원대상","👥 지원대상")]:
                        _sv = _struct.get(_sk, "")
                        if _sv: st.markdown(f"**{_sl}**: {_sv[:200]}")
                    # 본문 미리보기
                    _body = getattr(n, "body_text", "") or ""
                    if _body and not _struct:
                        st.markdown(f"**본문 미리보기**: {_body[:300]}...")
                    # 원문 사이트 미리보기 (바로 표시)
                    _detail = getattr(n, "detail_url", "") or ""
                    if _detail and _detail.startswith("http"):
                        st.markdown(f"[🔗 원문 바로가기]({_detail})")
                        import streamlit.components.v1 as components
                        components.iframe(_detail, height=480, scrolling=True)

        # ── 💡 오늘의 추천 공고 (A/B + 예산 2.1억+ + D-7~30) ──
        _rec = []
        for n in notices:
            sc = smap.get(n.notice_id)
            if not sc or sc.priority_grade not in ("A","B"): continue
            dd = _dday(n.deadline_date or "")
            if not (3 <= dd <= 30): continue
            _bgt_r = getattr(n, "budget", "") or ""
            _bv = None
            try:
                _m = re.search(r'(\d[\d,.]*)\s*억', _bgt_r)
                if _m: _bv = float(_m.group(1).replace(",",""))
            except: pass
            _rec.append((n, sc, dd, _bv))
        _rec.sort(key=lambda x: -x[1].priority_score)
        if _rec:
            st.markdown(_section(f"💡 오늘의 추천 공고 ({len(_rec[:5])}건)"), unsafe_allow_html=True)
            st.markdown(f'<p style="font-size:.75rem;color:{S4}">A/B등급 · D-3~30일 마감 · 점수 순</p>', unsafe_allow_html=True)
            for n, sc, dd, bv in _rec[:5]:
                pills = _pill(sc.priority_grade, sc.priority_grade.lower())
                if bv and bv >= 2.1: pills += f' <span style="background:#059669;color:#fff;padding:1px 8px;border-radius:10px;font-size:.68rem;font-weight:700">{bv:.0f}억</span>'
                elif bv: pills += f' <span style="background:#D97706;color:#fff;padding:1px 8px;border-radius:10px;font-size:.68rem;font-weight:700">{bv:.1f}억→파트너</span>'
                meta = f"{n.site} · {sc.priority_score:.0f}점 · D-{dd} · {n.agency or n.ministry or '-'}"
                st.markdown(_notice_row(sc.priority_grade, n.title[:60], meta, pills), unsafe_allow_html=True)

        st.markdown(_section("사이트별 수집 현황"), unsafe_allow_html=True)
        sc_cnt = Counter(n.site for n in notices).most_common()
        if sc_cnt:
            fig2 = go.Figure(go.Bar(x=[s[0] for s in sc_cnt], y=[s[1] for s in sc_cnt],
                                    marker_color=P, marker_line_width=0))
            fig2.update_layout(height=260, xaxis=dict(gridcolor=S2), yaxis=dict(gridcolor=S2, title="건수"), **_layout())
            st.plotly_chart(fig2, width="stretch")

        # ── 🏆 솔루션별 TOP3 공고 ──
        _sol_names = ["ManufacturingDT","RecipeAI","QualityAI","InspectionAI","SafetyAI","GenAI","InfraDS","PdM"]
        _sol_display = {"ManufacturingDT":"제조DT","RecipeAI":"레시피AI","QualityAI":"품질AI",
                        "InspectionAI":"검사AI","SafetyAI":"안전AI","GenAI":"GenAI","InfraDS":"인프라DS","PdM":"예지보전"}
        _sol_data = {s: [] for s in _sol_names}
        for n in notices:
            sc = smap.get(n.notice_id)
            if not sc or not sc.solution_scores: continue
            for s in _sol_names:
                v = sc.solution_scores.get(s, 0)
                if v > 0: _sol_data[s].append((n, sc, v))
        for s in _sol_names:
            _sol_data[s].sort(key=lambda x: -x[2])
        _active_sols = [(s, _sol_data[s]) for s in _sol_names if _sol_data[s]]
        if _active_sols:
            st.markdown(_section("🏆 솔루션별 TOP3 공고"), unsafe_allow_html=True)
            _sc1, _sc2 = st.columns(2)
            for _si, (s, items) in enumerate(_active_sols):
                with (_sc1 if _si % 2 == 0 else _sc2):
                    st.markdown(f'<div style="font-size:.85rem;font-weight:700;color:{P};margin:12px 0 6px">🔧 {_sol_display.get(s,s)}</div>', unsafe_allow_html=True)
                    for n, sc, v in items[:3]:
                        st.markdown(f'<div style="font-size:.8rem;color:{S8};padding:3px 0">{_pill(sc.priority_grade, sc.priority_grade.lower())} {n.title[:45]} <span style="color:{S4}">({v:.0f}점)</span></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 · Pipeline Runner
# ═══════════════════════════════════════════════════════════════════════════════

with tab_run:
    st.markdown(_section("수집 설정"), unsafe_allow_html=True)
    # ── st.form 으로 감싸서 selectbox 변경 시 탭 리셋 방지 ──
    with st.form("pipeline_form", border=False):
        cs1, cs2, cs3 = st.columns(3)
        with cs1: run_mode = st.selectbox("실행 모드", ["일반 수집 (빠름)", "전체 분석 (클러스터+알림)", "테스트 (Mock 데이터)"], key="run_mode_sel")
        with cs2: max_pages = st.slider("사이트당 최대 페이지", 1, 10, 5, key="max_pages_sel")
        with cs3: enable_sheets = st.toggle("Google Sheets 업로드", value=True, key="sheets_sel")
        with st.expander("수집 사이트 선택", expanded=False):
            selected_sites = st.multiselect("사이트", ALL_SITES, default=ALL_SITES, key="sel_sites", label_visibility="collapsed")
        ml = "일반" if "일반" in run_mode else "전체" if "전체" in run_mode else "테스트"

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.markdown(_metric(len(selected_sites), "선택 사이트"), unsafe_allow_html=True)
        c2.markdown(_metric(max_pages, "최대 페이지"), unsafe_allow_html=True)
        c3.markdown(_metric(ml, "실행 모드"), unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        run_clicked = st.form_submit_button("⚡ 수집 시작", type="primary", disabled=st.session_state.pipeline_running, use_container_width=True)

    if st.session_state.pipeline_result:
        st.success(f"✓ 마지막 실행: {len(st.session_state.pipeline_result.get('notices',[]))}건 수집 완료")

    if run_clicked:
        st.session_state.pipeline_running = True
        sites_to_use = selected_sites if selected_sites else ALL_SITES
        with st.status("수집 파이프라인 실행 중...", expanded=True) as status:
            st.write(f"**{run_mode}** · {len(sites_to_use)}개 사이트 · {max_pages}페이지/사이트")
            progress = st.progress(0, text="엔진 초기화...")
            try:
                # ── Streamlit Cloud Python 3.14: stderr/stdout closed 문제 방지 ──
                import logging as _logging
                _root = _logging.getLogger()
                for _h in list(_root.handlers):
                    _root.removeHandler(_h)
                _root.addHandler(_logging.StreamHandler(stream=open(os.devnull, "w")))
                _root.setLevel(_logging.INFO)

                progress.progress(5, text="설정 로딩...")
                from interx_engine.infrastructure.config.settings_loader import settings
                settings.ensure_dirs()
                progress.progress(10, text="수집기 구성...")
                dry_run = "테스트" in run_mode; full = "전체" in run_mode
                from run_engine import build_collectors, build_sheet_gateway, MultiCollectorAdapter
                collectors = build_collectors(sites_to_use if len(sites_to_use) < 16 else None, max_pages, dry_run=dry_run)
                st.write(f"✓ **{len(collectors)}**개 수집기 생성")
                multi = MultiCollectorAdapter(collectors, max_workers=8)
                sheet_gw = build_sheet_gateway(enable_sheets)
                progress.progress(20, text="파이프라인 실행...")
                execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")
                if full:
                    from interx_engine.application.orchestrators.full_pipeline import FullPipelineOrchestrator
                    orch = FullPipelineOrchestrator(collector=multi, base_dir=str(ROOT), sheet_gateway=sheet_gw)
                else:
                    from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
                    orch = DailyPipelineOrchestrator(collector=multi, sheet_gateway=sheet_gw)
                os.environ.pop("TELEGRAM_BOT_TOKEN", None); os.environ.pop("SLACK_WEBHOOK_URL", None)
                result = orch.run(execution_id)
                progress.progress(90, text="결과 정리...")
                nn = result.get("notices", []); scs = result.get("score_cards", [])
                gc = {"A":0,"B":0,"C":0,"D":0}; sm = {s.notice_id: s for s in scs}
                for n in nn:
                    sc = sm.get(n.notice_id)
                    if sc: gc[sc.priority_grade] = gc.get(sc.priority_grade,0)+1
                st.write(f"✓ **{len(nn)}**건 · A={gc['A']} B={gc['B']} C={gc['C']} D={gc['D']}")
                pp = result.get("proposal_files", [])
                if pp: st.write(f"✓ **{len(pp)}**건 제안서 생성")
                progress.progress(100, text="완료")
                st.session_state.pipeline_result = result
                st.session_state.pipeline_running = False
                history_entry = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "execution_id": execution_id, "total": len(nn), "grades": dict(gc),
                    "sites": dict(Counter(n.site for n in nn)), "proposals": len(pp),
                    "mode": ml, "l3_count": sum(1 for n in nn if getattr(n, "l3_strong", "N") == "Y")}
                st.session_state.collection_history.append(history_entry)
                status.update(label=f"✓ 완료 — {len(nn)}건 수집", state="complete")
                time.sleep(1); st.rerun()
            except Exception as e:
                status.update(label=f"오류 발생", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback; st.code(traceback.format_exc())
                st.session_state.pipeline_running = False


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 · Notice List + Detail
# ═══════════════════════════════════════════════════════════════════════════════

with tab_notices:
    result = _result()
    if not result:
        st.markdown(_empty("📋", "공고 데이터 없음", "수집 실행 후 이 탭에서 공고를 조회할 수 있습니다."), unsafe_allow_html=True)
    else:
        notices = result.get("notices", []); smap = _smap(result)
        st.markdown(_section("필터"), unsafe_allow_html=True)
        f1,f2,f3 = st.columns(3)
        with f1: gf = st.multiselect("등급", ["A","B","C","D"], default=["A","B","C","D"])
        with f2: sf = st.multiselect("사이트", sorted(set(n.site for n in notices)))
        with f3: kw = st.text_input("키워드 검색", placeholder="공고명 키워드...")

        filtered = []
        for n in notices:
            sc = smap.get(n.notice_id); g = sc.priority_grade if sc else "D"
            if g not in gf: continue
            if sf and n.site not in sf: continue
            if kw and kw.lower() not in (n.title or "").lower(): continue
            filtered.append((n, sc))
        go_ = {"A":0,"B":1,"C":2,"D":3}
        filtered.sort(key=lambda x: (go_.get(x[1].priority_grade if x[1] else "D",3), -(x[1].priority_score if x[1] else 0)))

        st.markdown(f'<p style="color:{S5};font-size:.82rem;font-weight:500">조회 결과 <b style="color:{CH}">{len(filtered)}</b> / {len(notices)}건</p>', unsafe_allow_html=True)

        rows = []
        for n, sc in filtered:
            dd = _dday(n.deadline_date or "")
            _bgt = n.budget or ""
            _bv = None
            try:
                _m = re.search(r'(\d[\d,.]*)\s*억', _bgt)
                if _m: _bv = float(_m.group(1).replace(",",""))
            except: pass
            _action = "인터엑스" if _bv and _bv >= 2.1 else "파트너이관" if _bv and _bv < 2.0 else "-"
            rows.append({"등급": sc.priority_grade if sc else "D", "점수": f"{sc.priority_score:.0f}" if sc else "-",
                         "공고명": n.title[:70] if n.title else "-", "주관기관": n.agency or n.ministry or "-",
                         "사이트": n.site, "마감일": n.deadline_date or "-", "D-day": str(dd) if dd>=0 else "마감",
                         "L3": "Y" if getattr(n,"l3_strong","N")=="Y" else "", "예산": _bgt or "-", "진행": _action})
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", height=420)

            dl1, dl2, _ = st.columns([1,1,5])
            df = pd.DataFrame(rows)
            dl1.download_button("📄 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                f"interx_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    df.to_excel(w, index=False, sheet_name="공고목록")
                dl2.download_button("📊 Excel", buf.getvalue(),
                                    f"interx_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except: pass

            # ── Detail Panel ──
            st.markdown(_section("공고 상세"), unsafe_allow_html=True)
            ntmap = {f"[{sc.priority_grade if sc else 'D'}] {n.title[:55]} ({n.site})": (n, sc) for n, sc in filtered}
            sel = st.selectbox("공고 선택", ["선택하세요..."] + list(ntmap.keys()), label_visibility="collapsed")
            if sel != "선택하세요..." and sel in ntmap:
                sn, ssc = ntmap[sel]
                dd = _dday(sn.deadline_date or "")
                grade = ssc.priority_grade if ssc else "D"
                gc = GRADE.get(grade, S5)

                st.markdown(f"""<div style="background:{S0};border-left:4px solid {gc};border-radius:0 12px 12px 0;padding:18px 24px;margin:8px 0">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
                        {_badge(grade)}
                        <span style="font-size:1.05rem;font-weight:700;color:{S8}">{sn.title}</span>
                    </div>
                    <div style="font-size:.78rem;color:{S5}">{sn.site} · {sn.agency or sn.ministry or '-'} · {sn.deadline_date or '-'} · 예산 {sn.budget or '-'}</div>
                </div>""", unsafe_allow_html=True)

                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("##### 기본 정보")
                    for label, val in [("주관기관", sn.agency or sn.ministry or "-"), ("부처", getattr(sn,"ministry","-") or "-"),
                                       ("마감일", f"{sn.deadline_date or '-'} (D-{dd})" if dd>=0 else f"{sn.deadline_date or '-'} (마감)"),
                                       ("예산", sn.budget or "-"), ("공고일", getattr(sn,"notice_date","-") or "-"),
                                       ("신청기간", getattr(sn,"apply_period","-") or "-")]:
                        st.markdown(f"- **{label}** : {val}")
                    link = getattr(sn, "detail_url", "") or ""
                    if link and link.startswith("http"): st.markdown(f"- **링크** : [{link[:50]}...]({link})")

                with dc2:
                    if ssc:
                        st.markdown("##### 스코어링 분석")
                        sc1,sc2,sc3 = st.columns(3)
                        sc1.metric("적합도", f"{ssc.fitness_score:.1f}")
                        sc2.metric("우선순위", f"{ssc.priority_score:.1f}")
                        sc3.metric("산업점수", f"{ssc.industry_score:.1f}")

                        fitness = ssc.fitness_score or 0; priority = ssc.priority_score or 0
                        industry = ssc.industry_score or 0; l3v = 1 if getattr(sn,"l3_strong","N")=="Y" else 0
                        urg = max(0, min(100, (30-dd)*3.33)) if dd>=0 else 0
                        wp = min(100, max(0, fitness*0.35 + priority*0.25 + 50*0.15 + urg*0.10 + l3v*10 + industry*0.05))
                        wp_c = GA if wp>=60 else GB if wp>=40 else GC if wp>=20 else GD
                        st.markdown(f"**수주 확률** &nbsp; <span style='color:{wp_c};font-size:1.3rem;font-weight:800'>{wp:.0f}%</span>", unsafe_allow_html=True)

                        if ssc.positive_keywords:
                            tags = " ".join(f'<span style="background:{P};color:{W};padding:3px 10px;border-radius:20px;font-size:.73rem;font-weight:600;margin:2px;display:inline-block">{k}</span>' for k in ssc.positive_keywords[:12])
                            st.markdown(f"**매칭 키워드** <br>{tags}", unsafe_allow_html=True)

                        if ssc.solution_scores:
                            SOL = {"ManufacturingDT":"제조DT","RecipeAI":"레시피AI","QualityAI":"품질AI",
                                   "InspectionAI":"비전검사","SafetyAI":"안전AI","GenAI":"GenAI","InfraDS":"데이터인프라","PdM":"예지보전"}
                            sols = sorted([(SOL.get(k,k),v) for k,v in ssc.solution_scores.items() if v>0], key=lambda x:-x[1])
                            if sols:
                                st.markdown("**솔루션 매칭** &nbsp;" + " · ".join(f"**{name}** {score:.0f}" for name,score in sols[:5]))

                body = getattr(sn, "body_text", "") or ""
                if body:
                    with st.expander("📄 공고 본문", expanded=False):
                        st.text(body[:5000])
                        if len(body) > 5000: st.caption(f"전체 {len(body):,}자 중 5,000자 표시")

                # ── 원문 사이트 미리보기 ──
                _sn_link = getattr(sn, "detail_url", "") or ""
                if _sn_link and _sn_link.startswith("http"):
                    with st.expander("🌐 원문 사이트 보기", expanded=False):
                        import streamlit.components.v1 as components
                        components.iframe(_sn_link, height=560, scrolling=True)
        else:
            st.info("필터 조건에 맞는 공고가 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 4 · Proposals
# ═══════════════════════════════════════════════════════════════════════════════

with tab_proposal:
    result = _result()
    if not result:
        st.markdown(_empty("📝", "제안서 데이터 없음", "수집 실행 시 A/B등급 공고에 대해 제안서가 자동 생성됩니다."), unsafe_allow_html=True)
    else:
        proposals = result.get("proposal_files", [])
        if not proposals:
            st.markdown(_empty("📝", "생성된 제안서가 없습니다", "A/B등급 공고가 있을 때 자동으로 제안서가 생성됩니다."), unsafe_allow_html=True)
        else:
            st.markdown(_section(f"자동 생성 제안서 ({len(proposals)}건)"), unsafe_allow_html=True)
            for _pi, p in enumerate(proposals):
                fp = Path(p)
                if fp.exists():
                    cn, cd = st.columns([5, 1])
                    cn.markdown(_notice_row("A", fp.stem, f"{fp.suffix} · {fp.stat().st_size:,} bytes"), unsafe_allow_html=True)
                    with open(fp, "rb") as f:
                        cd.download_button("다운로드", f.read(), fp.name,
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           key=f"dl_{_pi}_{fp.name}")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 5 · Competitor Analysis
# ═══════════════════════════════════════════════════════════════════════════════

with tab_compete:
    result = _result()
    if not result:
        st.markdown(_empty("🏢", "경쟁사 분석 데이터 없음", "수집 실행 후 경쟁사 관련 공고를 자동으로 분석합니다."), unsafe_allow_html=True)
    else:
        notices = result.get("notices", []); score_cards = result.get("score_cards", [])
        if notices:
            try:
                import plotly.graph_objects as go
                from interx_engine.application.use_cases.competitor_report import generate_competitor_report
                with st.spinner("경쟁사 분석 중..."):
                    cr = generate_competitor_report(notices, score_cards)
                s = cr.get("summary", {}); cn = cr.get("competitor_notices", [])

                c1,c2,c3,c4 = st.columns(4)
                c1.markdown(_metric(s.get("total_notices",0), "전체 공고"), unsafe_allow_html=True)
                c2.markdown(_metric(s.get("competitor_related",0), "경쟁사 관련"), unsafe_allow_html=True)
                c3.markdown(_metric(f'{s.get("competitor_ratio",0)}%', "경쟁 비율"), unsafe_allow_html=True)
                c4.markdown(_metric(s.get("tier1_count",0), "Tier1 탐지", GD), unsafe_allow_html=True)

                tc = s.get("top_competitors", [])
                if tc:
                    st.markdown(_section("경쟁사 탐지 TOP 10"), unsafe_allow_html=True)
                    fig = go.Figure(go.Bar(x=[c[1] for c in tc[:10]], y=[c[0] for c in tc[:10]], orientation='h', marker_color=P))
                    fig.update_layout(height=380, yaxis=dict(autorange="reversed"), xaxis=dict(gridcolor=S2, title="탐지 횟수"), **_layout())
                    st.plotly_chart(fig, width="stretch")
                if cn:
                    st.markdown(_section(f"경쟁사 관련 공고 ({len(cn)}건)"), unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame([{"등급":c["grade"],"공고명":c["title"][:55],"사이트":c["site"],
                                                "마감일":c["deadline"] or "-","경쟁사":" / ".join(c["competitors"]),
                                                "Tier":" / ".join(c["tiers"])} for c in cn]),
                                 width="stretch", height=380)
            except Exception as e: st.error(f"경쟁사 분석 실패: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 6 · Win Prediction
# ═══════════════════════════════════════════════════════════════════════════════

with tab_predict:
    result = _result()
    if not result:
        st.markdown(_empty("🎯", "수주 예측 데이터 없음", "수집 실행 후 공고별 수주 확률을 예측합니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); smap = _smap(result)
        preds = []
        for n in notices:
            sc = smap.get(n.notice_id)
            if not sc: continue
            f_ = sc.fitness_score or 0; p_ = sc.priority_score or 0; i_ = sc.industry_score or 0
            l3 = 1 if getattr(n,"l3_strong","N")=="Y" else 0
            dd = _dday(n.deadline_date or ""); u_ = max(0,min(100,(30-dd)*3.33)) if dd>=0 else 0
            wp = min(100, max(0, f_*0.35 + p_*0.25 + 50*0.15 + u_*0.10 + l3*10 + i_*0.05))
            preds.append({"notice":n, "sc":sc, "wp":wp})
        preds.sort(key=lambda x:-x["wp"])

        hp = sum(1 for p in preds if p["wp"]>=60)
        avg = sum(p["wp"] for p in preds)/max(1,len(preds))
        k1,k2,k3 = st.columns(3)
        k1.markdown(_metric(len(preds), "예측 대상"), unsafe_allow_html=True)
        k2.markdown(_metric(hp, "유망 60%+", GA), unsafe_allow_html=True)
        k3.markdown(_metric(f"{avg:.0f}%", "평균 확률"), unsafe_allow_html=True)

        col_h, col_t = st.columns([1,2])
        with col_h:
            bins = {"0-20":0,"20-40":0,"40-60":0,"60-80":0,"80-100":0}
            for p in preds:
                w=p["wp"]
                if w<20: bins["0-20"]+=1
                elif w<40: bins["20-40"]+=1
                elif w<60: bins["40-60"]+=1
                elif w<80: bins["60-80"]+=1
                else: bins["80-100"]+=1
            fig = go.Figure(go.Bar(x=[f"{k}%" for k in bins], y=list(bins.values()),
                                   marker_color=[GD,GC,"#FBBF24",GB,GA]))
            fig.update_layout(title=dict(text="확률 분포", font=dict(size=14,color=S8)),
                              height=330, xaxis=dict(title="구간"), yaxis=dict(title="건수",gridcolor=S2), **_layout())
            st.plotly_chart(fig, width="stretch")

        with col_t:
            st.markdown(_section("수주 유망 TOP 10"), unsafe_allow_html=True)
            for _wi, p in enumerate(preds[:10]):
                n,sc,wp = p["notice"],p["sc"],p["wp"]
                c = GA if wp>=60 else GB if wp>=40 else GC
                meta = f"{sc.priority_grade}등급 · {n.site} · {n.agency or '-'} · {n.deadline_date or '-'}"
                st.markdown(_notice_row(sc.priority_grade, f'<span style="color:{c};font-weight:800">{wp:.0f}%</span> {n.title[:50]}', meta), unsafe_allow_html=True)
                with st.expander(f"🔍 수주 가능성 분석", expanded=False):
                    # 개별 가중치 계산
                    _f = sc.fitness_score or 0; _p = sc.priority_score or 0; _i = sc.industry_score or 0
                    _l3 = 1 if getattr(n,"l3_strong","N")=="Y" else 0
                    _dd = _dday(n.deadline_date or ""); _u = max(0,min(100,(30-_dd)*3.33)) if _dd>=0 else 0
                    _fc = _f*0.35; _pc = _p*0.25; _bc = 50*0.15; _uc = _u*0.10; _lc = _l3*10; _ic = _i*0.05
                    # 시각적 바 차트
                    _factors = [("키워드 적합도", _fc, f"{_f:.0f}×0.35={_fc:.1f}"),
                                ("우선순위 점수", _pc, f"{_p:.0f}×0.25={_pc:.1f}"),
                                ("예산 기여", _bc, f"50×0.15={_bc:.1f}"),
                                ("마감 긴급도", _uc, f"D-{_dd}→{_u:.0f}×0.10={_uc:.1f}" if _dd>=0 else "마감→0"),
                                ("L3 강공고", _lc, f"{'Y' if _l3 else 'N'}→{_lc:.1f}"),
                                ("솔루션 매칭", _ic, f"{_i:.0f}×0.05={_ic:.1f}")]
                    _bar_html = ""
                    for _fn, _fv, _fd in _factors:
                        _bw = max(2, min(100, _fv * 3))
                        _bc2 = GA if _fv >= 10 else GB if _fv >= 5 else GC if _fv >= 2 else S4
                        _bar_html += f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:.78rem"><span style="width:90px;color:{S5};font-weight:600;text-align:right">{_fn}</span><div style="flex:1;background:{S1};border-radius:4px;height:18px;overflow:hidden"><div style="width:{_bw}%;height:100%;background:{_bc2};border-radius:4px"></div></div><span style="width:120px;color:{S4};font-size:.72rem">{_fd}</span></div>'
                    st.markdown(f'<div style="padding:4px 0">{_bar_html}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="text-align:right;font-size:.85rem;font-weight:800;color:{c};margin-top:6px">합계: {wp:.0f}%</div>', unsafe_allow_html=True)
                    # 핵심 근거 요약
                    _reasons = []
                    if _f >= 40: _reasons.append(f"키워드 적합도 높음 ({_f:.0f}점)")
                    if sc.positive_keywords: _reasons.append(f"매칭 키워드: {', '.join(sc.positive_keywords[:5])}")
                    if _l3: _reasons.append("L3 강공고 해당")
                    if 0 <= _dd <= 7: _reasons.append(f"마감 임박 D-{_dd}")
                    sol_hits = [(s,v) for s,v in (sc.solution_scores or {}).items() if v > 0]
                    if sol_hits: _reasons.append(f"솔루션: {', '.join(s for s,_ in sorted(sol_hits, key=lambda x:-x[1])[:3])}")
                    if _reasons:
                        st.markdown("**📌 핵심 근거**: " + " · ".join(_reasons))


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 7 · Deadline Calendar
# ═══════════════════════════════════════════════════════════════════════════════

with tab_calendar:
    result = _result()
    if not result:
        st.markdown(_empty("📅", "마감 캘린더 데이터 없음", "수집 실행 후 마감일 관리를 할 수 있습니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices",[]); smap = _smap(result)
        upcoming = []
        for n in notices:
            dl = n.deadline_date or ""
            if not dl: continue
            dd = _dday(dl)
            if dd < 0: continue
            upcoming.append({"date":dl,"dday":dd,"notice":n,"sc":smap.get(n.notice_id)})
        upcoming.sort(key=lambda x:x["dday"])

        d3=sum(1 for u in upcoming if u["dday"]<=3); d7=sum(1 for u in upcoming if u["dday"]<=7); d30=sum(1 for u in upcoming if u["dday"]<=30)
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(_metric(d3, "3일내 마감", GD), unsafe_allow_html=True)
        k2.markdown(_metric(d7, "7일내 마감", GC), unsafe_allow_html=True)
        k3.markdown(_metric(d30, "30일내 마감"), unsafe_allow_html=True)
        k4.markdown(_metric(len(upcoming), "전체 미마감"), unsafe_allow_html=True)

        if upcoming:
            dates = sorted(set(u["date"] for u in upcoming))[:30]
            dc = Counter(u["date"] for u in upcoming)
            fig = go.Figure(go.Bar(x=dates, y=[dc[d] for d in dates], marker_color=[
                GD if _dday(d)<=3 else GC if _dday(d)<=7 else P for d in dates]))
            fig.update_layout(height=280, xaxis=dict(title="마감일"), yaxis=dict(title="건수",gridcolor=S2), **_layout())
            st.plotly_chart(fig, width="stretch")

        st.markdown(_section(f"긴급 마감 D-7 이내 ({d7}건)"), unsafe_allow_html=True)
        for u in upcoming:
            if u["dday"]>7: break
            n,sc,dd = u["notice"],u["sc"],u["dday"]
            grade = sc.priority_grade if sc else "D"
            pill = _pill(f"D-{dd}", "urgent") if dd<=3 else _pill(f"D-{dd}", "c")
            meta = f"{n.site} · {n.agency or '-'} · 마감 {n.deadline_date}"
            st.markdown(_notice_row(grade, n.title[:55], meta, pill), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 8 · Solution Matching
# ═══════════════════════════════════════════════════════════════════════════════

with tab_solution:
    result = _result()
    if not result:
        st.markdown(_empty("🔧", "솔루션 분석 데이터 없음", "수집 실행 후 8개 솔루션별 매칭 분석을 제공합니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        score_cards = result.get("score_cards",[])
        SOL = {"ManufacturingDT":"제조 DT","RecipeAI":"레시피 AI","QualityAI":"품질 AI",
               "InspectionAI":"비전검사","SafetyAI":"안전 AI","GenAI":"GenAI","InfraDS":"데이터 인프라","PdM":"예지보전"}
        sol_t = defaultdict(list)
        for sc in score_cards:
            if sc.solution_scores:
                for k,v in sc.solution_scores.items():
                    if v>0: sol_t[k].append(v)
        if sol_t:
            sol_avg = {k:sum(v)/len(v) for k,v in sol_t.items()}
            sol_cnt = {k:len(v) for k,v in sol_t.items()}
            ss = sorted(sol_avg.items(), key=lambda x:-x[1])
            top = ss[0] if ss else ("N/A",0)

            k1,k2,k3 = st.columns(3)
            k1.markdown(_metric(len(sol_t), "매칭 솔루션"), unsafe_allow_html=True)
            k2.markdown(_metric(SOL.get(top[0],top[0]), "TOP 솔루션"), unsafe_allow_html=True)
            k3.markdown(_metric(f"{top[1]:.0f}", "TOP 평균점수"), unsafe_allow_html=True)

            cr, cb = st.columns(2)
            with cr:
                cats=[SOL.get(k,k) for k in sol_avg]; vals=list(sol_avg.values())
                fig=go.Figure(go.Scatterpolar(r=vals+[vals[0]], theta=cats+[cats[0]], fill='toself',
                    fillcolor='rgba(245,146,27,.08)', line=dict(color=P,width=2.5), marker=dict(size=6,color=P)))
                fig.update_layout(title=dict(text="솔루션 레이더",font=dict(size=14,color=S8)),
                    polar=dict(radialaxis=dict(visible=True,range=[0,100],gridcolor=S2),bgcolor=S0,angularaxis=dict(gridcolor=S2)),
                    height=380,**_layout())
                st.plotly_chart(fig, width="stretch")
            with cb:
                names=[SOL.get(k,k) for k,_ in ss]; avgs=[v for _,v in ss]; cnts=[sol_cnt[k] for k,_ in ss]
                fig=go.Figure()
                fig.add_trace(go.Bar(x=names,y=avgs,name="평균 점수",marker_color=P))
                fig.add_trace(go.Bar(x=names,y=cnts,name="매칭 공고",marker_color=GB))
                fig.update_layout(title=dict(text="솔루션별 비교",font=dict(size=14,color=S8)),barmode='group',height=380,
                    xaxis=dict(gridcolor=S2),yaxis=dict(gridcolor=S2),legend=dict(orientation="h",y=1.12),**_layout())
                st.plotly_chart(fig, width="stretch")
        else:
            st.markdown(_empty("🔧","솔루션 데이터 없음","매칭되는 솔루션이 없습니다."), unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 9 · Keyword Trends
# ═══════════════════════════════════════════════════════════════════════════════

with tab_keyword:
    result = _result()
    if not result:
        st.markdown(_empty("📈", "키워드 데이터 없음", "수집 실행 후 시장 키워드 트렌드를 분석합니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices",[]); score_cards = result.get("score_cards",[])
        kw_c = Counter()
        for sc in score_cards:
            if sc.positive_keywords:
                for k in sc.positive_keywords: kw_c[k]+=1
        title_w = Counter()
        stops = {"사업","지원","공고","모집","안내","위한","대한","관련","통한","기반","활용","추진",
                 "참여","신청","접수","대상","분야","과제","수행","기관","선정","계획","결과","변경",
                 "연장","프로그램","센터","재공고","용역","발표","공지","정보","운영","기술","개발",
                 "산업","기업","육성","연구","전문","협력","국내","혁신","전략","구축","도입","확대",
                 "사항","가능","제공","진행","통해","등록","기타","문의","담당","홈페이지","바로가기",
                 "상반기","하반기","년도","차년도","연도","해당",
                 # v5.2 추가 불용어 — 연도·일반 공고용어
                 "참여기업","모집공고","2025년","2025년도","2026년","2026년도","2027년","2027년도",
                 "수요기업","공모","통합","시행","예정","일정","기간","방법","절차","요강",
                 "수정","재안내","알림","공개","추가","확정","최종","우수","평가","심사",
                 "테크노파크","진흥원","진흥재단","중소기업","지원사업","지방자치"}
        for n in notices:
            for w in (n.title or "").split():
                c = "".join(ch for ch in w if ch.isalnum())
                # 숫자포함 연도패턴(2026년 등), 순수숫자, 2글자 미만, 불용어 제외
                if len(c) < 2 or c in stops or re.fullmatch(r'\d+', c) or re.fullmatch(r'\d{4}년도?', c): continue
                title_w[c] += 1

        k1,k2 = st.columns(2)
        k1.markdown(_metric(len(kw_c), "매칭 키워드"), unsafe_allow_html=True)
        k2.markdown(_metric(kw_c.most_common(1)[0][0] if kw_c else "-", "최다 키워드"), unsafe_allow_html=True)

        ck,ct = st.columns(2)
        with ck:
            if kw_c:
                t20=kw_c.most_common(20)
                fig=go.Figure(go.Bar(y=[k[0] for k in reversed(t20)],x=[k[1] for k in reversed(t20)],orientation='h',marker_color=P))
                fig.update_layout(title=dict(text="스코어링 키워드 TOP 20",font=dict(size=14,color=S8)),
                    height=480,xaxis=dict(title="횟수",gridcolor=S2),**_layout(margin=dict(l=110,r=16,t=40,b=36)))
                st.plotly_chart(fig, width="stretch")
        with ct:
            if title_w:
                t20t=title_w.most_common(20)
                fig=go.Figure(go.Bar(y=[k[0] for k in reversed(t20t)],x=[k[1] for k in reversed(t20t)],orientation='h',marker_color=GB))
                fig.update_layout(title=dict(text="제목 빈출 단어 TOP 20",font=dict(size=14,color=S8)),
                    height=480,xaxis=dict(title="횟수",gridcolor=S2),**_layout(margin=dict(l=110,r=16,t=40,b=36)))
                st.plotly_chart(fig, width="stretch")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 10 · Manager Overview
# ═══════════════════════════════════════════════════════════════════════════════

with tab_manager:
    result = _result()
    if not result:
        st.markdown(_empty("👤","담당자 현황 없음","수집 실행 후 담당자별 공고 배분을 확인할 수 있습니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices",[]); smap = _smap(result)
        md = defaultdict(lambda:{"total":0,"A":0,"B":0,"C":0,"D":0})
        for n in notices:
            mgr = n.manager or "미배정"; sc = smap.get(n.notice_id); g = sc.priority_grade if sc else "D"
            md[mgr]["total"]+=1; md[mgr][g]+=1

        tm = len([m for m in md if m!="미배정"]); ua = md.get("미배정",{}).get("total",0)
        k1,k2,k3 = st.columns(3)
        k1.markdown(_metric(tm, "배정 담당자"), unsafe_allow_html=True)
        k2.markdown(_metric(len(notices)-ua, "배정 완료"), unsafe_allow_html=True)
        k3.markdown(_metric(ua, "미배정", GD), unsafe_allow_html=True)

        if md:
            mgrs = sorted(md, key=lambda m:-md[m]["total"])
            fig = go.Figure()
            for g,c in [("A",GA),("B",GB),("C",GC),("D",GD)]:
                fig.add_trace(go.Bar(name=g, x=mgrs, y=[md[m][g] for m in mgrs], marker_color=c))
            fig.update_layout(title=dict(text="담당자별 등급 분포",font=dict(size=14,color=S8)),barmode='stack',height=380,
                legend=dict(orientation="h",y=1.12),xaxis=dict(gridcolor=S2),yaxis=dict(title="건수",gridcolor=S2),**_layout())
            st.plotly_chart(fig, width="stretch")

        st.markdown(_section("담당자 상세"), unsafe_allow_html=True)
        mrows = [{"담당자":m,"전체":d["total"],"A":d["A"],"B":d["B"],"C":d["C"],"D":d["D"],
                  "A비율":f'{d["A"]/max(1,d["total"])*100:.0f}%'} for m,d in sorted(md.items(),key=lambda x:-x[1]["total"])]
        st.dataframe(pd.DataFrame(mrows), width="stretch", height=350)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 11 · Collection History
# ═══════════════════════════════════════════════════════════════════════════════

with tab_history:
    history = st.session_state.get("collection_history",[])
    if not history:
        st.markdown(_empty("🕐","수집 히스토리 없음","수집을 실행하면 결과가 여기에 기록됩니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        latest = history[-1]
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(_metric(len(history), "총 수집 횟수"), unsafe_allow_html=True)
        k2.markdown(_metric(latest["total"], "최근 수집건수"), unsafe_allow_html=True)
        k3.markdown(_metric(latest["grades"].get("A",0), "최근 A등급", GA), unsafe_allow_html=True)
        if len(history)>=2:
            diff = latest["total"]-history[-2]["total"]
            ds = f"+{diff}" if diff>0 else str(diff)
            k4.markdown(_metric(ds, "이전 대비", GA if diff>0 else GD if diff<0 else S5), unsafe_allow_html=True)
        else:
            k4.markdown(_metric("-", "이전 대비"), unsafe_allow_html=True)

        st.markdown(_section("수집 기록"), unsafe_allow_html=True)
        hrows = [{"#":i,"수집일시":h["timestamp"],"모드":h.get("mode","-"),"전체":h["total"],
                  "A":h["grades"].get("A",0),"B":h["grades"].get("B",0),"C":h["grades"].get("C",0),
                  "D":h["grades"].get("D",0),"L3":h.get("l3_count",0),"제안서":h.get("proposals",0),
                  "사이트":len(h.get("sites",{}))} for i,h in enumerate(reversed(history),1)]
        st.dataframe(pd.DataFrame(hrows), width="stretch", height=280)

        try:
            buf=io.BytesIO()
            with pd.ExcelWriter(buf,engine="openpyxl") as w:
                pd.DataFrame(hrows).to_excel(w,index=False,sheet_name="히스토리")
            st.download_button("📊 히스토리 Excel", buf.getvalue(),
                               f"interx_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except: pass

        if len(history)>=2:
            ct,cg = st.columns(2)
            with ct:
                ts=[h["timestamp"][:16] for h in history]; tots=[h["total"] for h in history]
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=ts,y=tots,mode='lines+markers',name='전체',line=dict(color=P,width=3),marker=dict(size=8,color=P)))
                fig.add_trace(go.Scatter(x=ts,y=[h["grades"].get("A",0) for h in history],mode='lines+markers',name='A등급',line=dict(color=GA,width=2),marker=dict(size=6,color=GA)))
                fig.update_layout(title=dict(text="수집 추이",font=dict(size=14,color=S8)),height=330,
                    xaxis=dict(gridcolor=S2),yaxis=dict(title="건수",gridcolor=S2),legend=dict(orientation="h",y=1.12),**_layout())
                st.plotly_chart(fig, width="stretch")
            with cg:
                lg=history[-1]["grades"]; pg=history[-2]["grades"]
                gl=["A","B","C","D"]
                fig=go.Figure()
                fig.add_trace(go.Bar(name="이전",x=gl,y=[pg.get(g,0) for g in gl],marker_color=S3))
                fig.add_trace(go.Bar(name="최근",x=gl,y=[lg.get(g,0) for g in gl],marker_color=[GA,GB,GC,GD]))
                fig.update_layout(title=dict(text="등급 비교",font=dict(size=14,color=S8)),height=330,barmode='group',
                    xaxis=dict(gridcolor=S2),yaxis=dict(title="건수",gridcolor=S2),legend=dict(orientation="h",y=1.12),**_layout())
                st.plotly_chart(fig, width="stretch")

            if len(history)>=2:
                st.markdown(_section("사이트별 변화"), unsafe_allow_html=True)
                ls=history[-1].get("sites",{}); ps=history[-2].get("sites",{})
                asn=sorted(set(list(ls)+list(ps)))
                if asn:
                    sr=[{"사이트":s,"최근":ls.get(s,0),"이전":ps.get(s,0),
                         "변화":f"+{ls.get(s,0)-ps.get(s,0)}" if ls.get(s,0)-ps.get(s,0)>0 else str(ls.get(s,0)-ps.get(s,0))} for s in asn]
                    st.dataframe(pd.DataFrame(sr), width="stretch", height=280)


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 12 · AI News & Trends
# ═══════════════════════════════════════════════════════════════════════════════

with tab_news:
    import xml.etree.ElementTree as ET
    import requests as _req
    from html import unescape as _unescape

    @st.cache_data(ttl=1800, show_spinner=False)  # 30분 캐시
    def _fetch_rss(url, limit=8):
        """RSS 피드에서 뉴스 항목 파싱"""
        try:
            r = _req.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = []
            # RSS 2.0 or Atom
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if not title: continue
                # HTML 태그 제거 + unescape
                desc = re.sub(r'<[^>]+>', '', _unescape(desc))[:200]
                items.append({"title": _unescape(title), "link": link, "desc": desc, "date": pub[:16] if pub else ""})
                if len(items) >= limit: break
            # Atom 형식 fallback
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns) or root.iter("entry"):
                    title = ""
                    for t in entry.iter():
                        if t.tag.endswith("title"): title = (t.text or "").strip(); break
                    link = ""
                    for l in entry.iter():
                        if l.tag.endswith("link"): link = l.get("href","") or (l.text or "").strip(); break
                    summary = ""
                    for s in entry.iter():
                        if s.tag.endswith("summary") or s.tag.endswith("content"): summary = (s.text or "").strip(); break
                    if not title: continue
                    summary = re.sub(r'<[^>]+>', '', _unescape(summary))[:200]
                    items.append({"title": _unescape(title), "link": link, "desc": summary, "date": ""})
                    if len(items) >= limit: break
            return items
        except Exception:
            return []

    st.markdown(_section("🤖 AI 팩토리 · 제조AI 뉴스 (실시간)"), unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:.8rem;color:{S4}">RSS 피드 기반 실시간 뉴스 · 30분 간격 자동 갱신</p>', unsafe_allow_html=True)

    _rss_feeds = [
        {"cat": "🏭 AI·제조·스마트공장", "feeds": [
            ("AI타임스", "https://www.aitimes.com/rss/allArticle.xml"),
            ("로봇신문", "https://www.irobotnews.com/rss/allArticle.xml"),
            ("전자신문 AI", "https://rss.etnews.com/Section902.xml"),
        ]},
        {"cat": "📊 IT·산업 동향", "feeds": [
            ("ZDNet Korea", "https://zdnet.co.kr/rss/newsAll.htm"),
            ("디지털타임스", "https://www.dt.co.kr/rss/allArticle.xml"),
            ("IT조선", "http://it.chosun.com/rss/all_rss.xml"),
        ]},
        {"cat": "🌐 글로벌 AI", "feeds": [
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
            ("The Robot Report", "https://www.therobotreport.com/feed/"),
            ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
        ]},
    ]

    _news_cat = st.radio("카테고리", [f["cat"] for f in _rss_feeds], horizontal=True, key="news_cat")
    _sel_feed = next((f for f in _rss_feeds if f["cat"] == _news_cat), _rss_feeds[0])

    for feed_name, feed_url in _sel_feed["feeds"]:
        st.markdown(f'<div style="font-size:.9rem;font-weight:700;color:{P};margin:18px 0 8px;border-left:3px solid {P};padding-left:10px">{feed_name}</div>', unsafe_allow_html=True)
        items = _fetch_rss(feed_url, limit=5)
        if items:
            for it in items:
                _date_str = f' · <span style="color:{S4}">{it["date"]}</span>' if it["date"] else ""
                st.markdown(f'''<div style="background:{W};border:1px solid {S2};border-radius:10px;padding:14px 18px;margin-bottom:8px">
<a href="{it["link"]}" target="_blank" style="text-decoration:none;color:{S8};font-weight:600;font-size:.85rem;line-height:1.4">{it["title"]}</a>{_date_str}
<div style="font-size:.78rem;color:{S5};margin-top:6px;line-height:1.5">{it["desc"]}</div>
</div>''', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size:.8rem;color:{S4};padding:8px">피드를 불러올 수 없습니다. <a href="{feed_url}" target="_blank">직접 방문 ↗</a></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── 바로가기 링크 섹션 ──
    st.markdown(_section("🔗 주요 사이트 바로가기"), unsafe_allow_html=True)
    _links = [
        ("K-스마트공장", "https://www.smart-factory.kr/"), ("IITP", "https://www.iitp.kr/"),
        ("NIPA", "https://www.nipa.kr/"), ("과기정통부", "https://www.msit.go.kr/"),
        ("arXiv AI", "https://arxiv.org/list/cs.AI/recent"), ("Papers With Code", "https://paperswithcode.com/"),
        ("Hugging Face", "https://huggingface.co/blog"), ("Manufacturing Dive", "https://www.manufacturingdive.com/"),
    ]
    _link_html = " ".join(f'<a href="{u}" target="_blank" style="background:{P_BG};color:{P_D};border:1px solid rgba(255,128,0,.2);padding:6px 16px;border-radius:20px;font-size:.8rem;font-weight:600;text-decoration:none;display:inline-block;margin:3px">{n} ↗</a>' for n, u in _links)
    st.markdown(f'<div style="line-height:2.4">{_link_html}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(_section("📌 오늘의 AI 키워드"), unsafe_allow_html=True)
    _ai_keywords = ["에이전틱AI", "피지컬AI", "디지털트윈", "자율공정", "AI팩토리",
                     "생성형AI", "LLM", "Multi-Agent", "스마트공장", "예지보전",
                     "컴퓨터비전", "AI반도체", "엣지AI", "DTaaS", "로보틱스"]
    _kw_html = " ".join(f'<span style="background:{S0};color:{CH};padding:5px 14px;border-radius:20px;font-size:.8rem;font-weight:600;display:inline-block;margin:3px">{k}</span>' for k in _ai_keywords)
    st.markdown(f'<div style="line-height:2.2">{_kw_html}</div>', unsafe_allow_html=True)
