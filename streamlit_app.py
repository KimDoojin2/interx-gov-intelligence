"""
InterX Government Intelligence Engine — Enterprise Dashboard v7
Modern B2B SaaS Design (Palantir / Linear / Vercel inspired)
"""
from __future__ import annotations

import io, json, os, re, sys, time, hashlib
from collections import Counter, defaultdict
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# =============================================================================
#  Design System v7 — CSS Variable-based Dark/Light Mode
# =============================================================================
# Feature #8: Dark mode toggle support via CSS variables

def _get_theme():
    return st.session_state.get("theme_mode", "light")

def _is_dark():
    return _get_theme() == "dark"

# Brand colors (constant)
P = "#FF8000"
P_L = "#FF9F2E"
P_D = "#E67300"
A2 = "#3A7BEE"
GA = "#059669"; GB = "#2563EB"; GC = "#D97706"; GD = "#DC2626"
GRADE = {"A": GA, "B": GB, "C": GC, "D": GD}

# Theme-dependent tokens
def _t():
    if _is_dark():
        return dict(
            bg="#0A0A0F", bg2="#111118", bg3="#1A1A24",
            card="#14141E", card_hover="#1C1C28",
            border="rgba(255,255,255,.08)", border2="rgba(255,255,255,.12)",
            text="#E8E8ED", text2="#A0A0B0", text3="#6B6B7B",
            shadow="rgba(0,0,0,.4)", shadow2="rgba(0,0,0,.2)",
            nav_bg="linear-gradient(180deg,#08080D 0%,#0E0E16 100%)",
            input_bg="#1A1A24", table_stripe="rgba(255,255,255,.02)",
        )
    return dict(
        bg="#F8F9FC", bg2="#FFFFFF", bg3="#F1F3F9",
        card="#FFFFFF", card_hover="#FAFBFE",
        border="rgba(0,0,0,.06)", border2="rgba(0,0,0,.10)",
        text="#111827", text2="#6B7280", text3="#9CA3AF",
        shadow="rgba(0,0,0,.04)", shadow2="rgba(0,0,0,.02)",
        nav_bg="linear-gradient(180deg,#0D0D12 0%,#1A1A2E 100%)",
        input_bg="#F9FAFB", table_stripe="rgba(0,0,0,.015)",
    )

# ── Page Config ──
st.set_page_config(page_title="InterX Intelligence", page_icon="🔶", layout="wide", initial_sidebar_state="expanded")

# ── Intro animation ──
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = True
    st.markdown('<style>@keyframes ix-fade{0%{opacity:0;transform:scale(.85) translateY(14px)}15%{opacity:1;transform:scale(1.02)}40%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(.97) translateY(-8px)}}@keyframes ix-bg{0%,70%{opacity:1}100%{opacity:0;pointer-events:none;visibility:hidden}}.ix-intro{position:fixed;inset:0;z-index:99999;background:#000;display:flex;align-items:center;justify-content:center;animation:ix-bg 2.2s ease forwards}.ix-intro .logo{animation:ix-fade 2.2s ease forwards;text-align:center}.ix-intro .mark{font-size:3rem;font-weight:900;letter-spacing:-2px;font-family:Inter,system-ui,sans-serif}.ix-intro .mark b{color:#FF8000}.ix-intro .mark span{color:#fff}.ix-intro .sub{color:rgba(255,255,255,.4);font-size:.78rem;letter-spacing:4px;margin-top:10px;font-weight:500}</style><div class="ix-intro"><div class="logo"><div class="mark"><span>INTER</span><b>X</b></div><div class="sub">INTELLIGENCE ENGINE</div></div></div>', unsafe_allow_html=True)

