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
S8 = "#1A1A2E"      # deep navy-black
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
st.set_page_config(page_title="InterX Intelligence", page_icon="🔶", layout="wide", initial_sidebar_state="expanded")

# ── Intro (CSS only — Streamlit은 <script> 미실행) ──
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = True
    st.markdown('<style>@keyframes ix-fade{0%{opacity:0;transform:scale(.85) translateY(14px)}15%{opacity:1;transform:scale(1.02)}40%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(.97) translateY(-8px)}}@keyframes ix-bg{0%,70%{opacity:1}100%{opacity:0;pointer-events:none;visibility:hidden}}.ix-intro{position:fixed;inset:0;z-index:99999;background:#000;display:flex;align-items:center;justify-content:center;animation:ix-bg 2.4s ease forwards}.ix-intro .logo{animation:ix-fade 2.4s ease forwards;text-align:center}.ix-intro .mark{font-size:3rem;font-weight:900;letter-spacing:-2px;font-family:Inter,system-ui,sans-serif}.ix-intro .mark b{color:#FF8000}.ix-intro .mark span{color:#fff}.ix-intro .sub{color:rgba(255,255,255,.4);font-size:.78rem;letter-spacing:4px;margin-top:10px;font-weight:500}</style><div class="ix-intro"><div class="logo"><div class="mark"><span>INTER</span><b>X</b></div><div class="sub">INTELLIGENCE ENGINE</div></div></div>', unsafe_allow_html=True)

# ── Enterprise CSS v6 — Professional Grade ──
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Global ── */
.stApp{{background:#FAFAFA;font-family:'Inter',system-ui,-apple-system,sans-serif}}
#MainMenu,footer,header{{visibility:hidden}}

/* ── Sidebar Light Theme ── */
section[data-testid="stSidebar"]{{
    background:{W};min-width:240px;max-width:240px;
    border-right:1px solid rgba(0,0,0,.06);
}}
section[data-testid="stSidebar"] .stRadio label{{
    color:{S8} !important;font-weight:600;font-size:.82rem;
}}
section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"]{{
    color:{S8} !important;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label{{
    padding:10px 16px !important;border-radius:8px !important;margin:1px 0;
    transition:all .2s;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover{{
    background:rgba(255,128,0,.05) !important;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:has(input:checked){{
    background:rgba(255,128,0,.08) !important;
    border-left:3px solid {P} !important;color:{P} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{{
    color:{S5} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3{{
    color:{S8} !important;
}}

/* ── Full-bleed: 모든 Streamlit 내부 패딩 제거 ── */
.stApp > header{{display:none !important}}
.stMainBlockContainer,
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"],
.block-container{{
    padding:0 !important;max-width:100% !important;width:100% !important;
}}
[data-testid="stAppViewContainer"]{{padding:0 !important}}
[data-testid="stAppViewContainer"] > section{{padding:0 !important}}
[data-testid="stAppViewContainer"] > section > div{{padding:0 !important}}
[data-testid="stVerticalBlock"]{{gap:0 !important}}
.stApp [data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"] > div:first-child {{padding:0 !important}}
/* Streamlit 1.x top padding kill */
.appview-container .main .block-container{{padding-top:0 !important;padding-bottom:0 !important;padding-left:0 !important;padding-right:0 !important;max-width:100% !important}}

/* ── Page content area 내부 패딩 ── */
.page-content{{padding:20px 32px}}

/* ── Footer를 화면 하단 고정 ── */
.stApp [data-testid="stAppViewContainer"]{{min-height:100vh;display:flex;flex-direction:column}}
.stApp [data-testid="stAppViewContainer"] > section{{flex:1;display:flex;flex-direction:column}}
.stApp [data-testid="stAppViewContainer"] > section > div{{flex:1;display:flex;flex-direction:column}}
.ix-footer-wrap{{margin-top:auto}}

/* ── Top Navigation Bar ── */
.nav-bar{{
    background:linear-gradient(135deg,#0D0D0D 0%,#1A1A2E 100%);
    border-radius:0;padding:14px 36px;margin:0;width:100%;
    display:flex;align-items:center;justify-content:space-between;
    border-bottom:1px solid rgba(255,128,0,.15);box-sizing:border-box;
}}
.nav-bar .brand{{font-size:1.4rem;font-weight:900;letter-spacing:-1.5px}}
.nav-bar .brand span{{color:#fff}} .nav-bar .brand b{{color:{P}}}
.nav-bar .meta{{display:flex;align-items:center;gap:16px}}
.nav-bar .meta-item{{
    color:rgba(255,255,255,.35);font-size:.68rem;font-weight:500;letter-spacing:.5px;
    display:flex;align-items:center;gap:5px;
}}
.nav-bar .meta-dot{{width:5px;height:5px;border-radius:50%;background:#22C55E;display:inline-block}}

/* ── Hero Banner (removed — sidebar branding) ── */

/* ── Content wrapper spacing ── */
.content-spacer{{height:28px}}

/* ── Metric Card v6 — Glass morphism ── */
.m-card{{
    background:{W};border:1px solid rgba(0,0,0,.06);border-radius:14px;padding:22px 20px;
    box-shadow:0 1px 3px rgba(0,0,0,.04),0 4px 12px rgba(0,0,0,.02);
    position:relative;overflow:hidden;transition:all .35s cubic-bezier(.25,.8,.25,1);
}}
.m-card::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,{P},#FFB347);transform:scaleX(0);transform-origin:left;
    transition:transform .35s cubic-bezier(.25,.8,.25,1);
}}
.m-card:hover{{
    border-color:rgba(255,128,0,.2);
    box-shadow:0 4px 20px rgba(255,128,0,.1),0 1px 3px rgba(0,0,0,.04);
    transform:translateY(-3px);
}}
.m-card:hover::before{{transform:scaleX(1)}}
.m-val{{font-size:1.85rem;font-weight:800;color:#1A1A2E;line-height:1.1;letter-spacing:-1px}}
.m-label{{font-size:.65rem;color:{S5};margin-top:8px;font-weight:600;text-transform:uppercase;letter-spacing:1px}}

/* ── Section Header v6 ── */
.sec-h{{
    display:flex;align-items:center;gap:10px;margin:30px 0 16px;
}}
.sec-h .dot{{width:3px;height:22px;border-radius:2px;background:linear-gradient(180deg,{P},#FFB347)}}
.sec-h .txt{{font-size:.9rem;font-weight:700;color:#1A1A2E;letter-spacing:-.3px}}

/* ── Notice Row v6 ── */
.n-row{{
    background:{W};border:1px solid rgba(0,0,0,.06);border-radius:12px;
    padding:14px 18px;margin-bottom:6px;
    border-left:3px solid transparent;transition:all .25s cubic-bezier(.25,.8,.25,1);
    cursor:default;display:flex;align-items:center;gap:14px;
}}
.n-row:hover{{
    border-left-color:{P};background:#FEFAF6;
    box-shadow:0 2px 12px rgba(255,128,0,.06);transform:translateX(2px);
}}
.n-badge{{
    min-width:34px;height:26px;display:inline-flex;align-items:center;justify-content:center;
    border-radius:7px;font-size:.72rem;font-weight:800;color:{W};flex-shrink:0;
    box-shadow:0 1px 3px rgba(0,0,0,.12);
}}
.n-title{{font-size:.85rem;font-weight:600;color:#1A1A2E;flex:1;line-height:1.4}}
.n-meta{{font-size:.72rem;color:{S4};font-weight:500}}

/* ── Status Pill v6 ── */
.pill{{
    display:inline-flex;align-items:center;gap:4px;
    padding:3px 10px;border-radius:20px;font-size:.68rem;font-weight:600;
    backdrop-filter:blur(4px);
}}
.pill-a{{background:#ECFDF5;color:#065F46}} .pill-b{{background:#EFF6FF;color:#1E40AF}}
.pill-c{{background:#FFFBEB;color:#92400E}} .pill-d{{background:#FEF2F2;color:#991B1B}}
.pill-l3{{background:#FDF2F8;color:#9D174D}}
.pill-urgent{{background:#FEF2F2;color:#DC2626;border:1px solid #FECACA;animation:pulse-urgent 2s ease infinite}}
@keyframes pulse-urgent{{0%,100%{{opacity:1}}50%{{opacity:.7}}}}

/* ── Data Table ── */
.stDataFrame{{border-radius:12px;overflow:hidden;border:1px solid rgba(0,0,0,.06)}}
.stDataFrame [data-testid="stDataFrameResizable"]{{border-radius:12px}}

/* ── Tabs (hidden — using sidebar nav) ── */

/* ── Button v6 ── */
.stButton>button{{
    background:linear-gradient(135deg,#1A1A2E,#2D2D44);
    color:{W};font-weight:700;border:none;border-radius:10px;
    padding:.65rem 2rem;font-size:.83rem;letter-spacing:.3px;
    transition:all .35s cubic-bezier(.25,.8,.25,1);
    box-shadow:0 2px 8px rgba(0,0,0,.12);
}}
.stButton>button:hover{{
    background:linear-gradient(135deg,{P},{P_L});
    box-shadow:0 4px 20px rgba(255,128,0,.3);transform:translateY(-2px);
}}

/* ── Form submit (primary) ── */
.stFormSubmitButton>button{{
    background:linear-gradient(135deg,{P},{P_L});
    border:none;font-weight:700;border-radius:10px;
    box-shadow:0 2px 12px rgba(255,128,0,.2);
}}
.stFormSubmitButton>button:hover{{
    box-shadow:0 4px 24px rgba(255,128,0,.35);transform:translateY(-2px);
}}

/* ── Progress ── */
.stProgress>div>div>div>div{{background:linear-gradient(90deg,{P},{P_L});border-radius:4px}}

/* ── Inputs ── */
.stSelectbox label,.stMultiSelect label,.stSlider label{{font-weight:600;color:#1A1A2E;font-size:.8rem}}
.stTextInput>div>div>input{{border-radius:10px;border-color:rgba(0,0,0,.08)}}
.stTextInput>div>div>input:focus{{border-color:{P};box-shadow:0 0 0 2px rgba(255,128,0,.1)}}

/* ── Expander ── */
.streamlit-expanderHeader{{font-weight:600;font-size:.83rem;color:#1A1A2E}}

/* ── Empty State ── */
.empty{{text-align:center;padding:5rem 0}}
.empty .icon{{font-size:2.5rem;margin-bottom:14px;opacity:.5}}
.empty .heading{{font-size:1.05rem;font-weight:700;color:#1A1A2E;margin-bottom:8px}}
.empty .desc{{font-size:.83rem;color:{S5};line-height:1.6;max-width:440px;margin:0 auto}}
.empty .action{{
    display:inline-block;margin-top:20px;padding:10px 24px;
    background:linear-gradient(135deg,{P},{P_L});color:{W};
    border-radius:10px;font-size:.82rem;font-weight:700;text-decoration:none;
    box-shadow:0 2px 12px rgba(255,128,0,.2);
}}

/* ── Footer Banner — interxlab.com ── */
.ix-footer{{
    background:linear-gradient(135deg,#0D0D0D 0%,#1A1A2E 100%);
    margin:0;padding:48px 40px 36px;width:100%;box-sizing:border-box;
}}
.ix-footer .ft-brand{{font-size:1.6rem;font-weight:900;letter-spacing:-1.5px;margin-bottom:20px}}
.ix-footer .ft-brand span{{color:#fff}} .ix-footer .ft-brand b{{color:{P}}}
.ix-footer .ft-email{{color:rgba(255,255,255,.4);font-size:.82rem;margin-bottom:24px;font-weight:400}}
.ix-footer .ft-divider{{border:none;border-top:1px solid rgba(255,255,255,.06);margin:24px 0}}
.ix-footer .ft-copy{{color:rgba(255,255,255,.2);font-size:.72rem;letter-spacing:.5px}}
.ix-footer .ft-links{{display:flex;gap:20px;margin-top:12px}}
.ix-footer .ft-links a{{
    color:rgba(255,255,255,.3);font-size:.72rem;text-decoration:none;font-weight:500;
    transition:color .2s;
}}
.ix-footer .ft-links a:hover{{color:{P}}}

/* ── Chat ── */
.stChatMessage{{border-radius:12px}}
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

# ── Sidebar Navigation ──
with st.sidebar:
    st.markdown(f'<div style="padding:18px 12px 10px;text-align:center"><div style="font-size:1.5rem;font-weight:900;letter-spacing:-1.5px"><span style="color:{S8}">INTER</span><span style="color:{P}">X</span></div><div style="color:{S4};font-size:.62rem;letter-spacing:4px;margin-top:4px">INTELLIGENCE ENGINE</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="border-top:1px solid rgba(0,0,0,.06);margin:8px 0 12px"></div>', unsafe_allow_html=True)

    NAV_ITEMS = [
        "📊 대시보드", "⚡ 수집 실행", "📋 공고 목록", "📝 제안서", "🏢 경쟁사",
        "🎯 수주 예측", "📅 마감 캘린더", "🔧 솔루션", "📈 키워드", "👤 담당자",
        "🕐 히스토리", "🤖 AI 뉴스", "💬 AI 챗봇",
    ]
    page = st.radio("메뉴", NAV_ITEMS, label_visibility="collapsed", key="nav_page")

    st.markdown(f'<div style="border-top:1px solid rgba(0,0,0,.06);margin:16px 0 12px"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="padding:0 12px"><div style="display:flex;align-items:center;gap:6px;font-size:.68rem;color:{S4}"><span style="width:5px;height:5px;border-radius:50%;background:#22C55E;display:inline-block"></span> LIVE · v5.9 · 25 Sites · ML v2</div></div>', unsafe_allow_html=True)

# ── Compact Top Bar (full-width) ──
st.markdown(f"""<div class="nav-bar">
    <div><div class="brand"><span>INTER</span><b>X</b></div></div>
    <div class="meta">
        <div class="meta-item"><span class="meta-dot"></span> LIVE</div>
        <div class="meta-item">v5.9</div>
        <div class="meta-item">25 SITES</div>
        <div class="meta-item">ML v2</div>
    </div>
</div>
<div class="page-content">""", unsafe_allow_html=True)

for key, default in [("pipeline_result", None), ("pipeline_running", False),
                      ("collection_history", []), ("selected_notice_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = default

ALL_SITES = ["bizinfo","kiat","nipa","innopolis","bipa","uipa","gicon","ttp","gjtp","kised","ketep","koiia","jejutp","smart_factory","iitp",
             "seoultp","gdtp","gwtp","sjtp","cbtp","ctp","btp","utp","gntp","ptp"]

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE · Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📊 대시보드":
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
                    # 핵심 내용 미리보기 (구조화 섹션 없을 때)
                    if not _struct:
                        _body = getattr(n, "body_text", "") or ""
                        _body = re.sub(r'\{\{[^}]+\}\}', '', _body).strip()
                        if _body and _body.startswith("[첨부:"):
                            st.caption("📎 OCR: 첨부파일에서 텍스트 자동 추출됨")
                        if _body and len(_body) > 20:
                            # 메타데이터/잡음 패턴 제거 후 핵심 문장 추출
                            _junk_re = re.compile(
                                r"(작성일|작성자|조회수|다운로드|첨부파일|담당자\s*연락처|담당자\s*이메일|"
                                r"\.pdf|\.hwp|\.xlsx|\.docx|KB\)|MB\)|로그인|회원가입|"
                                r"주메뉴|바로가기|MAIN\s*TOPIC|홈\s*>|Ⅰ\.|Ⅱ\.|작성자\s|"
                                r"접수기간\s*\d|조회수\s*\d|^\d{2}-\d{2}-\d{2}$)", re.I)
                            _imp_re = re.compile(
                                r"(지원\s*대상|지원\s*내용|지원\s*규모|신청\s*자격|접수\s*기간|"
                                r"사업\s*목적|사업\s*내용|모집\s*기간|총\s*사업비|선정\s*규모|"
                                r"사업\s*개요|참여\s*자격|공모\s*분야|수행\s*기간|과제당)")
                            _sents = [s.strip() for s in re.split(r'(?<=[.다요됨함!\n])\s+', _body)
                                      if len(s.strip()) > 25 and not _junk_re.search(s)]
                            _imp = [s for s in _sents if _imp_re.search(s)][:3]
                            if _imp:
                                st.markdown("**📋 핵심 내용**:")
                                for _is in _imp:
                                    st.markdown(f"- {_is[:200]}")
                            elif _sents:
                                st.markdown(f"**📋 핵심 내용**: {_sents[0][:300]}")
                    # 원문 바로가기 + 원문 미리보기 iframe
                    _detail = getattr(n, "detail_url", "") or ""
                    if _detail and _detail.startswith("http"):
                        st.markdown(f"🔗 **[원문 바로가기 (새 탭)]({_detail})**")
                        st.caption("⚠️ 일부 사이트는 보안 정책으로 미리보기가 차단됩니다.")
                        st.iframe(_detail, height=480)

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
#  PAGE · Pipeline Runner
# ═══════════════════════════════════════════════════════════════════════════════

if page == "⚡ 수집 실행":
    # ── 실행 중이면 설정 폼 숨기고 상태만 표시 ──
    if not st.session_state.pipeline_running:
        st.markdown(_section("수집 설정"), unsafe_allow_html=True)
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
            run_clicked = st.form_submit_button("⚡ 수집 시작", type="primary", use_container_width=True)
    else:
        run_clicked = False
        selected_sites = ALL_SITES
        run_mode = "일반 수집 (빠름)"
        max_pages = 5
        enable_sheets = True
        ml = "일반"

    if st.session_state.pipeline_result and not st.session_state.pipeline_running:
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
#  PAGE · Notice List + Detail
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📋 공고 목록":
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
                body = re.sub(r'\{\{[^}]+\}\}', '', body).strip()

                # OCR 보강 표시 (body_text가 첨부파일에서 추출된 경우)
                if body and body.startswith("[첨부:"):
                    st.caption("📎 OCR: 첨부파일에서 텍스트 자동 추출됨")

                _sn_struct = getattr(sn, "structured", None) or {}
                _sn_summary = getattr(sn, "summary", "") or ""
                _sn_summary = re.sub(r'\{\{[^}]+\}\}', '', _sn_summary).strip()
                # 핵심 내용 요약 (구조화 > summary > 키워드 문장)
                if _sn_struct or _sn_summary or (body and len(body) > 20):
                    with st.expander("📋 공고 핵심 내용", expanded=False):
                        # 구조화 섹션
                        for _sk2, _sl2 in [("사업목적","🎯 사업목적"), ("지원내용","💰 지원내용"),
                                           ("지원대상","👥 지원대상"), ("지원금액","💵 지원금액"),
                                           ("신청방법","📝 신청방법"), ("추진일정","📅 추진일정")]:
                            _sv2 = _sn_struct.get(_sk2, "")
                            if _sv2:
                                st.markdown(f"**{_sl2}**")
                                st.markdown(f"> {_sv2[:300]}")
                        # summary (핵심 문장)
                        if not _sn_struct and _sn_summary and len(_sn_summary) > 20:
                            st.markdown("**📌 핵심 요약**")
                            st.markdown(f"> {_sn_summary[:400]}")
                        # 전체 본문 (접기)
                        if body and len(body) > 50:
                            st.markdown("---")
                            st.caption("📄 전체 본문")
                            st.text(body[:5000])
                            if len(body) > 5000: st.caption(f"전체 {len(body):,}자 중 5,000자 표시")

                # ── AI 분석 ──
                _ai_key = f"ai_analysis_{sn.notice_id}"
                if st.button("💡 AI 분석", key=_ai_key, help="Gemini AI로 공고 적합도 분석 및 제안 전략 생성"):
                    with st.spinner("AI 분석 중..."):
                        try:
                            from interx_engine.infrastructure.ai.notice_analyzer import analyze_notice
                            _ai_result = analyze_notice(
                                title=sn.title,
                                body_text=body,
                                summary=_sn_summary,
                                structured=_sn_struct,
                                matched_keywords=", ".join(ssc.positive_keywords[:8]) if ssc and ssc.positive_keywords else "",
                                grade=grade,
                                score=ssc.fitness_score if ssc else 0,
                                budget=sn.budget or "",
                                solution_scores=ssc.solution_scores if ssc else None,
                            )
                            st.markdown(f"""<div style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border:1px solid #bae6fd;border-radius:12px;padding:16px 20px;margin:10px 0">
                                <div style="font-size:.85rem;font-weight:700;color:#0369a1;margin-bottom:8px">💡 AI 분석 결과</div>
                                <div style="font-size:.82rem;color:#1e3a5f;margin-bottom:6px"><b>적합도:</b> {_ai_result.get('fit_reason','')}</div>
                                <div style="font-size:.82rem;color:#1e3a5f;margin-bottom:6px"><b>제안 전략:</b> {_ai_result.get('proposal_strategy','')}</div>
                                <div style="font-size:.82rem;color:#1e3a5f;margin-bottom:6px"><b>솔루션 매핑:</b> {_ai_result.get('solution_mapping','')}</div>
                                <div style="font-size:.82rem;color:#1e3a5f;margin-bottom:6px"><b>핵심 요구:</b> {_ai_result.get('key_requirements','')}</div>
                                <div style="font-size:.78rem;color:#b45309"><b>리스크:</b> {_ai_result.get('risk_factors','')}</div>
                            </div>""", unsafe_allow_html=True)
                        except Exception as _ai_err:
                            st.error(f"AI 분석 실패: {_ai_err}")

                # ── 원문 바로가기 ──
                _sn_link = getattr(sn, "detail_url", "") or ""
                if _sn_link and _sn_link.startswith("http"):
                    st.markdown(f"🔗 **[원문 바로가기 (새 탭에서 열기)]({_sn_link})**")
                    with st.expander("🌐 원문 사이트 미리보기", expanded=False):
                        st.caption("⚠️ 일부 사이트는 보안 정책으로 미리보기가 차단됩니다. 차단 시 위 링크를 이용하세요.")
                        st.iframe(_sn_link, height=560)
        else:
            st.info("필터 조건에 맞는 공고가 없습니다.")


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE · Proposals
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📝 제안서":
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
#  PAGE · Competitor Analysis
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🏢 경쟁사":
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
#  PAGE · Win Prediction
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🎯 수주 예측":
    result = _result()
    if not result:
        st.markdown(_empty("🎯", "수주 예측 데이터 없음", "수집 실행 후 공고별 수주 확률을 예측합니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        from interx_engine.application.use_cases.win_prediction import WinPredictionUseCase, _extract_v2_features, _WEIGHTS_V2
        notices = result.get("notices", []); smap = _smap(result)

        # ── ML 엔진 v2로 수주 예측 ──
        _wp_uc = WinPredictionUseCase()
        _wp_info = _wp_uc.model_info
        preds = []
        for n in notices:
            sc = smap.get(n.notice_id)
            if not sc: continue
            feats = _extract_v2_features(n, sc)
            wp = sum(_WEIGHTS_V2.get(k, 0) * v for k, v in feats.items() if k in _WEIGHTS_V2)
            wp = min(1.0, max(0.0, wp)) * 100
            preds.append({"notice":n, "sc":sc, "wp":wp, "feats":feats})
        preds.sort(key=lambda x:-x["wp"])

        hp = sum(1 for p in preds if p["wp"]>=60)
        avg = sum(p["wp"] for p in preds)/max(1,len(preds))
        k1,k2,k3,k4 = st.columns(4)
        k1.markdown(_metric(len(preds), "예측 대상"), unsafe_allow_html=True)
        k2.markdown(_metric(hp, "유망 60%+", GA), unsafe_allow_html=True)
        k3.markdown(_metric(f"{avg:.0f}%", "평균 확률"), unsafe_allow_html=True)
        _ml_label = f'{_wp_info["model"]}' if _wp_info["mode"] == "ml" else "RuleV2"
        k4.markdown(_metric(_ml_label, "ML 모델", A2), unsafe_allow_html=True)

        # ── ML 모델 정보 배너 ──
        _ml_badge_color = GA if _wp_info["mode"] == "ml" else P
        _ml_status = "ML 활성" if _wp_info["mode"] == "ml" else "룰 기반 (학습 데이터 수집 중)"
        st.markdown(f'<div style="background:{S0};border:1px solid {S2};border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;gap:12px"><span style="background:{_ml_badge_color};color:{W};padding:3px 10px;border-radius:6px;font-size:.72rem;font-weight:700">{_ml_status}</span><span style="font-size:.78rem;color:{S5}">v2 피처 10개 · {_wp_info.get("accuracy","—")} 정확도 · 수집 실행마다 학습 데이터 자동 저장</span></div>', unsafe_allow_html=True)

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
                n,sc,wp,feats = p["notice"],p["sc"],p["wp"],p["feats"]
                c = GA if wp>=60 else GB if wp>=40 else GC
                meta = f"{sc.priority_grade}등급 · {n.site} · {n.agency or '-'} · {n.deadline_date or '-'}"
                st.markdown(_notice_row(sc.priority_grade, f'<span style="color:{c};font-weight:800">{wp:.0f}%</span> {n.title[:50]}', meta), unsafe_allow_html=True)
                with st.expander("🔍 수주 가능성 분석", expanded=False):
                    # v2 피처별 기여도 시각화
                    _feat_labels = {
                        "fitness_score": "키워드 적합도", "priority_score": "우선순위",
                        "budget_score": "예산 기여", "dday_urgency": "마감 긴급도",
                        "l3_flag": "L3 강공고", "industry_score": "솔루션 매칭",
                        "tfidf_similarity": "InterX 유사도", "keyword_density": "키워드 밀도",
                        "type_multiplier": "공고 유형", "combo_count": "콤보 키워드",
                    }
                    _bar_html = ""
                    for _fk, _fl in _feat_labels.items():
                        _fv = feats.get(_fk, 0) * _WEIGHTS_V2.get(_fk, 0) * 100
                        _raw = feats.get(_fk, 0)
                        _w = _WEIGHTS_V2.get(_fk, 0)
                        _bw = max(2, min(100, _fv * 4))
                        _bc2 = GA if _fv >= 8 else GB if _fv >= 4 else GC if _fv >= 1 else S4
                        _bar_html += f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:.78rem"><span style="width:100px;color:{S5};font-weight:600;text-align:right">{_fl}</span><div style="flex:1;background:{S1};border-radius:4px;height:18px;overflow:hidden"><div style="width:{_bw}%;height:100%;background:{_bc2};border-radius:4px"></div></div><span style="width:100px;color:{S4};font-size:.72rem">{_raw:.2f}x{_w:.2f}={_fv:.1f}</span></div>'
                    st.markdown(f'<div style="padding:4px 0">{_bar_html}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="text-align:right;font-size:.85rem;font-weight:800;color:{c};margin-top:6px">합계: {wp:.0f}%</div>', unsafe_allow_html=True)
                    # 핵심 근거 요약
                    _f = sc.fitness_score or 0; _dd = _dday(n.deadline_date or "")
                    _reasons = []
                    if _f >= 40: _reasons.append(f"키워드 적합도 높음 ({_f:.0f}점)")
                    if sc.positive_keywords: _reasons.append(f"매칭 키워드: {', '.join(sc.positive_keywords[:5])}")
                    if n.l3_strong == "Y": _reasons.append("L3 강공고 해당")
                    if sc.tfidf_similarity >= 0.3: _reasons.append(f"InterX 유사도 {sc.tfidf_similarity:.0%}")
                    if sc.combo_keywords: _reasons.append(f"콤보: {', '.join(sc.combo_keywords[:3])}")
                    if 0 <= _dd <= 7: _reasons.append(f"마감 임박 D-{_dd}")
                    sol_hits = [(s,v) for s,v in (sc.solution_scores or {}).items() if v > 0]
                    if sol_hits: _reasons.append(f"솔루션: {', '.join(s for s,_ in sorted(sol_hits, key=lambda x:-x[1])[:3])}")
                    if _reasons:
                        st.markdown("**📌 핵심 근거**: " + " · ".join(_reasons))

        # ── ML 학습 데이터 현황 ──
        st.markdown(_section("🤖 ML 학습 데이터 현황"), unsafe_allow_html=True)
        _train_dir = ROOT / "data" / "exports" / "training"
        if _train_dir.exists():
            _jsonl_files = sorted(_train_dir.glob("*.jsonl"), reverse=True)
            _total_lines = 0
            for _jf in _jsonl_files[:10]:
                _total_lines += sum(1 for line in _jf.read_text(encoding="utf-8").splitlines() if line.strip())
            st.markdown(f'<div style="background:{S0};border-radius:10px;padding:12px 16px;font-size:.82rem;color:{CH}">JSONL 파일 <b>{len(_jsonl_files)}</b>개 · 총 <b>{_total_lines}</b>건 · 20건 이상 시 ML 학습 가능</div>', unsafe_allow_html=True)
            if _total_lines >= 20:
                if st.button("🧠 ML 모델 학습 실행", key="train_ml"):
                    with st.spinner("ML 모델 학습 중..."):
                        try:
                            from interx_engine.application.use_cases.win_prediction import WinPredictionTrainer
                            trainer = WinPredictionTrainer()
                            result_ml = trainer.train()
                            st.success(f"학습 완료! 모델: {result_ml['model_type']} · 정확도: {result_ml['accuracy']:.1%} · 샘플: {result_ml['n_samples']}건")
                            if result_ml.get("feature_importance"):
                                fi = result_ml["feature_importance"]
                                fig_fi = go.Figure(go.Bar(
                                    x=list(fi.values()), y=list(fi.keys()),
                                    orientation='h', marker_color=P,
                                ))
                                fig_fi.update_layout(title=dict(text="피처 중요도",font=dict(size=14,color=S8)),
                                    height=300, xaxis=dict(title="중요도"), **_layout())
                                st.plotly_chart(fig_fi, width="stretch")
                        except Exception as e:
                            st.error(f"학습 실패: {e}")
        else:
            st.markdown(f'<div style="font-size:.82rem;color:{S4};padding:8px">수집을 실행하면 학습 데이터가 자동으로 축적됩니다.</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE · Deadline Calendar
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📅 마감 캘린더":
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
#  PAGE · Solution Matching
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🔧 솔루션":
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
#  PAGE · Keyword Trends
# ═══════════════════════════════════════════════════════════════════════════════

if page == "📈 키워드":
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
#  PAGE · Manager Overview
# ═══════════════════════════════════════════════════════════════════════════════

if page == "👤 담당자":
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
#  PAGE · Collection History
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🕐 히스토리":
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
#  PAGE · AI News & Trends
# ═══════════════════════════════════════════════════════════════════════════════

if page == "🤖 AI 뉴스":
    import xml.etree.ElementTree as ET
    import requests as _req
    from html import unescape as _unescape

    @st.cache_data(ttl=1800, show_spinner=False)  # 30분 캐시
    def _fetch_rss(url, limit=8):
        """RSS 피드에서 뉴스 항목 파싱 (핵심 요약 포함)"""
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
                # content:encoded 가 있으면 더 풍부한 본문 사용
                content_encoded = ""
                for el in item:
                    if el.tag.endswith("encoded") or el.tag.endswith("content"):
                        content_encoded = (el.text or "").strip()
                        break
                pub = (item.findtext("pubDate") or "").strip()
                if not title: continue
                # HTML 태그 제거 + unescape
                raw = content_encoded if len(content_encoded) > len(desc) else desc
                raw = re.sub(r'<[^>]+>', '', _unescape(raw)).strip()
                # 핵심 문장 추출 (마침표 기준 3문장)
                sents = [s.strip() for s in re.split(r'(?<=[.다요됨함])\s+', raw) if len(s.strip()) > 15]
                summary_bullets = sents[:3] if sents else [raw[:300]]
                items.append({
                    "title": _unescape(title), "link": link,
                    "desc": raw[:200],  # 짧은 미리보기
                    "summary": summary_bullets,  # 핵심 요약 문장들
                    "full_desc": raw[:800],  # 전체 요약
                    "date": pub[:16] if pub else "",
                })
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
                    raw_text = ""
                    for s in entry.iter():
                        if s.tag.endswith("content") or s.tag.endswith("summary"):
                            raw_text = (s.text or "").strip(); break
                    if not title: continue
                    raw_text = re.sub(r'<[^>]+>', '', _unescape(raw_text)).strip()
                    sents = [s.strip() for s in re.split(r'(?<=[.다요됨함])\s+', raw_text) if len(s.strip()) > 15]
                    items.append({
                        "title": _unescape(title), "link": link,
                        "desc": raw_text[:200],
                        "summary": sents[:3] if sents else [raw_text[:300]],
                        "full_desc": raw_text[:800],
                        "date": "",
                    })
                    if len(items) >= limit: break
            return items
        except Exception:
            return []

    @st.cache_data(ttl=3600, show_spinner=False)
    def _fetch_article_summary(url):
        """기사 원문에서 핵심 내용 추출"""
        try:
            r = _req.get(url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            r.raise_for_status()
            from bs4 import BeautifulSoup as _BS
            soup = _BS(r.text, "html.parser")
            # 불필요 태그 제거
            for tag in soup(["script","style","nav","header","footer","aside","noscript","iframe"]):
                tag.decompose()
            # 본문 추출 (article > div.content > p 순서로 시도)
            article = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|body|entry"))
            target = article if article else soup
            paragraphs = target.find_all("p")
            text_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
            if not text_parts:
                text_parts = [target.get_text(" ", strip=True)[:1500]]
            full = " ".join(text_parts[:10])
            # 핵심 문장 추출 (5문장)
            sents = [s.strip() for s in re.split(r'(?<=[.다요됨함!?])\s+', full) if len(s.strip()) > 20]
            return sents[:5] if sents else [full[:500]]
        except Exception:
            return []

    st.markdown(_section("🤖 AI 팩토리 · 제조AI · IT 산업 뉴스"), unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:.8rem;color:{S4}">RSS 피드 기반 실시간 뉴스 · 30분 캐시 · 기사 클릭 시 핵심 요약 표시</p>', unsafe_allow_html=True)

    _rss_feeds = [
        {"cat": "🏭 AI·제조·스마트공장", "feeds": [
            ("AI타임스", "https://www.aitimes.com/rss/allArticle.xml"),
            ("로봇신문", "https://www.irobotnews.com/rss/allArticle.xml"),
            ("전자신문 AI", "https://rss.etnews.com/Section902.xml"),
        ]},
        {"cat": "📊 IT·산업 동향", "feeds": [
            ("전자신문 IT", "https://rss.etnews.com/Section901.xml"),
            ("디지털데일리", "https://www.ddaily.co.kr/rss/rss.aspx"),
            ("테크M", "https://www.techm.kr/rss/allArticle.xml"),
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
            for _ni, it in enumerate(items):
                _date_str = f' · {it["date"]}' if it["date"] else ""
                # ── 뉴스 카드 (제목 + RSS 요약) ──
                st.markdown(f'''<div style="background:{W};border:1px solid {S2};border-radius:10px;padding:14px 18px;margin-bottom:4px">
<a href="{it["link"]}" target="_blank" style="text-decoration:none;color:{S8};font-weight:700;font-size:.88rem;line-height:1.4">{it["title"]}</a>
<span style="font-size:.72rem;color:{S4}">{_date_str}</span>
<div style="font-size:.78rem;color:{S5};margin-top:6px;line-height:1.55">{it["desc"]}</div>
</div>''', unsafe_allow_html=True)
                # ── 핵심 요약 (RSS 본문 기반 + 원문 fetch) ──
                _exp_key = f"news_{feed_name}_{_ni}"
                with st.expander("📌 핵심 내용 보기", expanded=False):
                    # 1) RSS 본문 요약
                    if it["summary"] and it["summary"][0]:
                        for _si, _sent in enumerate(it["summary"]):
                            if _sent and len(_sent) > 10:
                                st.markdown(f'<div style="font-size:.82rem;color:{CH};line-height:1.6;padding:2px 0 2px 12px;border-left:2px solid {P}"><b>{_si+1}.</b> {_sent[:200]}</div>', unsafe_allow_html=True)
                    # 2) 원문에서 추가 요약 (버튼 클릭 시)
                    if it.get("link"):
                        if st.button("📖 원문 상세 요약 가져오기", key=f"fetch_{_exp_key}"):
                            with st.spinner("기사 본문 분석중..."):
                                _art_sents = _fetch_article_summary(it["link"])
                            if _art_sents:
                                st.markdown(f'<div style="background:{S0};border-radius:8px;padding:12px 16px;margin-top:8px">', unsafe_allow_html=True)
                                st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:{P};margin-bottom:8px">📰 기사 핵심 요약</div>', unsafe_allow_html=True)
                                for _ai, _as in enumerate(_art_sents):
                                    st.markdown(f'<div style="font-size:.82rem;color:{CH};line-height:1.6;padding:3px 0 3px 14px;border-left:2px solid {A2}"><b>▸</b> {_as[:250]}</div>', unsafe_allow_html=True)
                                st.markdown('</div>', unsafe_allow_html=True)
                            else:
                                st.caption("원문 요약을 가져올 수 없습니다. 위 링크를 직접 방문해주세요.")
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


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE · AI Chatbot (RAG)
# ═══════════════════════════════════════════════════════════════════════════════

if page == "💬 AI 챗봇":
    st.markdown(_section("💬 AI 공고 분석 챗봇"), unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:.8rem;color:{S4}">수집된 공고 데이터 기반 자연어 질의응답 · Gemini 무료 API · GEMINI_API_KEY 설정 필요</p>', unsafe_allow_html=True)

    # Gemini API 상태 표시
    try:
        from interx_engine.infrastructure.ai.gemini_client import is_available as _ai_available
        _has_ai = _ai_available()
    except Exception:
        _has_ai = False

    if _has_ai:
        st.markdown(f'<div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:8px 14px;font-size:.8rem;color:#065f46;margin-bottom:12px">✅ Gemini AI 연결됨 — 자연어 질문이 가능합니다</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:8px 14px;font-size:.8rem;color:#92400e;margin-bottom:12px">⚠️ GEMINI_API_KEY 미설정 — 규칙 기반 검색만 가능합니다. <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#d97706;font-weight:700">무료 발급 →</a></div>', unsafe_allow_html=True)

    # 채팅 히스토리
    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    # 예시 질문
    st.markdown(f'<div style="font-size:.78rem;color:{S5};margin-bottom:8px">💡 예시 질문:</div>', unsafe_allow_html=True)
    _example_qs = ["A등급 공고 중 스마트공장 관련은?", "마감 7일 이내 공고 요약해줘", "이번에 수집된 L3 강공고는?", "디지털트윈 관련 공고 추천해줘"]
    _eq_cols = st.columns(len(_example_qs))
    for _eqi, _eq in enumerate(_example_qs):
        if _eq_cols[_eqi].button(_eq, key=f"eq_{_eqi}", use_container_width=True):
            st.session_state.ai_chat_input = _eq

    # 채팅 표시
    for _msg in st.session_state.ai_chat_history:
        with st.chat_message(_msg["role"]):
            st.markdown(_msg["content"])

    # 입력
    _default_input = st.session_state.pop("ai_chat_input", "")
    _user_q = st.chat_input("공고에 대해 무엇이든 질문하세요...", key="ai_chat_box")
    if _default_input and not _user_q:
        _user_q = _default_input

    if _user_q:
        # 사용자 메시지 표시
        st.session_state.ai_chat_history.append({"role": "user", "content": _user_q})
        with st.chat_message("user"):
            st.markdown(_user_q)

        # AI 답변
        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                try:
                    result = _result()
                    _all_notices = result.get("notices", []) if result else []
                    _all_scores = result.get("score_cards", []) if result else []
                    _sc_map = {s.notice_id: s for s in _all_scores}

                    from interx_engine.infrastructure.ai.chatbot import answer_question
                    _answer = answer_question(
                        question=_user_q,
                        notices=_all_notices,
                        score_map=_sc_map,
                        chat_history=st.session_state.ai_chat_history[:-1],  # 현재 질문 제외
                    )
                    st.markdown(_answer)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": _answer})
                except Exception as _chat_err:
                    _err_msg = f"답변 생성 실패: {_chat_err}"
                    st.error(_err_msg)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": _err_msg})

    # 일일 브리핑 버튼
    st.markdown("---")
    st.markdown(f'<div style="font-size:.9rem;font-weight:700;color:{S8};margin:8px 0">📋 일일 브리핑 자동 생성</div>', unsafe_allow_html=True)
    if st.button("📋 오늘의 브리핑 생성", key="gen_briefing"):
        with st.spinner("브리핑 생성 중..."):
            try:
                result = _result()
                _all_notices = result.get("notices", []) if result else []
                _all_scores = result.get("score_cards", []) if result else []
                _sc_map = {s.notice_id: s for s in _all_scores}
                _exec_id = result.get("execution_id", "") if result else ""

                from interx_engine.infrastructure.ai.briefing_generator import generate_briefing
                _briefing = generate_briefing(
                    notices=_all_notices,
                    score_map=_sc_map,
                    execution_id=_exec_id,
                )
                st.markdown(f'<div style="background:{S0};border:1px solid {S2};border-radius:12px;padding:16px 20px;font-size:.85rem;color:{CH};white-space:pre-wrap;line-height:1.7">{_briefing}</div>', unsafe_allow_html=True)
                st.download_button("📥 브리핑 텍스트 다운로드", _briefing, "interx_briefing.txt", "text/plain")
            except Exception as _br_err:
                st.error(f"브리핑 생성 실패: {_br_err}")

    # 히스토리 초기화
    if st.session_state.ai_chat_history:
        if st.button("🗑️ 대화 초기화", key="clear_chat"):
            st.session_state.ai_chat_history = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  FOOTER — interxlab.com 스타일
# ═══════════════════════════════════════════════════════════════════════════════

# page-content div 닫기 + footer (margin-top:auto로 화면 하단 밀착)
st.markdown(f"""</div><div class="ix-footer-wrap"><div class="ix-footer">
    <div class="ft-brand"><span>INTER</span><b>X</b></div>
    <div class="ft-email">Email : ixg.innovation.dx_security@interxlab.com</div>
    <hr class="ft-divider">
    <div class="ft-copy">Copyright &copy; INTERX All rights reserved</div>
    <div class="ft-links">
        <a href="https://interxlab.com" target="_blank">interxlab.com</a>
        <a href="https://interx-gov-intel.streamlit.app" target="_blank">Intelligence Engine</a>
        <a href="https://github.com/KimDoojin2/interx-gov-intelligence" target="_blank">GitHub</a>
    </div>
</div></div>""", unsafe_allow_html=True)