# ── Enterprise CSS v7 ──
t = _t()
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Global ── */
.stApp{{background:{t['bg']};font-family:'Inter',system-ui,-apple-system,sans-serif;color:{t['text']}}}
#MainMenu,footer{{visibility:hidden}}
header[data-testid="stHeader"]{{background:transparent !important;backdrop-filter:none !important}}
button[kind="headerNoPadding"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"]{{visibility:visible !important;z-index:999 !important}}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{{
    background:{t['card']};min-width:260px;max-width:260px;
    border-right:1px solid {t['border']};
}}
section[data-testid="stSidebar"] .stRadio label{{color:{t['text']} !important;font-weight:600;font-size:.82rem}}
section[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"]{{color:{t['text']} !important}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label{{
    padding:10px 16px !important;border-radius:10px !important;margin:2px 0;transition:all .2s;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover{{
    background:rgba(255,128,0,.06) !important;
}}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:has(input:checked){{
    background:rgba(255,128,0,.10) !important;
    border-left:3px solid {P} !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{{color:{t['text3']} !important}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3{{color:{t['text']} !important}}

/* ── Layout ── */
.block-container,[data-testid="stMainBlockContainer"]{{
    padding-top:0 !important;padding-bottom:0 !important;
    padding-left:1.5rem !important;padding-right:1.5rem !important;max-width:100% !important;
}}

/* ── Top Nav ── */
.nav-bar{{
    background:{t['nav_bg']};padding:12px 32px;margin:0 -1.5rem 0 -1.5rem;
    display:flex;align-items:center;justify-content:space-between;
    border-bottom:1px solid rgba(255,128,0,.12);
}}
.nav-bar .brand{{font-size:1.3rem;font-weight:900;letter-spacing:-1.5px}}
.nav-bar .brand span{{color:#fff}}.nav-bar .brand b{{color:{P}}}
.nav-bar .meta{{display:flex;align-items:center;gap:18px}}
.nav-bar .meta-item{{color:rgba(255,255,255,.4);font-size:.68rem;font-weight:500;letter-spacing:.5px;display:flex;align-items:center;gap:5px}}
.nav-bar .meta-dot{{width:5px;height:5px;border-radius:50%;background:#22C55E;display:inline-block}}

/* ── KPI Card v7 ── */
.kpi-card{{
    background:{t['card']};border:1px solid {t['border']};border-radius:16px;padding:24px 22px;
    position:relative;overflow:hidden;transition:all .3s cubic-bezier(.25,.8,.25,1);
}}
.kpi-card::before{{
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,{P},{P_L});transform:scaleX(0);transform-origin:left;
    transition:transform .3s cubic-bezier(.25,.8,.25,1);
}}
.kpi-card:hover{{
    border-color:rgba(255,128,0,.2);box-shadow:0 8px 30px {t['shadow']};transform:translateY(-2px);
}}
.kpi-card:hover::before{{transform:scaleX(1)}}
.kpi-val{{font-size:2rem;font-weight:800;color:{t['text']};line-height:1;letter-spacing:-1px}}
.kpi-label{{font-size:.65rem;color:{t['text3']};margin-top:10px;font-weight:600;text-transform:uppercase;letter-spacing:1.2px}}
.kpi-delta{{font-size:.72rem;font-weight:700;margin-top:4px}}
.kpi-delta.up{{color:{GA}}}.kpi-delta.down{{color:{GD}}}

/* ── Section Header v7 ── */
.sec-h{{display:flex;align-items:center;gap:10px;margin:32px 0 16px}}
.sec-h .dot{{width:3px;height:22px;border-radius:2px;background:linear-gradient(180deg,{P},{P_L})}}
.sec-h .txt{{font-size:.92rem;font-weight:700;color:{t['text']};letter-spacing:-.3px}}

/* ── Notice Row v7 ── */
.n-row{{
    background:{t['card']};border:1px solid {t['border']};border-radius:12px;
    padding:14px 18px;margin-bottom:6px;border-left:3px solid transparent;
    transition:all .2s cubic-bezier(.25,.8,.25,1);display:flex;align-items:center;gap:14px;
}}
.n-row:hover{{border-left-color:{P};background:{t['card_hover']};transform:translateX(2px)}}
.n-badge{{
    min-width:34px;height:26px;display:inline-flex;align-items:center;justify-content:center;
    border-radius:8px;font-size:.72rem;font-weight:800;color:#fff;flex-shrink:0;
}}
.n-title{{font-size:.85rem;font-weight:600;color:{t['text']};flex:1;line-height:1.4}}
.n-meta{{font-size:.72rem;color:{t['text3']};font-weight:500}}

/* ── Status Pill ── */
.pill{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:.68rem;font-weight:600}}
.pill-a{{background:rgba(5,150,105,.1);color:{GA}}}.pill-b{{background:rgba(37,99,235,.1);color:{GB}}}
.pill-c{{background:rgba(217,119,6,.1);color:{GC}}}.pill-d{{background:rgba(220,38,38,.1);color:{GD}}}
.pill-l3{{background:rgba(157,23,77,.1);color:#9D174D}}
.pill-urgent{{background:rgba(220,38,38,.08);color:#DC2626;border:1px solid rgba(220,38,38,.2);animation:pulse-urgent 2s ease infinite}}
@keyframes pulse-urgent{{0%,100%{{opacity:1}}50%{{opacity:.6}}}}

/* ── Apply Status Badge (Feature #1) ── */
.apply-badge{{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:6px;font-size:.68rem;font-weight:700}}
.apply-open{{background:rgba(5,150,105,.1);color:#059669;border:1px solid rgba(5,150,105,.2)}}
.apply-upcoming{{background:rgba(37,99,235,.1);color:#2563EB;border:1px solid rgba(37,99,235,.2)}}
.apply-closed{{background:rgba(107,114,128,.08);color:#6B7280;border:1px solid rgba(107,114,128,.15)}}

/* ── Urgent Banner (Feature #4) ── */
.urgent-banner{{
    background:linear-gradient(135deg,rgba(220,38,38,.08),rgba(220,38,38,.04));
    border:1px solid rgba(220,38,38,.15);border-radius:14px;padding:16px 24px;
    margin:16px 0;animation:urgent-glow 3s ease infinite;
}}
@keyframes urgent-glow{{0%,100%{{box-shadow:0 0 0 rgba(220,38,38,0)}}50%{{box-shadow:0 0 20px rgba(220,38,38,.08)}}}}
.urgent-banner .ub-title{{font-size:.82rem;font-weight:800;color:#DC2626;margin-bottom:8px;display:flex;align-items:center;gap:8px}}
.urgent-banner .ub-item{{
    display:flex;align-items:center;gap:10px;padding:6px 0;
    border-bottom:1px solid rgba(220,38,38,.06);font-size:.8rem;color:{t['text']};
}}
.urgent-banner .ub-item:last-child{{border:none}}

/* ── Data Table ── */
.stDataFrame{{border-radius:12px;overflow:hidden;border:1px solid {t['border']}}}

/* ── Button v7 ── */
.stButton>button{{
    background:{t['card']};color:{t['text']};font-weight:600;
    border:1px solid {t['border2']};border-radius:10px;
    padding:.6rem 1.8rem;font-size:.82rem;transition:all .25s;
}}
.stButton>button:hover{{
    border-color:rgba(255,128,0,.3);color:{P};
    box-shadow:0 4px 16px rgba(255,128,0,.1);transform:translateY(-1px);
}}
.stFormSubmitButton>button{{
    background:linear-gradient(135deg,{P},{P_L}) !important;
    border:none !important;font-weight:700;border-radius:10px;color:#fff !important;
}}
.stFormSubmitButton>button:hover{{box-shadow:0 4px 24px rgba(255,128,0,.3);transform:translateY(-2px)}}

/* ── Progress ── */
.stProgress>div>div>div>div{{background:linear-gradient(90deg,{P},{P_L});border-radius:4px}}

/* ── Inputs ── */
.stSelectbox label,.stMultiSelect label,.stSlider label{{font-weight:600;color:{t['text']};font-size:.8rem}}
.stTextInput>div>div>input{{border-radius:10px;background:{t['input_bg']};border-color:{t['border2']}}}
.stTextInput>div>div>input:focus{{border-color:{P};box-shadow:0 0 0 2px rgba(255,128,0,.1)}}

/* ── Expander ── */
.streamlit-expanderHeader{{font-weight:600;font-size:.83rem;color:{t['text']}}}

/* ── Empty State ── */
.empty{{text-align:center;padding:5rem 0}}
.empty .icon{{font-size:2.5rem;margin-bottom:14px;opacity:.5}}
.empty .heading{{font-size:1.05rem;font-weight:700;color:{t['text']};margin-bottom:8px}}
.empty .desc{{font-size:.83rem;color:{t['text2']};line-height:1.6;max-width:440px;margin:0 auto}}

/* ── Chat ── */
.stChatMessage{{border-radius:12px}}

/* ── Compare Table (Feature #6) ── */
.cmp-table{{width:100%;border-collapse:separate;border-spacing:0;border-radius:12px;overflow:hidden;border:1px solid {t['border']}}}
.cmp-table th{{background:{t['bg3']};color:{t['text2']};font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:12px 16px;text-align:left}}
.cmp-table td{{padding:12px 16px;font-size:.82rem;color:{t['text']};border-top:1px solid {t['border']};vertical-align:top}}
.cmp-table tr:hover td{{background:{t['card_hover']}}}
</style>""", unsafe_allow_html=True)


# =============================================================================
#  Utility Functions
# =============================================================================

def _dday(dl: str) -> int:
    try: return (datetime.strptime(dl, "%Y-%m-%d").date() - date.today()).days
    except Exception: return -1

def _kpi(val, label, accent="", delta="", delta_dir=""):
    ac = f' style="color:{accent}"' if accent else ""
    dd = ""
    if delta:
        cls = "up" if delta_dir == "up" else "down" if delta_dir == "down" else ""
        arrow = "+" if delta_dir == "up" else ""
        dd = f'<div class="kpi-delta {cls}">{arrow}{delta}</div>'
    return f'<div class="kpi-card"><div class="kpi-val"{ac}>{val}</div>{dd}<div class="kpi-label">{label}</div></div>'

def _section(title):
    return f'<div class="sec-h"><div class="dot"></div><div class="txt">{title}</div></div>'

def _badge(grade):
    c = GRADE.get(grade, t['text3'])
    return f'<span class="n-badge" style="background:{c}">{grade}</span>'

def _pill(text, variant="a"):
    return f'<span class="pill pill-{variant}">{text}</span>'

def _apply_badge(status):
    """Feature #1: Apply status badges"""
    if not status: return ""
    if "접수중" in status:
        return '<span class="apply-badge apply-open">접수중</span>'
    elif "접수예정" in status:
        return '<span class="apply-badge apply-upcoming">접수예정</span>'
    elif "마감" in status:
        return '<span class="apply-badge apply-closed">마감</span>'
    return f'<span class="apply-badge apply-closed">{status}</span>'

def _notice_row(grade, title, meta, extra=""):
    return f'<div class="n-row">{_badge(grade)}<div style="flex:1"><div class="n-title">{title}</div><div class="n-meta">{meta}</div></div>{extra}</div>'

def _empty(icon, heading, desc):
    return f'<div class="empty"><div class="icon">{icon}</div><div class="heading">{heading}</div><div class="desc">{desc}</div></div>'

def _result():
    return st.session_state.get("pipeline_result")

def _smap(result):
    return {s.notice_id: s for s in result.get("score_cards", [])}

def _layout(**kw):
    base = dict(paper_bgcolor=t['card'], plot_bgcolor=t['bg3'],
                font=dict(color=t['text'], family="Inter,system-ui,sans-serif", size=12),
                margin=dict(t=40, b=36, l=36, r=16),
                hoverlabel=dict(bgcolor=t['text'], font_color=t['card'], font_size=12))
    base.update(kw); return base

def _win_prob(n, sc):
    """Feature #2: Calculate win probability for a notice"""
    if not sc: return 0
    fitness = sc.fitness_score or 0
    priority = sc.priority_score or 0
    industry = sc.industry_score or 0
    dd = _dday(n.deadline_date or "")
    l3v = 1 if getattr(n, "l3_strong", "N") == "Y" else 0
    urg = max(0, min(100, (30 - dd) * 3.33)) if dd >= 0 else 0
    wp = min(100, max(0, fitness * 0.35 + priority * 0.25 + 50 * 0.15 + urg * 0.10 + l3v * 10 + industry * 0.05))
    return wp

def _ai_cache_key(notice_id):
    """Feature #3: Cache key for AI analysis"""
    return f"ai_cache_{notice_id}"


# ── 요약/본문 잡음 제거 ──────────────────────────────────────────────────────
_JUNK_PATTERNS = re.compile(
    r"HOME\s+정책정보|본문\s*바로가기|대메뉴\s*바로가기|"
    r"해시태그\s*#|본문출력파일|바로보기\s+다운로드|링크복사\s+QR코드|"
    r"정보에\s*만족하셨|욕설.*삭제될\s*있음|기업마당\s*정책정보에|"
    r"공고를\s*열람한\s*사용자가|조회수\s*\d+|"
    r"<title[^>]*>.*?</title>|"
    r"\{\{[^}]+\}\}",
    re.I | re.DOTALL,
)
_RELATED_POST_RE = re.compile(
    r"NO\.\s+\d{4}\.\d{2}\.\d{2}~\d{4}\.\d{2}\.\d{2}\s+#.+",
    re.DOTALL,
)

def _clean_summary(text: str) -> str:
    """핵심 요약에서 네비게이션/해시태그/관련 공고 등 잡음 제거."""
    if not text:
        return ""
    text = _JUNK_PATTERNS.sub("", text)
    text = _RELATED_POST_RE.sub("", text)
    # 해시태그 블록 제거
    text = re.sub(r'#\w+(\s+#\w+){2,}', '', text)
    # 연속 공백 정리
    text = re.sub(r'\s{2,}', ' ', text).strip()
    # "HOME 정책정보 지원사업 지원사업" 같은 breadcrumb 제거
    text = re.sub(r'^(HOME\s+)?(정책정보\s+)?(지원사업\s+)*', '', text).strip()
    return text


def _extract_key_summary(summary: str, body: str, structured: dict) -> str:
    """공고 핵심 요약 추출: 구조화 섹션 > 핵심 문장 > 정제된 summary."""
    # 1) 구조화 섹션이 있으면 조합
    parts = []
    for key in ["사업목적", "지원내용", "지원대상"]:
        v = (structured or {}).get(key, "")
        if v and len(v) > 15:
            parts.append(v[:200])
    if parts:
        return " | ".join(parts)

    # 2) body에서 핵심 키워드 문장 추출
    src = _clean_summary(body or summary or "")
    if not src:
        return ""
    _KEY_RE = re.compile(
        r"(지원\s*대상|지원\s*내용|지원\s*규모|사업\s*개요|사업\s*목적|"
        r"신청\s*자격|접수\s*기간|총\s*사업비|과제당|선정\s*규모|공모\s*분야)"
    )
    sents = [s.strip() for s in re.split(r'(?<=[.다요됨함!\n])\s+', src) if len(s.strip()) > 15]
    important = [s for s in sents if _KEY_RE.search(s)]
    if important:
        return " ".join(important[:3])[:500]

    # 3) 첫 유의미 문장
    for s in sents:
        if len(s) >= 25:
            return s[:300]
    return src[:300]


# =============================================================================
#  Navigation
# =============================================================================

NAV_ITEMS = [
    "📊 대시보드", "🚀 수집 실행", "📋 공고 목록", "🔍 공고 비교",
    "📝 제안서", "🏢 경쟁사", "🎯 수주 예측", "📅 마감 캘린더",
    "📈 분석", "👤 담당자", "🤖 AI 뉴스", "💬 AI 챗봇",
]

with st.sidebar:
    st.markdown(f'<div style="padding:20px 16px 12px;text-align:center">'
                f'<div style="font-size:1.5rem;font-weight:900;letter-spacing:-1.5px">'
                f'<span style="color:{t["text"]}">INTER</span><span style="color:{P}">X</span></div>'
                f'<div style="color:{t["text3"]};font-size:.6rem;letter-spacing:4px;margin-top:4px">INTELLIGENCE ENGINE</div></div>',
                unsafe_allow_html=True)
    st.markdown(f'<div style="border-top:1px solid {t["border"]};margin:8px 0 12px"></div>', unsafe_allow_html=True)

    page = st.radio("Navigation", NAV_ITEMS, label_visibility="collapsed")

    st.markdown(f'<div style="border-top:1px solid {t["border"]};margin:16px 0 12px"></div>', unsafe_allow_html=True)

    # Feature #8: Dark mode toggle
    _current_theme = _get_theme()
    _theme_label = "🌙 다크 모드" if _current_theme == "light" else "☀️ 라이트 모드"
    if st.button(_theme_label, key="theme_toggle", width="stretch"):
        st.session_state.theme_mode = "dark" if _current_theme == "light" else "light"
        st.rerun()

    st.markdown(f'<div style="padding:8px 16px;font-size:.68rem;color:{t["text3"]}">'
                f'v7.0 · {datetime.now().strftime("%Y-%m-%d")}</div>', unsafe_allow_html=True)


# ── Top Bar ──
st.markdown(f"""<div class="nav-bar">
    <div class="brand"><span>INTER</span><b>X</b></div>
    <div class="meta">
        <div class="meta-item"><div class="meta-dot"></div>시스템 정상</div>
        <div class="meta-item">{datetime.now().strftime('%Y.%m.%d %H:%M')}</div>
        <div class="meta-item">v7.0</div>
    </div>
</div>""", unsafe_allow_html=True)


# =============================================================================
#  PAGE: Dashboard
# =============================================================================

if page == "📊 대시보드":
    result = _result()
    if not result:
        st.markdown(_empty("📊", "데이터를 수집해주세요",
                           "좌측 메뉴에서 '수집 실행'을 선택하여 정부지원사업 공고를 수집하세요."),
                    unsafe_allow_html=True)
    else:
        notices = result.get("notices", []); smap = _smap(result)
        score_cards = result.get("score_cards", [])
        gc = {"A": 0, "B": 0, "C": 0, "D": 0}
        wp_sum = 0; wp_cnt = 0
        for sc in score_cards:
            gc[sc.priority_grade] = gc.get(sc.priority_grade, 0) + 1
        for n in notices:
            sc = smap.get(n.notice_id)
            wp = _win_prob(n, sc)
            if wp > 0: wp_sum += wp; wp_cnt += 1

        # ── Feature #4: D-3 Urgent Banner ──
        d3_notices = []
        for n in notices:
            dd = _dday(n.deadline_date or "")
            if 0 <= dd <= 3:
                sc = smap.get(n.notice_id)
                d3_notices.append((n, sc, dd))
        d3_notices.sort(key=lambda x: x[2])

        if d3_notices:
            items_html = ""
            for n, sc, dd in d3_notices[:5]:
                grade = sc.priority_grade if sc else "D"
                gc_color = GRADE.get(grade, t['text3'])
                items_html += f'<div class="ub-item">{_badge(grade)} <span style="flex:1">{n.title[:60]}</span> <span style="color:#DC2626;font-weight:800;font-size:.85rem">D-{dd}</span> <span style="color:{t["text3"]};font-size:.72rem">{n.site} · {n.agency or "-"}</span></div>'
            st.markdown(f'<div class="urgent-banner"><div class="ub-title">🚨 긴급 마감 D-3 이내 ({len(d3_notices)}건)</div>{items_html}</div>', unsafe_allow_html=True)

        # ── KPI Cards ──
        st.markdown(_section("핵심 지표"), unsafe_allow_html=True)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.markdown(_kpi(len(notices), "전체 공고"), unsafe_allow_html=True)
        k2.markdown(_kpi(gc["A"], "A등급", GA), unsafe_allow_html=True)
        k3.markdown(_kpi(gc["B"], "B등급", GB), unsafe_allow_html=True)
        l3_count = sum(1 for n in notices if getattr(n, "l3_strong", "N") == "Y")
        k4.markdown(_kpi(l3_count, "L3 강공고", "#9D174D"), unsafe_allow_html=True)
        d7 = sum(1 for n in notices if 0 <= _dday(n.deadline_date or "") <= 7)
        k5.markdown(_kpi(d7, "D-7 마감", GD), unsafe_allow_html=True)
        # Feature #2: Win probability KPI
        avg_wp = wp_sum / max(1, wp_cnt)
        wp_color = GA if avg_wp >= 60 else GB if avg_wp >= 40 else GC
        k6.markdown(_kpi(f"{avg_wp:.0f}%", "평균 수주확률", wp_color), unsafe_allow_html=True)

        # ── Grade Distribution + Search ──
        col_chart, col_search = st.columns([1, 2])
        with col_chart:
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(
                x=["A", "B", "C", "D"], y=[gc["A"], gc["B"], gc["C"], gc["D"]],
                marker_color=[GA, GB, GC, GD],
                text=[gc["A"], gc["B"], gc["C"], gc["D"]], textposition='outside',
            ))
            fig.update_layout(title=dict(text="등급 분포", font=dict(size=14, color=t['text'])),
                              height=320, yaxis=dict(gridcolor=t['border']),
                              xaxis=dict(gridcolor=t['border']), **_layout())
            st.plotly_chart(fig, width="stretch")

        with col_search:
            st.markdown(_section("빠른 검색"), unsafe_allow_html=True)
            sq = st.text_input("공고명 검색", placeholder="키워드를 입력하세요...", label_visibility="collapsed")
            if sq:
                found = [(n, smap.get(n.notice_id)) for n in notices if sq.lower() in (n.title or "").lower()][:10]
                for n, sc in found:
                    g = sc.priority_grade if sc else "D"
                    dd = _dday(n.deadline_date or "")
                    wp = _win_prob(n, sc)
                    dd_str = f"D-{dd}" if dd >= 0 else "마감"
                    apply_st = _apply_badge(getattr(n, "apply_status", ""))
                    meta = f"{n.site} · {n.agency or '-'} · {dd_str} · 수주 {wp:.0f}%"
                    st.markdown(_notice_row(g, n.title[:60], meta, apply_st), unsafe_allow_html=True)
                if not found:
                    st.caption("검색 결과가 없습니다.")

        # ── A-grade Top Notices ──
        a_notices = [(n, smap.get(n.notice_id)) for n in notices
                     if smap.get(n.notice_id) and smap[n.notice_id].priority_grade == "A"]
        a_notices.sort(key=lambda x: -(x[1].priority_score if x[1] else 0))

        if a_notices:
            st.markdown(_section(f"A등급 핵심 공고 ({len(a_notices)}건)"), unsafe_allow_html=True)
            for n, sc in a_notices[:8]:
                dd = _dday(n.deadline_date or "")
                wp = _win_prob(n, sc)
                dd_str = f"D-{dd}" if dd >= 0 else "마감"
                apply_st = _apply_badge(getattr(n, "apply_status", ""))
                wp_color = GA if wp >= 60 else GB if wp >= 40 else GC
                wp_pill = f'<span class="pill" style="background:rgba({",".join(str(int(wp_color.lstrip("#")[i:i+2], 16)) for i in (0,2,4))},.1);color:{wp_color};font-weight:700">수주 {wp:.0f}%</span>'
                meta = f"{n.site} · {n.agency or '-'} · 예산 {n.budget or '-'} · {dd_str}"
                st.markdown(_notice_row("A", n.title[:60], meta, f"{apply_st} {wp_pill}"), unsafe_allow_html=True)
                with st.expander("상세 보기", expanded=False):
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.markdown(f"**주관기관**: {n.agency or n.ministry or '-'}")
                        st.markdown(f"**부처**: {getattr(n, 'ministry', '-') or '-'}")
                        st.markdown(f"**마감일**: {n.deadline_date or '-'} ({dd_str})")
                        st.markdown(f"**예산**: {n.budget or '-'}")
                        st.markdown(f"**공고일**: {getattr(n, 'notice_date', '-') or '-'}")
                        st.markdown(f"**신청기간**: {getattr(n, 'apply_period', '-') or '-'}")
                        st.markdown(f"**접수상태**: {getattr(n, 'apply_status', '-') or '-'}")
                        link = getattr(n, "detail_url", "") or ""
                        if link.startswith("http"):
                            st.markdown(f"[원문 바로가기 ↗]({link})")
                    with dc2:
                        if sc:
                            _sc1, _sc2, _sc3 = st.columns(3)
                            _sc1.metric("적합도", f"{sc.fitness_score:.1f}")
                            _sc2.metric("우선순위", f"{sc.priority_score:.1f}")
                            _sc3.metric("산업점수", f"{sc.industry_score:.1f}")
                            wp_c = GA if wp >= 60 else GB if wp >= 40 else GC if wp >= 20 else GD
                            st.markdown(f"**수주 확률** &nbsp; <span style='color:{wp_c};font-size:1.3rem;font-weight:800'>{wp:.0f}%</span>", unsafe_allow_html=True)
                            if sc.positive_keywords:
                                tags = " ".join(f'`{k}`' for k in sc.positive_keywords[:8])
                                st.markdown(f"**키워드**: {tags}")
                            if sc.solution_scores:
                                SOL_D = {"ManufacturingDT": "제조DT", "RecipeAI": "레시피AI", "QualityAI": "품질AI",
                                         "InspectionAI": "비전검사", "SafetyAI": "안전AI", "GenAI": "GenAI",
                                         "InfraDS": "데이터인프라", "PdM": "예지보전"}
                                sols_d = sorted([(SOL_D.get(k, k), v) for k, v in sc.solution_scores.items() if v > 0], key=lambda x: -x[1])
                                if sols_d:
                                    st.markdown("**솔루션 매칭**: " + " · ".join(f"**{name}** {score:.0f}" for name, score in sols_d[:5]))

                    # 공고 핵심 내용
                    _body_d = getattr(n, "body_text", "") or ""
                    _struct_d = getattr(n, "structured", None) or {}
                    _summary_d = getattr(n, "summary", "") or ""
                    _key_summ = _extract_key_summary(_summary_d, _body_d, _struct_d)
                    if _struct_d or _key_summ or (_body_d and len(_body_d) > 20):
                        st.markdown("---")
                        for _sk, _sl in [("사업목적", "🎯 사업목적"), ("지원내용", "💰 지원내용"),
                                         ("지원대상", "👥 지원대상"), ("지원금액", "💵 지원금액"),
                                         ("신청방법", "📝 신청방법")]:
                            _sv = _clean_summary(_struct_d.get(_sk, ""))
                            if _sv and len(_sv) > 10:
                                st.markdown(f"**{_sl}**")
                                st.markdown(f"> {_sv[:300]}")
                        if not _struct_d and _key_summ and len(_key_summ) > 20:
                            st.markdown("**📌 핵심 요약**")
                            st.markdown(f"> {_key_summ}")
                        if _body_d and len(_body_d) > 50:
                            st.caption("📄 전체 본문")
                            st.text(_clean_summary(_body_d[:3000]))

                    # AI 분석 (캐시 지원)
                    _dk = _ai_cache_key(n.notice_id)
                    _dc = st.session_state.get(_dk)
                    if _dc:
                        st.markdown(f'<div style="background:{t["bg3"]};border:1px solid {t["border"]};border-radius:10px;padding:12px 16px;margin:8px 0;font-size:.82rem"><b style="color:{A2}">💡 AI 분석 (캐시)</b><br><b>적합도:</b> {_dc.get("fit_reason","")}<br><b>제안 전략:</b> {_dc.get("proposal_strategy","")}<br><b>솔루션:</b> {_dc.get("solution_mapping","")}</div>', unsafe_allow_html=True)
                    if st.button("💡 AI 분석" + (" (재분석)" if _dc else ""), key=f"dash_ai_{n.notice_id}"):
                        with st.spinner("AI 분석 중..."):
                            try:
                                from interx_engine.infrastructure.ai.notice_analyzer import analyze_notice
                                _ai_r = analyze_notice(
                                    title=n.title, body_text=_body_d, summary=_summary_d,
                                    structured=_struct_d,
                                    matched_keywords=", ".join(sc.positive_keywords[:8]) if sc and sc.positive_keywords else "",
                                    grade="A", score=sc.fitness_score if sc else 0,
                                    budget=n.budget or "", solution_scores=sc.solution_scores if sc else None,
                                )
                                st.session_state[_dk] = _ai_r
                                st.markdown(f'<div style="background:{t["bg3"]};border:1px solid {t["border"]};border-radius:10px;padding:12px 16px;margin:8px 0;font-size:.82rem"><b style="color:{A2}">💡 AI 분석 결과</b><br><b>적합도:</b> {_ai_r.get("fit_reason","")}<br><b>제안 전략:</b> {_ai_r.get("proposal_strategy","")}<br><b>솔루션:</b> {_ai_r.get("solution_mapping","")}<br><b>핵심 요구:</b> {_ai_r.get("key_requirements","")}<br><span style="color:{GC}"><b>리스크:</b> {_ai_r.get("risk_factors","")}</span></div>', unsafe_allow_html=True)
                            except Exception as _ae:
                                st.error(f"AI 분석 실패: {_ae}")

                    # 원문 사이트 미리보기 (iframe)
                    _link_d = getattr(n, "detail_url", "") or ""
                    if _link_d and _link_d.startswith("http"):
                        st.markdown(f"🔗 **[원문 바로가기 (새 탭)]({_link_d})**")
                        with st.expander("🌐 원문 사이트 미리보기", expanded=False):
                            st.caption("⚠️ 일부 사이트는 보안 정책으로 미리보기가 차단됩니다.")
                            st.iframe(_link_d, height=500)

        # ── Solution TOP3 + Site Stats ──
        col_sol, col_site = st.columns(2)
        with col_sol:
            sol_c = Counter()
            for sc in score_cards:
                if sc.solution_scores:
                    for k, v in sc.solution_scores.items():
                        if v > 0: sol_c[k] += 1
            if sol_c:
                SOL = {"ManufacturingDT": "제조DT", "RecipeAI": "레시피AI", "QualityAI": "품질AI",
                       "InspectionAI": "비전검사", "SafetyAI": "안전AI", "GenAI": "GenAI",
                       "InfraDS": "데이터인프라", "PdM": "예지보전"}
                st.markdown(_section("솔루션 매칭 TOP"), unsafe_allow_html=True)
                top3 = sol_c.most_common(5)
                fig = go.Figure(go.Bar(
                    x=[SOL.get(k, k) for k, _ in top3], y=[v for _, v in top3],
                    marker_color=[P, P_L, A2, GB, GC][:len(top3)],
                    text=[v for _, v in top3], textposition='outside',
                ))
                fig.update_layout(height=300, yaxis=dict(gridcolor=t['border']), **_layout())
                st.plotly_chart(fig, width="stretch")

        with col_site:
            site_c = Counter(n.site for n in notices)
            if site_c:
                st.markdown(_section("사이트별 수집"), unsafe_allow_html=True)
                top_sites = site_c.most_common(8)
                fig = go.Figure(go.Bar(
                    y=[s for s, _ in reversed(top_sites)], x=[c for _, c in reversed(top_sites)],
                    orientation='h', marker_color=P,
                ))
                fig.update_layout(height=300, xaxis=dict(gridcolor=t['border']), **_layout(margin=dict(l=100, r=16, t=40, b=36)))
                st.plotly_chart(fig, width="stretch")


# =============================================================================
#  PAGE: Pipeline Runner
# =============================================================================

if page == "🚀 수집 실행":
    st.markdown(_section("파이프라인 실행"), unsafe_allow_html=True)

    if "pipeline_running" not in st.session_state:
        st.session_state.pipeline_running = False
    if "collection_history" not in st.session_state:
        st.session_state.collection_history = []

    with st.form("run_form"):
        c1, c2 = st.columns(2)
        with c1:
            run_mode = st.selectbox("실행 모드", [
                "일반 수집 (Daily)", "전체 수집 (Full — 클러스터링 포함)",
                "테스트 (Dry Run — Mock 데이터)"
            ])
            ml = run_mode.split("(")[0].strip()
        with c2:
            max_pages = st.slider("사이트당 페이지 수", 1, 10, 3)

        sites_all = ["bizinfo", "iris", "smba", "kiat", "kstartup", "keit", "kaia", "iitp",
                     "nipa", "kodit", "dicia", "mss", "kibo", "smart_factory", "ketep", "kised"]
        sites_to_use = st.multiselect("수집 사이트", sites_all, default=sites_all,
                                       help="전체 선택 시 모든 사이트 수집")
        enable_sheets = st.checkbox("Google Sheets 업로드", value=True)
        submitted = st.form_submit_button("🚀 수집 시작", disabled=st.session_state.pipeline_running)

    if submitted and not st.session_state.pipeline_running:
        st.session_state.pipeline_running = True
        progress = st.progress(0, text="준비 중...")
        status = st.status("파이프라인 실행 중...", expanded=True)
        with status:
            try:
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
                gc = {"A": 0, "B": 0, "C": 0, "D": 0}; sm = {s.notice_id: s for s in scs}
                for n in nn:
                    sc = sm.get(n.notice_id)
                    if sc: gc[sc.priority_grade] = gc.get(sc.priority_grade, 0) + 1
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
                status.update(label="오류 발생", state="error")
                st.error(f"파이프라인 실행 실패: {e}")
                import traceback; st.code(traceback.format_exc())
                st.session_state.pipeline_running = False


# =============================================================================
#  PAGE: Notice List + Detail
# =============================================================================

if page == "📋 공고 목록":
    result = _result()
    if not result:
        st.markdown(_empty("📋", "공고 데이터 없음", "수집 실행 후 이 탭에서 공고를 조회할 수 있습니다."), unsafe_allow_html=True)
    else:
        notices = result.get("notices", []); smap = _smap(result)
        st.markdown(_section("필터"), unsafe_allow_html=True)
        f1, f2, f3, f4 = st.columns(4)
        with f1: gf = st.multiselect("등급", ["A", "B", "C", "D"], default=["A", "B", "C", "D"])
        with f2: sf = st.multiselect("사이트", sorted(set(n.site for n in notices)))
        with f3: kw = st.text_input("키워드 검색", placeholder="공고명 키워드...")
        with f4:
            as_filter = st.multiselect("접수상태", ["접수중", "접수예정", "마감", "전체"], default=["전체"])

        filtered = []
        for n in notices:
            sc = smap.get(n.notice_id); g = sc.priority_grade if sc else "D"
            if g not in gf: continue
            if sf and n.site not in sf: continue
            if kw and kw.lower() not in (n.title or "").lower(): continue
            # Feature #1: Filter by apply status
            if "전체" not in as_filter:
                n_status = getattr(n, "apply_status", "") or ""
                if as_filter and not any(s in n_status for s in as_filter): continue
            filtered.append((n, sc))
        go_ = {"A": 0, "B": 1, "C": 2, "D": 3}
        filtered.sort(key=lambda x: (go_.get(x[1].priority_grade if x[1] else "D", 3), -(x[1].priority_score if x[1] else 0)))

        st.markdown(f'<p style="color:{t["text2"]};font-size:.82rem;font-weight:500">조회 결과 <b style="color:{P}">{len(filtered)}</b> / {len(notices)}건</p>', unsafe_allow_html=True)

        rows = []
        for n, sc in filtered:
            dd = _dday(n.deadline_date or "")
            _bgt = n.budget or ""
            _bv = None
            try:
                _m = re.search(r'(\d[\d,.]*)\s*억', _bgt)
                if _m: _bv = float(_m.group(1).replace(",", ""))
            except Exception: pass
            _action = "인터엑스" if _bv and _bv >= 2.1 else "파트너이관" if _bv and _bv < 2.0 else "-"
            wp = _win_prob(n, sc)
            rows.append({
                "등급": sc.priority_grade if sc else "D",
                "점수": f"{sc.priority_score:.0f}" if sc else "-",
                "공고명": n.title[:70] if n.title else "-",
                "주관기관": n.agency or n.ministry or "-",
                "사이트": n.site,
                "마감일": n.deadline_date or "-",
                "D-day": str(dd) if dd >= 0 else "마감",
                "수주확률": f"{wp:.0f}%",
                "접수상태": getattr(n, "apply_status", "") or "-",
                "L3": "Y" if getattr(n, "l3_strong", "N") == "Y" else "",
                "예산": _bgt or "-",
                "진행": _action,
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), width="stretch", height=420)

            dl1, dl2, _ = st.columns([1, 1, 5])
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
            except Exception: pass

            # ── Detail Panel ──
            st.markdown(_section("공고 상세"), unsafe_allow_html=True)
            ntmap = {f"[{sc.priority_grade if sc else 'D'}] {n.title[:55]} ({n.site})": (n, sc) for n, sc in filtered}
            sel = st.selectbox("공고 선택", ["선택하세요..."] + list(ntmap.keys()), label_visibility="collapsed")
            if sel != "선택하세요..." and sel in ntmap:
                sn, ssc = ntmap[sel]
                dd = _dday(sn.deadline_date or "")
                grade = ssc.priority_grade if ssc else "D"
                gc_c = GRADE.get(grade, t['text3'])

                apply_st = _apply_badge(getattr(sn, "apply_status", ""))
                st.markdown(f"""<div style="background:{t['card']};border-left:4px solid {gc_c};border-radius:0 14px 14px 0;padding:20px 24px;margin:8px 0;border:1px solid {t['border']}">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;flex-wrap:wrap">
                        {_badge(grade)}
                        <span style="font-size:1.05rem;font-weight:700;color:{t['text']}">{sn.title}</span>
                        {apply_st}
                    </div>
                    <div style="font-size:.78rem;color:{t['text3']}">{sn.site} · {sn.agency or sn.ministry or '-'} · {sn.deadline_date or '-'} · 예산 {sn.budget or '-'}</div>
                </div>""", unsafe_allow_html=True)

                dc1, dc2 = st.columns(2)
                with dc1:
                    st.markdown("##### 기본 정보")
                    for label, val in [("주관기관", sn.agency or sn.ministry or "-"),
                                       ("부처", getattr(sn, "ministry", "-") or "-"),
                                       ("마감일", f"{sn.deadline_date or '-'} (D-{dd})" if dd >= 0 else f"{sn.deadline_date or '-'} (마감)"),
                                       ("예산", sn.budget or "-"),
                                       ("공고일", getattr(sn, "notice_date", "-") or "-"),
                                       ("신청기간", getattr(sn, "apply_period", "-") or "-"),
                                       ("접수상태", getattr(sn, "apply_status", "-") or "-")]:
                        st.markdown(f"- **{label}** : {val}")
                    link = getattr(sn, "detail_url", "") or ""
                    if link and link.startswith("http"): st.markdown(f"- **링크** : [{link[:50]}...]({link})")

                with dc2:
                    if ssc:
                        st.markdown("##### 스코어링 분석")
                        sc1, sc2, sc3 = st.columns(3)
                        sc1.metric("적합도", f"{ssc.fitness_score:.1f}")
                        sc2.metric("우선순위", f"{ssc.priority_score:.1f}")
                        sc3.metric("산업점수", f"{ssc.industry_score:.1f}")

                        wp = _win_prob(sn, ssc)
                        wp_c = GA if wp >= 60 else GB if wp >= 40 else GC if wp >= 20 else GD
                        st.markdown(f"**수주 확률** &nbsp; <span style='color:{wp_c};font-size:1.3rem;font-weight:800'>{wp:.0f}%</span>", unsafe_allow_html=True)

                        if ssc.positive_keywords:
                            tags = " ".join(f'`{k}`' for k in ssc.positive_keywords[:12])
                            st.markdown(f"**매칭 키워드**: {tags}")

                        if ssc.solution_scores:
                            SOL = {"ManufacturingDT": "제조DT", "RecipeAI": "레시피AI", "QualityAI": "품질AI",
                                   "InspectionAI": "비전검사", "SafetyAI": "안전AI", "GenAI": "GenAI",
                                   "InfraDS": "데이터인프라", "PdM": "예지보전"}
                            sols = sorted([(SOL.get(k, k), v) for k, v in ssc.solution_scores.items() if v > 0], key=lambda x: -x[1])
                            if sols:
                                st.markdown("**솔루션 매칭**: " + " · ".join(f"**{name}** {score:.0f}" for name, score in sols[:5]))

                body = getattr(sn, "body_text", "") or ""
                body = re.sub(r'\{\{[^}]+\}\}', '', body).strip()

                if body and body.startswith("[첨부:"):
                    st.caption("📎 OCR: 첨부파일에서 텍스트 자동 추출됨")

                _sn_struct = getattr(sn, "structured", None) or {}
                _sn_summary = getattr(sn, "summary", "") or ""
                _sn_key_summ = _extract_key_summary(_sn_summary, body, _sn_struct)

                if _sn_struct or _sn_key_summ or (body and len(body) > 20):
                    with st.expander("📋 공고 핵심 내용", expanded=False):
                        for _sk2, _sl2 in [("사업목적", "🎯 사업목적"), ("지원내용", "💰 지원내용"),
                                           ("지원대상", "👥 지원대상"), ("지원금액", "💵 지원금액"),
                                           ("신청방법", "📝 신청방법"), ("추진일정", "📅 추진일정")]:
                            _sv2 = _clean_summary(_sn_struct.get(_sk2, ""))
                            if _sv2 and len(_sv2) > 10:
                                st.markdown(f"**{_sl2}**")
                                st.markdown(f"> {_sv2[:300]}")
                        if not _sn_struct and _sn_key_summ and len(_sn_key_summ) > 20:
                            st.markdown("**📌 핵심 요약**")
                            st.markdown(f"> {_sn_key_summ}")
                        if body and len(body) > 50:
                            st.markdown("---")
                            st.caption("📄 전체 본문")
                            st.text(_clean_summary(body[:5000]))
                            if len(body) > 5000: st.caption(f"전체 {len(body):,}자 중 5,000자 표시")

                # ── Feature #3: AI Analysis with Caching ──
                _cache_key = _ai_cache_key(sn.notice_id)
                _cached = st.session_state.get(_cache_key)

                if _cached:
                    _ai_result = _cached
                    st.markdown(f"""<div style="background:{t['bg3']};border:1px solid {t['border']};border-radius:12px;padding:16px 20px;margin:10px 0">
                        <div style="font-size:.85rem;font-weight:700;color:{A2};margin-bottom:8px">💡 AI 분석 결과 <span style="font-size:.68rem;color:{t['text3']}">(캐시됨)</span></div>
                        <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>적합도:</b> {_ai_result.get('fit_reason','')}</div>
                        <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>제안 전략:</b> {_ai_result.get('proposal_strategy','')}</div>
                        <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>솔루션 매핑:</b> {_ai_result.get('solution_mapping','')}</div>
                        <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>핵심 요구:</b> {_ai_result.get('key_requirements','')}</div>
                        <div style="font-size:.78rem;color:{GC}"><b>리스크:</b> {_ai_result.get('risk_factors','')}</div>
                    </div>""", unsafe_allow_html=True)

                if st.button("💡 AI 분석" + (" (재분석)" if _cached else ""), key=f"ai_{sn.notice_id}"):
                    with st.spinner("AI 분석 중..."):
                        try:
                            from interx_engine.infrastructure.ai.notice_analyzer import analyze_notice
                            _ai_result = analyze_notice(
                                title=sn.title, body_text=body, summary=_sn_summary,
                                structured=_sn_struct,
                                matched_keywords=", ".join(ssc.positive_keywords[:8]) if ssc and ssc.positive_keywords else "",
                                grade=grade, score=ssc.fitness_score if ssc else 0,
                                budget=sn.budget or "", solution_scores=ssc.solution_scores if ssc else None,
                            )
                            # Feature #3: Cache the result
                            st.session_state[_cache_key] = _ai_result
                            st.markdown(f"""<div style="background:{t['bg3']};border:1px solid {t['border']};border-radius:12px;padding:16px 20px;margin:10px 0">
                                <div style="font-size:.85rem;font-weight:700;color:{A2};margin-bottom:8px">💡 AI 분석 결과</div>
                                <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>적합도:</b> {_ai_result.get('fit_reason','')}</div>
                                <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>제안 전략:</b> {_ai_result.get('proposal_strategy','')}</div>
                                <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>솔루션 매핑:</b> {_ai_result.get('solution_mapping','')}</div>
                                <div style="font-size:.82rem;color:{t['text']};margin-bottom:6px"><b>핵심 요구:</b> {_ai_result.get('key_requirements','')}</div>
                                <div style="font-size:.78rem;color:{GC}"><b>리스크:</b> {_ai_result.get('risk_factors','')}</div>
                            </div>""", unsafe_allow_html=True)
                        except Exception as _ai_err:
                            st.error(f"AI 분석 실패: {_ai_err}")

                # ── 원문 바로가기 ──
                _sn_link = getattr(sn, "detail_url", "") or ""
                if _sn_link and _sn_link.startswith("http"):
                    st.markdown(f"🔗 **[원문 바로가기 (새 탭에서 열기)]({_sn_link})**")
                    with st.expander("🌐 원문 사이트 미리보기", expanded=False):
                        st.caption("⚠️ 일부 사이트는 보안 정책으로 미리보기가 차단됩니다.")
                        st.iframe(_sn_link, height=560)
        else:
            st.info("필터 조건에 맞는 공고가 없습니다.")


# =============================================================================
#  PAGE: Notice Comparison (Feature #6)
# =============================================================================

if page == "🔍 공고 비교":
    result = _result()
    if not result:
        st.markdown(_empty("🔍", "공고 비교", "수집 실행 후 공고를 비교할 수 있습니다."), unsafe_allow_html=True)
    else:
        notices = result.get("notices", []); smap = _smap(result)
        st.markdown(_section("공고 비교 분석 (최대 3건)"), unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:.8rem;color:{t["text3"]}">2~3개 공고를 선택하면 주요 항목을 나란히 비교합니다.</p>', unsafe_allow_html=True)

        ntmap = {f"[{smap[n.notice_id].priority_grade if n.notice_id in smap else 'D'}] {n.title[:55]} ({n.site})": n
                 for n in notices}

        sel_notices = st.multiselect("비교할 공고 선택 (2~3건)", list(ntmap.keys()), max_selections=3)

        if len(sel_notices) >= 2:
            compare_items = []
            for sel in sel_notices:
                n = ntmap[sel]
                sc = smap.get(n.notice_id)
                compare_items.append((n, sc))

            # Build comparison table
            fields = [
                ("공고명", lambda n, sc: n.title or "-"),
                ("등급", lambda n, sc: sc.priority_grade if sc else "D"),
                ("사이트", lambda n, sc: n.site),
                ("주관기관", lambda n, sc: n.agency or n.ministry or "-"),
                ("마감일", lambda n, sc: n.deadline_date or "-"),
                ("D-day", lambda n, sc: str(_dday(n.deadline_date or "")) if _dday(n.deadline_date or "") >= 0 else "마감"),
                ("접수상태", lambda n, sc: getattr(n, "apply_status", "") or "-"),
                ("예산", lambda n, sc: n.budget or "-"),
                ("적합도", lambda n, sc: f"{sc.fitness_score:.1f}" if sc else "-"),
                ("우선순위", lambda n, sc: f"{sc.priority_score:.1f}" if sc else "-"),
                ("수주확률", lambda n, sc: f"{_win_prob(n, sc):.0f}%"),
                ("L3 강공고", lambda n, sc: "Y" if getattr(n, "l3_strong", "N") == "Y" else "N"),
                ("매칭 키워드", lambda n, sc: " | ".join(sc.positive_keywords[:6]) if sc and sc.positive_keywords else "-"),
                ("추천 솔루션", lambda n, sc: " | ".join(
                    k for k, v in sorted((sc.solution_scores or {}).items(), key=lambda x: -x[1]) if v > 0
                )[:3] if sc and sc.solution_scores else "-"),
            ]

            # Render comparison table
            cols_count = len(compare_items)
            header = "<tr><th>항목</th>" + "".join(f"<th>공고 {i+1}</th>" for i in range(cols_count)) + "</tr>"
            body_rows = ""
            for field_name, extractor in fields:
                cells = ""
                for n, sc in compare_items:
                    val = extractor(n, sc)
                    # Highlight best values
                    style = ""
                    if field_name == "등급" and val == "A":
                        style = f' style="color:{GA};font-weight:800"'
                    elif field_name == "등급" and val == "B":
                        style = f' style="color:{GB};font-weight:700"'
                    elif field_name == "L3 강공고" and val == "Y":
                        style = f' style="color:#9D174D;font-weight:700"'
                    cells += f"<td{style}>{val}</td>"
                body_rows += f"<tr><td style='font-weight:600;color:{t['text2']}'>{field_name}</td>{cells}</tr>"

            st.markdown(f'<table class="cmp-table">{header}{body_rows}</table>', unsafe_allow_html=True)

            # Side-by-side win probability visualization
            import plotly.graph_objects as go
            st.markdown(_section("수주 확률 비교"), unsafe_allow_html=True)
            names = [f"공고 {i+1}" for i in range(len(compare_items))]
            wps = [_win_prob(n, sc) for n, sc in compare_items]
            colors = [GA if w >= 60 else GB if w >= 40 else GC for w in wps]
            fig = go.Figure(go.Bar(
                x=names, y=wps, marker_color=colors,
                text=[f"{w:.0f}%" for w in wps], textposition='outside',
            ))
            fig.update_layout(height=300, yaxis=dict(range=[0, 100], title="확률 (%)", gridcolor=t['border']), **_layout())
            st.plotly_chart(fig, width="stretch")

            # Recommendation
            best_idx = wps.index(max(wps))
            best_n, best_sc = compare_items[best_idx]
            st.markdown(f"""<div style="background:rgba(5,150,105,.06);border:1px solid rgba(5,150,105,.15);border-radius:12px;padding:14px 20px;margin:12px 0">
                <div style="font-size:.82rem;font-weight:700;color:{GA}">💡 추천: 공고 {best_idx+1} — {best_n.title[:50]}</div>
                <div style="font-size:.78rem;color:{t['text2']};margin-top:4px">수주확률 {wps[best_idx]:.0f}%로 가장 높은 기회입니다.</div>
            </div>""", unsafe_allow_html=True)

        elif len(sel_notices) == 1:
            st.info("비교를 위해 최소 2건의 공고를 선택해주세요.")


# =============================================================================
#  PAGE: Proposals
# =============================================================================

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


# =============================================================================
#  PAGE: Competitor Analysis
# =============================================================================

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

                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(_kpi(s.get("total_notices", 0), "전체 공고"), unsafe_allow_html=True)
                c2.markdown(_kpi(s.get("competitor_related", 0), "경쟁사 관련"), unsafe_allow_html=True)
                c3.markdown(_kpi(f'{s.get("competitor_ratio", 0)}%', "경쟁 비율"), unsafe_allow_html=True)
                c4.markdown(_kpi(s.get("tier1_count", 0), "Tier1 탐지", GD), unsafe_allow_html=True)

                tc = s.get("top_competitors", [])
                if tc:
                    st.markdown(_section("경쟁사 탐지 TOP 10"), unsafe_allow_html=True)
                    fig = go.Figure(go.Bar(x=[c[1] for c in tc[:10]], y=[c[0] for c in tc[:10]],
                                          orientation='h', marker_color=P))
                    fig.update_layout(height=380, yaxis=dict(autorange="reversed"),
                                      xaxis=dict(gridcolor=t['border'], title="탐지 횟수"), **_layout())
                    st.plotly_chart(fig, width="stretch")
                if cn:
                    st.markdown(_section(f"경쟁사 관련 공고 ({len(cn)}건)"), unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame([{
                        "등급": c["grade"], "공고명": c["title"][:55], "사이트": c["site"],
                        "마감일": c["deadline"] or "-", "경쟁사": " / ".join(c["competitors"]),
                        "Tier": " / ".join(c["tiers"])
                    } for c in cn]), width="stretch", height=380)
            except Exception as e:
                st.error(f"경쟁사 분석 실패: {e}")


# =============================================================================
#  PAGE: Win Prediction
# =============================================================================

if page == "🎯 수주 예측":
    result = _result()
    if not result:
        st.markdown(_empty("🎯", "수주 예측 데이터 없음", "수집 실행 후 공고별 수주 확률을 예측합니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        from interx_engine.application.use_cases.win_prediction import WinPredictionUseCase, _extract_v2_features, _WEIGHTS_V2
        notices = result.get("notices", []); smap = _smap(result)

        _wp_uc = WinPredictionUseCase()
        _wp_info = _wp_uc.model_info
        preds = []
        for n in notices:
            sc = smap.get(n.notice_id)
            if not sc: continue
            feats = _extract_v2_features(n, sc)
            wp = sum(_WEIGHTS_V2.get(k, 0) * v for k, v in feats.items() if k in _WEIGHTS_V2)
            wp = min(1.0, max(0.0, wp)) * 100
            preds.append({"notice": n, "sc": sc, "wp": wp, "feats": feats})
        preds.sort(key=lambda x: -x["wp"])

        hp = sum(1 for p in preds if p["wp"] >= 60)
        avg = sum(p["wp"] for p in preds) / max(1, len(preds))
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(_kpi(len(preds), "예측 대상"), unsafe_allow_html=True)
        k2.markdown(_kpi(hp, "유망 60%+", GA), unsafe_allow_html=True)
        k3.markdown(_kpi(f"{avg:.0f}%", "평균 확률"), unsafe_allow_html=True)
        _ml_label = f'{_wp_info["model"]}' if _wp_info["mode"] == "ml" else "RuleV2"
        k4.markdown(_kpi(_ml_label, "ML 모델", A2), unsafe_allow_html=True)

        _ml_badge_color = GA if _wp_info["mode"] == "ml" else P
        _ml_status = "ML 활성" if _wp_info["mode"] == "ml" else "룰 기반 (학습 데이터 수집 중)"
        st.markdown(f'<div style="background:{t["card"]};border:1px solid {t["border"]};border-radius:10px;padding:10px 16px;margin:8px 0;display:flex;align-items:center;gap:12px"><span style="background:{_ml_badge_color};color:#fff;padding:3px 10px;border-radius:6px;font-size:.72rem;font-weight:700">{_ml_status}</span><span style="font-size:.78rem;color:{t["text3"]}">v2 피처 10개 · {_wp_info.get("accuracy","—")} 정확도</span></div>', unsafe_allow_html=True)

        col_h, col_t = st.columns([1, 2])
        with col_h:
            bins = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
            for p in preds:
                w = p["wp"]
                if w < 20: bins["0-20"] += 1
                elif w < 40: bins["20-40"] += 1
                elif w < 60: bins["40-60"] += 1
                elif w < 80: bins["60-80"] += 1
                else: bins["80-100"] += 1
            fig = go.Figure(go.Bar(x=[f"{k}%" for k in bins], y=list(bins.values()),
                                   marker_color=[GD, GC, "#FBBF24", GB, GA]))
            fig.update_layout(title=dict(text="확률 분포", font=dict(size=14, color=t['text'])),
                              height=330, xaxis=dict(title="구간"), yaxis=dict(title="건수", gridcolor=t['border']), **_layout())
            st.plotly_chart(fig, width="stretch")

        with col_t:
            st.markdown(_section("수주 유망 TOP 10"), unsafe_allow_html=True)
            for _wi, p in enumerate(preds[:10]):
                n, sc, wp, feats = p["notice"], p["sc"], p["wp"], p["feats"]
                c = GA if wp >= 60 else GB if wp >= 40 else GC
                meta = f"{sc.priority_grade}등급 · {n.site} · {n.agency or '-'} · {n.deadline_date or '-'}"
                st.markdown(_notice_row(sc.priority_grade, f'<span style="color:{c};font-weight:800">{wp:.0f}%</span> {n.title[:50]}', meta), unsafe_allow_html=True)
                with st.expander("🔍 수주 가능성 분석", expanded=False):
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
                        _bc2 = GA if _fv >= 8 else GB if _fv >= 4 else GC if _fv >= 1 else t['text3']
                        _bar_html += f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:.78rem"><span style="width:100px;color:{t["text2"]};font-weight:600;text-align:right">{_fl}</span><div style="flex:1;background:{t["bg3"]};border-radius:4px;height:18px;overflow:hidden"><div style="width:{_bw}%;height:100%;background:{_bc2};border-radius:4px"></div></div><span style="width:100px;color:{t["text3"]};font-size:.72rem">{_raw:.2f}x{_w:.2f}={_fv:.1f}</span></div>'
                    st.markdown(f'<div style="padding:4px 0">{_bar_html}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="text-align:right;font-size:.85rem;font-weight:800;color:{c};margin-top:6px">합계: {wp:.0f}%</div>', unsafe_allow_html=True)
                    _f = sc.fitness_score or 0; _dd = _dday(n.deadline_date or "")
                    _reasons = []
                    if _f >= 40: _reasons.append(f"키워드 적합도 높음 ({_f:.0f}점)")
                    if sc.positive_keywords: _reasons.append(f"매칭 키워드: {', '.join(sc.positive_keywords[:5])}")
                    if n.l3_strong == "Y": _reasons.append("L3 강공고 해당")
                    if sc.tfidf_similarity >= 0.3: _reasons.append(f"InterX 유사도 {sc.tfidf_similarity:.0%}")
                    if sc.combo_keywords: _reasons.append(f"콤보: {', '.join(sc.combo_keywords[:3])}")
                    if 0 <= _dd <= 7: _reasons.append(f"마감 임박 D-{_dd}")
                    sol_hits = [(s, v) for s, v in (sc.solution_scores or {}).items() if v > 0]
                    if sol_hits: _reasons.append(f"솔루션: {', '.join(s for s, _ in sorted(sol_hits, key=lambda x: -x[1])[:3])}")
                    if _reasons:
                        st.markdown("**📌 핵심 근거**: " + " · ".join(_reasons))

        # ML Training Data
        st.markdown(_section("🤖 ML 학습 데이터 현황"), unsafe_allow_html=True)
        _train_dir = ROOT / "data" / "exports" / "training"
        if _train_dir.exists():
            _jsonl_files = sorted(_train_dir.glob("*.jsonl"), reverse=True)
            _total_lines = 0
            for _jf in _jsonl_files[:10]:
                _total_lines += sum(1 for line in _jf.read_text(encoding="utf-8").splitlines() if line.strip())
            st.markdown(f'<div style="background:{t["card"]};border:1px solid {t["border"]};border-radius:10px;padding:12px 16px;font-size:.82rem;color:{t["text"]}">JSONL 파일 <b>{len(_jsonl_files)}</b>개 · 총 <b>{_total_lines}</b>건 · 20건 이상 시 ML 학습 가능</div>', unsafe_allow_html=True)
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
                                fig_fi = go.Figure(go.Bar(x=list(fi.values()), y=list(fi.keys()),
                                                          orientation='h', marker_color=P))
                                fig_fi.update_layout(title=dict(text="피처 중요도", font=dict(size=14, color=t['text'])),
                                                     height=300, xaxis=dict(title="중요도"), **_layout())
                                st.plotly_chart(fig_fi, width="stretch")
                        except Exception as e:
                            st.error(f"학습 실패: {e}")
        else:
            st.markdown(f'<div style="font-size:.82rem;color:{t["text3"]};padding:8px">수집을 실행하면 학습 데이터가 자동으로 축적됩니다.</div>', unsafe_allow_html=True)


# =============================================================================
#  PAGE: Deadline Calendar
# =============================================================================

if page == "📅 마감 캘린더":
    result = _result()
    if not result:
        st.markdown(_empty("📅", "마감 캘린더 데이터 없음", "수집 실행 후 마감일 관리를 할 수 있습니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); smap = _smap(result)
        upcoming = []
        for n in notices:
            dl = n.deadline_date or ""
            if not dl: continue
            dd = _dday(dl)
            if dd < 0: continue
            upcoming.append({"date": dl, "dday": dd, "notice": n, "sc": smap.get(n.notice_id)})
        upcoming.sort(key=lambda x: x["dday"])

        d3 = sum(1 for u in upcoming if u["dday"] <= 3)
        d7 = sum(1 for u in upcoming if u["dday"] <= 7)
        d30 = sum(1 for u in upcoming if u["dday"] <= 30)
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(_kpi(d3, "3일내 마감", GD), unsafe_allow_html=True)
        k2.markdown(_kpi(d7, "7일내 마감", GC), unsafe_allow_html=True)
        k3.markdown(_kpi(d30, "30일내 마감"), unsafe_allow_html=True)
        k4.markdown(_kpi(len(upcoming), "전체 미마감"), unsafe_allow_html=True)

        if upcoming:
            dates = sorted(set(u["date"] for u in upcoming))[:30]
            dc = Counter(u["date"] for u in upcoming)
            fig = go.Figure(go.Bar(x=dates, y=[dc[d] for d in dates], marker_color=[
                GD if _dday(d) <= 3 else GC if _dday(d) <= 7 else P for d in dates]))
            fig.update_layout(height=280, xaxis=dict(title="마감일"), yaxis=dict(title="건수", gridcolor=t['border']), **_layout())
            st.plotly_chart(fig, width="stretch")

        st.markdown(_section(f"긴급 마감 D-7 이내 ({d7}건)"), unsafe_allow_html=True)
        for u in upcoming:
            if u["dday"] > 7: break
            n, sc, dd = u["notice"], u["sc"], u["dday"]
            grade = sc.priority_grade if sc else "D"
            pill = _pill(f"D-{dd}", "urgent") if dd <= 3 else _pill(f"D-{dd}", "c")
            apply_st = _apply_badge(getattr(n, "apply_status", ""))
            meta = f"{n.site} · {n.agency or '-'} · 마감 {n.deadline_date}"
            st.markdown(_notice_row(grade, n.title[:55], meta, f"{apply_st} {pill}"), unsafe_allow_html=True)


# =============================================================================
#  PAGE: Analytics (Solution + Keywords + History)
# =============================================================================

if page == "📈 분석":
    result = _result()
    _an_tab = st.radio("분석 항목", ["🔧 솔루션", "📈 키워드", "🕐 히스토리"], horizontal=True, label_visibility="collapsed")

    if _an_tab == "🔧 솔루션":
        if not result:
            st.markdown(_empty("🔧", "솔루션 분석 데이터 없음", "수집 실행 후 8개 솔루션별 매칭 분석을 제공합니다."), unsafe_allow_html=True)
        else:
            import plotly.graph_objects as go
            score_cards = result.get("score_cards", [])
            SOL = {"ManufacturingDT": "제조 DT", "RecipeAI": "레시피 AI", "QualityAI": "품질 AI",
                   "InspectionAI": "비전검사", "SafetyAI": "안전 AI", "GenAI": "GenAI",
                   "InfraDS": "데이터 인프라", "PdM": "예지보전"}
            sol_t = defaultdict(list)
            for sc in score_cards:
                if sc.solution_scores:
                    for k, v in sc.solution_scores.items():
                        if v > 0: sol_t[k].append(v)
            if sol_t:
                sol_avg = {k: sum(v) / len(v) for k, v in sol_t.items()}
                sol_cnt = {k: len(v) for k, v in sol_t.items()}
                ss = sorted(sol_avg.items(), key=lambda x: -x[1])
                top = ss[0] if ss else ("N/A", 0)

                k1, k2, k3 = st.columns(3)
                k1.markdown(_kpi(len(sol_t), "매칭 솔루션"), unsafe_allow_html=True)
                k2.markdown(_kpi(SOL.get(top[0], top[0]), "TOP 솔루션"), unsafe_allow_html=True)
                k3.markdown(_kpi(f"{top[1]:.0f}", "TOP 평균점수"), unsafe_allow_html=True)

                cr, cb = st.columns(2)
                with cr:
                    cats = [SOL.get(k, k) for k in sol_avg]; vals = list(sol_avg.values())
                    fig = go.Figure(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]], fill='toself',
                        fillcolor='rgba(245,146,27,.08)', line=dict(color=P, width=2.5), marker=dict(size=6, color=P)))
                    fig.update_layout(title=dict(text="솔루션 레이더", font=dict(size=14, color=t['text'])),
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100], gridcolor=t['border']),
                                   bgcolor=t['bg3'], angularaxis=dict(gridcolor=t['border'])),
                        height=380, **_layout())
                    st.plotly_chart(fig, width="stretch")
                with cb:
                    names = [SOL.get(k, k) for k, _ in ss]; avgs = [v for _, v in ss]; cnts = [sol_cnt[k] for k, _ in ss]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=names, y=avgs, name="평균 점수", marker_color=P))
                    fig.add_trace(go.Bar(x=names, y=cnts, name="매칭 공고", marker_color=GB))
                    fig.update_layout(title=dict(text="솔루션별 비교", font=dict(size=14, color=t['text'])),
                                      barmode='group', height=380,
                                      xaxis=dict(gridcolor=t['border']), yaxis=dict(gridcolor=t['border']),
                                      legend=dict(orientation="h", y=1.12), **_layout())
                    st.plotly_chart(fig, width="stretch")
            else:
                st.markdown(_empty("🔧", "솔루션 데이터 없음", "매칭되는 솔루션이 없습니다."), unsafe_allow_html=True)

    elif _an_tab == "📈 키워드":
        if not result:
            st.markdown(_empty("📈", "키워드 데이터 없음", "수집 실행 후 시장 키워드 트렌드를 분석합니다."), unsafe_allow_html=True)
        else:
            import plotly.graph_objects as go
            notices = result.get("notices", []); score_cards = result.get("score_cards", [])
            kw_c = Counter()
            for sc in score_cards:
                if sc.positive_keywords:
                    for k in sc.positive_keywords: kw_c[k] += 1
            title_w = Counter()
            stops = {"사업", "지원", "공고", "모집", "안내", "위한", "대한", "관련", "통한", "기반", "활용", "추진",
                     "참여", "신청", "접수", "대상", "분야", "과제", "수행", "기관", "선정", "계획", "결과", "변경",
                     "연장", "프로그램", "센터", "재공고", "용역", "발표", "공지", "정보", "운영", "기술", "개발",
                     "산업", "기업", "육성", "연구", "전문", "협력", "국내", "혁신", "전략", "구축", "도입", "확대",
                     "사항", "가능", "제공", "진행", "통해", "등록", "기타", "문의", "담당", "홈페이지", "바로가기",
                     "상반기", "하반기", "년도", "차년도", "연도", "해당",
                     "참여기업", "모집공고", "2025년", "2025년도", "2026년", "2026년도", "2027년", "2027년도",
                     "수요기업", "공모", "통합", "시행", "예정", "일정", "기간", "방법", "절차", "요강",
                     "수정", "재안내", "알림", "공개", "추가", "확정", "최종", "우수", "평가", "심사",
                     "테크노파크", "진흥원", "진흥재단", "중소기업", "지원사업", "지방자치"}
            for n in notices:
                for w in (n.title or "").split():
                    c = "".join(ch for ch in w if ch.isalnum())
                    if len(c) < 2 or c in stops or re.fullmatch(r'\d+', c) or re.fullmatch(r'\d{4}년도?', c): continue
                    title_w[c] += 1

            k1, k2 = st.columns(2)
            k1.markdown(_kpi(len(kw_c), "매칭 키워드"), unsafe_allow_html=True)
            k2.markdown(_kpi(kw_c.most_common(1)[0][0] if kw_c else "-", "최다 키워드"), unsafe_allow_html=True)

            ck, ct = st.columns(2)
            with ck:
                if kw_c:
                    t20 = kw_c.most_common(20)
                    fig = go.Figure(go.Bar(y=[k[0] for k in reversed(t20)], x=[k[1] for k in reversed(t20)],
                                          orientation='h', marker_color=P))
                    fig.update_layout(title=dict(text="스코어링 키워드 TOP 20", font=dict(size=14, color=t['text'])),
                                      height=480, xaxis=dict(title="횟수", gridcolor=t['border']),
                                      **_layout(margin=dict(l=110, r=16, t=40, b=36)))
                    st.plotly_chart(fig, width="stretch")
            with ct:
                if title_w:
                    t20t = title_w.most_common(20)
                    fig = go.Figure(go.Bar(y=[k[0] for k in reversed(t20t)], x=[k[1] for k in reversed(t20t)],
                                          orientation='h', marker_color=GB))
                    fig.update_layout(title=dict(text="제목 빈출 단어 TOP 20", font=dict(size=14, color=t['text'])),
                                      height=480, xaxis=dict(title="횟수", gridcolor=t['border']),
                                      **_layout(margin=dict(l=110, r=16, t=40, b=36)))
                    st.plotly_chart(fig, width="stretch")

    elif _an_tab == "🕐 히스토리":
        history = st.session_state.get("collection_history", [])
        if not history:
            st.markdown(_empty("🕐", "수집 히스토리 없음", "수집을 실행하면 결과가 여기에 기록됩니다."), unsafe_allow_html=True)
        else:
            import plotly.graph_objects as go
            latest = history[-1]
            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(_kpi(len(history), "총 수집 횟수"), unsafe_allow_html=True)
            k2.markdown(_kpi(latest["total"], "최근 수집건수"), unsafe_allow_html=True)
            k3.markdown(_kpi(latest["grades"].get("A", 0), "최근 A등급", GA), unsafe_allow_html=True)
            if len(history) >= 2:
                diff = latest["total"] - history[-2]["total"]
                ds = f"+{diff}" if diff > 0 else str(diff)
                dd = "up" if diff > 0 else "down" if diff < 0 else ""
                k4.markdown(_kpi(ds, "이전 대비", GA if diff > 0 else GD if diff < 0 else "", delta_dir=dd), unsafe_allow_html=True)
            else:
                k4.markdown(_kpi("-", "이전 대비"), unsafe_allow_html=True)

            st.markdown(_section("수집 기록"), unsafe_allow_html=True)
            hrows = [{"#": i, "수집일시": h["timestamp"], "모드": h.get("mode", "-"), "전체": h["total"],
                      "A": h["grades"].get("A", 0), "B": h["grades"].get("B", 0),
                      "C": h["grades"].get("C", 0), "D": h["grades"].get("D", 0),
                      "L3": h.get("l3_count", 0), "제안서": h.get("proposals", 0),
                      "사이트": len(h.get("sites", {}))} for i, h in enumerate(reversed(history), 1)]
            st.dataframe(pd.DataFrame(hrows), width="stretch", height=280)

            try:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    pd.DataFrame(hrows).to_excel(w, index=False, sheet_name="히스토리")
                st.download_button("📊 히스토리 Excel", buf.getvalue(),
                                   f"interx_history_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception: pass

            if len(history) >= 2:
                ct_col, cg_col = st.columns(2)
                with ct_col:
                    ts = [h["timestamp"][:16] for h in history]; tots = [h["total"] for h in history]
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=ts, y=tots, mode='lines+markers', name='전체',
                                            line=dict(color=P, width=3), marker=dict(size=8, color=P)))
                    fig.add_trace(go.Scatter(x=ts, y=[h["grades"].get("A", 0) for h in history],
                                            mode='lines+markers', name='A등급',
                                            line=dict(color=GA, width=2), marker=dict(size=6, color=GA)))
                    fig.update_layout(title=dict(text="수집 추이", font=dict(size=14, color=t['text'])), height=330,
                                      xaxis=dict(gridcolor=t['border']), yaxis=dict(title="건수", gridcolor=t['border']),
                                      legend=dict(orientation="h", y=1.12), **_layout())
                    st.plotly_chart(fig, width="stretch")
                with cg_col:
                    lg = history[-1]["grades"]; pg = history[-2]["grades"]
                    gl = ["A", "B", "C", "D"]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name="이전", x=gl, y=[pg.get(g, 0) for g in gl], marker_color=t['text3']))
                    fig.add_trace(go.Bar(name="최근", x=gl, y=[lg.get(g, 0) for g in gl], marker_color=[GA, GB, GC, GD]))
                    fig.update_layout(title=dict(text="등급 비교", font=dict(size=14, color=t['text'])), height=330,
                                      barmode='group', xaxis=dict(gridcolor=t['border']),
                                      yaxis=dict(title="건수", gridcolor=t['border']),
                                      legend=dict(orientation="h", y=1.12), **_layout())
                    st.plotly_chart(fig, width="stretch")

                st.markdown(_section("사이트별 변화"), unsafe_allow_html=True)
                ls = history[-1].get("sites", {}); ps = history[-2].get("sites", {})
                asn = sorted(set(list(ls) + list(ps)))
                if asn:
                    sr = [{"사이트": s, "최근": ls.get(s, 0), "이전": ps.get(s, 0),
                           "변화": f"+{ls.get(s, 0) - ps.get(s, 0)}" if ls.get(s, 0) - ps.get(s, 0) > 0
                           else str(ls.get(s, 0) - ps.get(s, 0))} for s in asn]
                    st.dataframe(pd.DataFrame(sr), width="stretch", height=280)


# =============================================================================
#  PAGE: Manager Overview
# =============================================================================

if page == "👤 담당자":
    result = _result()
    if not result:
        st.markdown(_empty("👤", "담당자 현황 없음", "수집 실행 후 담당자별 공고 배분을 확인할 수 있습니다."), unsafe_allow_html=True)
    else:
        import plotly.graph_objects as go
        notices = result.get("notices", []); smap = _smap(result)
        md = defaultdict(lambda: {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0})
        for n in notices:
            mgr = n.manager or "미배정"; sc = smap.get(n.notice_id); g = sc.priority_grade if sc else "D"
            md[mgr]["total"] += 1; md[mgr][g] += 1

        tm = len([m for m in md if m != "미배정"]); ua = md.get("미배정", {}).get("total", 0)
        k1, k2, k3 = st.columns(3)
        k1.markdown(_kpi(tm, "배정 담당자"), unsafe_allow_html=True)
        k2.markdown(_kpi(len(notices) - ua, "배정 완료"), unsafe_allow_html=True)
        k3.markdown(_kpi(ua, "미배정", GD), unsafe_allow_html=True)

        if md:
            mgrs = sorted(md, key=lambda m: -md[m]["total"])
            fig = go.Figure()
            for g, c in [("A", GA), ("B", GB), ("C", GC), ("D", GD)]:
                fig.add_trace(go.Bar(name=g, x=mgrs, y=[md[m][g] for m in mgrs], marker_color=c))
            fig.update_layout(title=dict(text="담당자별 등급 분포", font=dict(size=14, color=t['text'])),
                              barmode='stack', height=380,
                              legend=dict(orientation="h", y=1.12),
                              xaxis=dict(gridcolor=t['border']), yaxis=dict(title="건수", gridcolor=t['border']),
                              **_layout())
            st.plotly_chart(fig, width="stretch")

        st.markdown(_section("담당자 상세"), unsafe_allow_html=True)
        mrows = [{"담당자": m, "전체": d["total"], "A": d["A"], "B": d["B"], "C": d["C"], "D": d["D"],
                  "A비율": f'{d["A"] / max(1, d["total"]) * 100:.0f}%'} for m, d in sorted(md.items(), key=lambda x: -x[1]["total"])]
        st.dataframe(pd.DataFrame(mrows), width="stretch", height=350)


# =============================================================================
#  PAGE: AI News & Trends
# =============================================================================

if page == "🤖 AI 뉴스":
    import xml.etree.ElementTree as ET
    import requests as _req
    from html import unescape as _unescape

    @st.cache_data(ttl=1800, show_spinner=False)
    def _fetch_rss(url, limit=8):
        try:
            r = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()
                content_encoded = ""
                for el in item:
                    if el.tag.endswith("encoded") or el.tag.endswith("content"):
                        content_encoded = (el.text or "").strip(); break
                pub = (item.findtext("pubDate") or "").strip()
                if not title: continue
                raw = content_encoded if len(content_encoded) > len(desc) else desc
                raw = re.sub(r'<[^>]+>', '', _unescape(raw)).strip()
                sents = [s.strip() for s in re.split(r'(?<=[.다요됨함])\s+', raw) if len(s.strip()) > 15]
                items.append({
                    "title": _unescape(title), "link": link,
                    "desc": raw[:200], "summary": sents[:3] if sents else [raw[:300]],
                    "full_desc": raw[:800], "date": pub[:16] if pub else "",
                })
                if len(items) >= limit: break
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns) or root.iter("entry"):
                    title = ""
                    for tt in entry.iter():
                        if tt.tag.endswith("title"): title = (tt.text or "").strip(); break
                    link = ""
                    for ll in entry.iter():
                        if ll.tag.endswith("link"): link = ll.get("href", "") or (ll.text or "").strip(); break
                    raw_text = ""
                    for ss in entry.iter():
                        if ss.tag.endswith("content") or ss.tag.endswith("summary"):
                            raw_text = (ss.text or "").strip(); break
                    if not title: continue
                    raw_text = re.sub(r'<[^>]+>', '', _unescape(raw_text)).strip()
                    sents = [s.strip() for s in re.split(r'(?<=[.다요됨함])\s+', raw_text) if len(s.strip()) > 15]
                    items.append({
                        "title": _unescape(title), "link": link,
                        "desc": raw_text[:200], "summary": sents[:3] if sents else [raw_text[:300]],
                        "full_desc": raw_text[:800], "date": "",
                    })
                    if len(items) >= limit: break
            return items
        except Exception:
            return []

    @st.cache_data(ttl=3600, show_spinner=False)
    def _fetch_article_summary(url):
        try:
            r = _req.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r.raise_for_status()
            from bs4 import BeautifulSoup as _BS
            soup = _BS(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "iframe"]):
                tag.decompose()
            article = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|body|entry"))
            target = article if article else soup
            paragraphs = target.find_all("p")
            text_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
            if not text_parts: text_parts = [target.get_text(" ", strip=True)[:1500]]
            full = " ".join(text_parts[:10])
            sents = [s.strip() for s in re.split(r'(?<=[.다요됨함!?])\s+', full) if len(s.strip()) > 20]
            return sents[:5] if sents else [full[:500]]
        except Exception:
            return []

    st.markdown(_section("AI / 제조 / IT 산업 뉴스"), unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:.8rem;color:{t["text3"]}">RSS 피드 기반 실시간 뉴스 · 30분 캐시</p>', unsafe_allow_html=True)

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
                st.markdown(f'''<div style="background:{t['card']};border:1px solid {t['border']};border-radius:10px;padding:14px 18px;margin-bottom:4px">
<a href="{it["link"]}" target="_blank" style="text-decoration:none;color:{t['text']};font-weight:700;font-size:.88rem;line-height:1.4">{it["title"]}</a>
<span style="font-size:.72rem;color:{t['text3']}">{_date_str}</span>
<div style="font-size:.78rem;color:{t['text2']};margin-top:6px;line-height:1.55">{it["desc"]}</div>
</div>''', unsafe_allow_html=True)
                _exp_key = f"news_{feed_name}_{_ni}"
                with st.expander("📌 핵심 내용 보기", expanded=False):
                    if it["summary"] and it["summary"][0]:
                        for _si, _sent in enumerate(it["summary"]):
                            if _sent and len(_sent) > 10:
                                st.markdown(f'<div style="font-size:.82rem;color:{t["text"]};line-height:1.6;padding:2px 0 2px 12px;border-left:2px solid {P}"><b>{_si + 1}.</b> {_sent[:200]}</div>', unsafe_allow_html=True)
                    if it.get("link"):
                        if st.button("📖 원문 상세 요약 가져오기", key=f"fetch_{_exp_key}"):
                            with st.spinner("기사 본문 분석중..."):
                                _art_sents = _fetch_article_summary(it["link"])
                            if _art_sents:
                                st.markdown(f'<div style="background:{t["bg3"]};border-radius:8px;padding:12px 16px;margin-top:8px">', unsafe_allow_html=True)
                                st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:{P};margin-bottom:8px">기사 핵심 요약</div>', unsafe_allow_html=True)
                                for _ai_idx, _as in enumerate(_art_sents):
                                    st.markdown(f'<div style="font-size:.82rem;color:{t["text"]};line-height:1.6;padding:3px 0 3px 14px;border-left:2px solid {A2}"><b>▸</b> {_as[:250]}</div>', unsafe_allow_html=True)
                                st.markdown('</div>', unsafe_allow_html=True)
                            else:
                                st.caption("원문 요약을 가져올 수 없습니다.")
        else:
            st.markdown(f'<div style="font-size:.8rem;color:{t["text3"]};padding:8px">피드를 불러올 수 없습니다. <a href="{feed_url}" target="_blank">직접 방문</a></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(_section("주요 사이트 바로가기"), unsafe_allow_html=True)
    _links = [
        ("K-스마트공장", "https://www.smart-factory.kr/"), ("IITP", "https://www.iitp.kr/"),
        ("NIPA", "https://www.nipa.kr/"), ("과기정통부", "https://www.msit.go.kr/"),
        ("arXiv AI", "https://arxiv.org/list/cs.AI/recent"), ("Papers With Code", "https://paperswithcode.com/"),
        ("Hugging Face", "https://huggingface.co/blog"), ("Manufacturing Dive", "https://www.manufacturingdive.com/"),
    ]
    _link_html = " ".join(f'<a href="{u}" target="_blank" style="background:rgba(255,128,0,.06);color:{P};border:1px solid rgba(255,128,0,.15);padding:6px 16px;border-radius:20px;font-size:.8rem;font-weight:600;text-decoration:none;display:inline-block;margin:3px">{n}</a>' for n, u in _links)
    st.markdown(f'<div style="line-height:2.4">{_link_html}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown(_section("오늘의 AI 키워드"), unsafe_allow_html=True)
    _ai_keywords = ["에이전틱AI", "피지컬AI", "디지털트윈", "자율공정", "AI팩토리",
                     "생성형AI", "LLM", "Multi-Agent", "스마트공장", "예지보전",
                     "컴퓨터비전", "AI반도체", "엣지AI", "DTaaS", "로보틱스"]
    _kw_html = " ".join(f'<span style="background:{t["bg3"]};color:{t["text"]};padding:5px 14px;border-radius:20px;font-size:.8rem;font-weight:600;display:inline-block;margin:3px">{k}</span>' for k in _ai_keywords)
    st.markdown(f'<div style="line-height:2.2">{_kw_html}</div>', unsafe_allow_html=True)


# =============================================================================
#  PAGE: AI Chatbot (RAG)
# =============================================================================

if page == "💬 AI 챗봇":
    st.markdown(_section("AI 공고 분석 챗봇"), unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:.8rem;color:{t["text3"]}">수집된 공고 데이터 기반 자연어 질의응답 · Gemini 무료 API</p>', unsafe_allow_html=True)

    try:
        from interx_engine.infrastructure.ai.gemini_client import is_available as _ai_available
        _has_ai = _ai_available()
    except Exception:
        _has_ai = False

    if _has_ai:
        st.markdown(f'<div style="background:rgba(5,150,105,.06);border:1px solid rgba(5,150,105,.15);border-radius:8px;padding:8px 14px;font-size:.8rem;color:#065f46;margin-bottom:12px">Gemini AI 연결됨</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:rgba(217,119,6,.06);border:1px solid rgba(217,119,6,.15);border-radius:8px;padding:8px 14px;font-size:.8rem;color:#92400e;margin-bottom:12px">GEMINI_API_KEY 미설정 — 규칙 기반 검색만 가능합니다. <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#d97706;font-weight:700">무료 발급</a></div>', unsafe_allow_html=True)

    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    st.markdown(f'<div style="font-size:.78rem;color:{t["text3"]};margin-bottom:8px">예시 질문:</div>', unsafe_allow_html=True)
    _example_qs = ["A등급 공고 중 스마트공장 관련은?", "마감 7일 이내 공고 요약해줘", "이번에 수집된 L3 강공고는?", "디지털트윈 관련 공고 추천해줘"]
    _eq_cols = st.columns(len(_example_qs))
    for _eqi, _eq in enumerate(_example_qs):
        if _eq_cols[_eqi].button(_eq, key=f"eq_{_eqi}", width="stretch"):
            st.session_state.ai_chat_input = _eq

    for _msg in st.session_state.ai_chat_history:
        with st.chat_message(_msg["role"]):
            st.markdown(_msg["content"])

    _default_input = st.session_state.pop("ai_chat_input", "")
    _user_q = st.chat_input("공고에 대해 무엇이든 질문하세요...", key="ai_chat_box")
    if _default_input and not _user_q:
        _user_q = _default_input

    if _user_q:
        st.session_state.ai_chat_history.append({"role": "user", "content": _user_q})
        with st.chat_message("user"):
            st.markdown(_user_q)

        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                try:
                    result = _result()
                    _all_notices = result.get("notices", []) if result else []
                    _all_scores = result.get("score_cards", []) if result else []
                    _sc_map = {s.notice_id: s for s in _all_scores}

                    from interx_engine.infrastructure.ai.chatbot import answer_question
                    _answer = answer_question(
                        question=_user_q, notices=_all_notices, score_map=_sc_map,
                        chat_history=st.session_state.ai_chat_history[:-1],
                    )
                    st.markdown(_answer)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": _answer})
                except Exception as _chat_err:
                    _err_msg = f"답변 생성 실패: {_chat_err}"
                    st.error(_err_msg)
                    st.session_state.ai_chat_history.append({"role": "assistant", "content": _err_msg})

    st.markdown("---")
    st.markdown(f'<div style="font-size:.9rem;font-weight:700;color:{t["text"]};margin:8px 0">일일 브리핑 자동 생성</div>', unsafe_allow_html=True)
    if st.button("📋 오늘의 브리핑 생성", key="gen_briefing"):
        with st.spinner("브리핑 생성 중..."):
            try:
                result = _result()
                _all_notices = result.get("notices", []) if result else []
                _all_scores = result.get("score_cards", []) if result else []
                _sc_map = {s.notice_id: s for s in _all_scores}
                _exec_id = result.get("execution_id", "") if result else ""

                from interx_engine.infrastructure.ai.briefing_generator import generate_briefing
                _briefing = generate_briefing(notices=_all_notices, score_map=_sc_map, execution_id=_exec_id)
                st.markdown(f'<div style="background:{t["card"]};border:1px solid {t["border"]};border-radius:12px;padding:16px 20px;font-size:.85rem;color:{t["text"]};white-space:pre-wrap;line-height:1.7">{_briefing}</div>', unsafe_allow_html=True)
                st.download_button("브리핑 텍스트 다운로드", _briefing, "interx_briefing.txt", "text/plain")
            except Exception as _br_err:
                st.error(f"브리핑 생성 실패: {_br_err}")

    if st.session_state.ai_chat_history:
        if st.button("대화 초기화", key="clear_chat"):
            st.session_state.ai_chat_history = []
            st.rerun()
