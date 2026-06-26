from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.scoring")

# ── 기본 임계값 (scoring.yaml 로드 실패 시 fallback) ──────────────────────────
_L3_DEFAULT      = 35
_PARTNER_DEFAULT = 20
_GRADE_A         = 48
_GRADE_B         = 30
_GRADE_C         = 18
_NEG_MULT        = 6.0
_POS_MULT        = 5.0
_STRUCT_BONUS    = 1.5
_BUDGET_BONUS    = 3.0
_SCALE           = 15.0
_W_FIT           = 0.6
_W_IND           = 0.4


def _load_thresholds(config_path: str | None = None) -> dict:
    """scoring.yaml에서 임계값 로드. 실패 시 기본값 반환."""
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    # 프로젝트 루트 자동 탐색 (src 기준 2단계 위)
    here = Path(__file__).resolve()
    for _ in range(6):
        candidate = here / "configs" / "scoring.yaml"
        if candidate.exists():
            candidates.append(candidate)
        here = here.parent

    for p in candidates:
        try:
            import yaml
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            t = raw.get("thresholds", {})
            pf = raw.get("priority_formula", {})
            sol = raw.get("solutions", {})
            # combo_keywords: [[kw_a, kw_b, bonus], ...] → List[tuple]
            combo_raw = raw.get("combo_keywords", [])
            combo_list = []
            for item in combo_raw:
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    combo_list.append((str(item[0]), str(item[1]), float(item[2])))

            return {
                "L3_THRESHOLD":      t.get("l3_strong",        _L3_DEFAULT),
                "PARTNER_THRESHOLD": t.get("partner_candidate", _PARTNER_DEFAULT),
                "GRADE_A":           t.get("grade_a",          _GRADE_A),
                "GRADE_B":           t.get("grade_b",          _GRADE_B),
                "GRADE_C":           t.get("grade_c",          _GRADE_C),
                "NEG_MULT":          t.get("neg_multiplier",          _NEG_MULT),
                "NEG_MULT_STRONG":   t.get("neg_multiplier_strong",  _NEG_MULT),
                "NEG_MULT_MEDIUM":   t.get("neg_multiplier_medium",  4.0),
                "NEG_MULT_WEAK":     t.get("neg_multiplier_weak",    2.0),
                "POS_MULT":          t.get("pos_multiplier",         _POS_MULT),
                "STRUCT_BONUS":      t.get("struct_bonus_factor", _STRUCT_BONUS),
                "BUDGET_BONUS":      t.get("budget_bonus",     _BUDGET_BONUS),
                "SCALE":             sol.get("scale_factor",   _SCALE),
                "W_FIT":             pf.get("w_fitness",       _W_FIT),
                "W_IND":             pf.get("w_industry",      _W_IND),
                "COMBO_KEYWORDS":    combo_list,
            }
        except Exception as e:
            log.warning("scoring.yaml 로드 실패 (%s): %s — fallback 기본값 사용", p, e)
            continue
    return {
        "L3_THRESHOLD": _L3_DEFAULT, "PARTNER_THRESHOLD": _PARTNER_DEFAULT,
        "GRADE_A": _GRADE_A, "GRADE_B": _GRADE_B, "GRADE_C": _GRADE_C,
        "NEG_MULT": _NEG_MULT, "NEG_MULT_STRONG": _NEG_MULT,
        "NEG_MULT_MEDIUM": 4.0, "NEG_MULT_WEAK": 2.0,
        "POS_MULT": _POS_MULT,
        "STRUCT_BONUS": _STRUCT_BONUS, "BUDGET_BONUS": _BUDGET_BONUS,
        "SCALE": _SCALE, "W_FIT": _W_FIT, "W_IND": _W_IND,
        "COMBO_KEYWORDS": [],  # YAML 로드 실패 시 빈 리스트
    }


_CFG = _load_thresholds()
L3_THRESHOLD      = _CFG["L3_THRESHOLD"]
PARTNER_THRESHOLD = _CFG["PARTNER_THRESHOLD"]
# YAML에서 콤보 키워드 로드 (없으면 코드 내 fallback 사용)
COMBO_KEYWORD_GROUPS: List[tuple] = (
    _CFG.get("COMBO_KEYWORDS") or _COMBO_KEYWORD_GROUPS_FALLBACK
)

# ── 제조/AI 필수 코어 키워드 (하나도 없으면 0점) ──────────────────────────────
CORE_KEYWORDS = {
    # ── 제조/스마트공장 핵심 (단독으로 코어 자격 충분) ──
    "제조", "스마트공장", "스마트팩토리", "디지털트윈", "디지털 트윈", "예지보전",
    "산업ai", "산업 ai", "제조ai", "제조 ai", "설비", "머신비전", "머신 비전",
    "자율제조", "자율공장", "자율형공장", "aas",
    "ax", "자동화", "iot", "센서",
    "ai공장", "ai 공장", "산업ai에이전트", "산업ai솔루션",
    "ai응용제품", "ai 응용제품", "제조dx", "학습데이터",
    # ── v3: 실제 수행 사업 기반 추가 ──
    "자율운영", "자율제어", "자율가공", "ai팩토리", "ai 팩토리",
    "암묵지", "뿌리", "밸류체인", "copilot", "코파일럿",
    "오케스트레이션", "ax실증",
    "제조안전", "파운데이션",
    # ── v3.1: 2026 신규 과제 목록 기반 추가 ──
    "에이전틱ai", "에이전틱", "agentic", "자율공정",
    "제조dtaas", "dtaas", "엔드프로덕트", "테스트베드",
    "소부장", "혁신바우처", "피지컬ai", "피지컬 ai",
    "물류자동화", "물류 자동화", "ai선박", "ai반도체",
    # ── 제조 맥락 필수 복합어 (단독 "품질","안전","공정" 등은 너무 범용 → 제거) ──
    "공정최적화", "공정제어", "공정자동화", "품질검사", "품질ai",
    "안전ai", "로봇자동화", "산업로봇", "협동로봇",
    # NOTE v5.7: "ai","인공지능","품질","안전","공정","데이터","로봇","클라우드",
    #   "플랫폼","poc","agent","에이전트","스케줄링","실증" 등 범용 단어 제거
    #   → 이들은 POSITIVE_KEYWORDS에서 가점만 부여 (코어 게이트 통과 X)
    #   → "디지털 품질 컨설팅", "AI 교육", "데이터분석 교육" 같은 오탐 방지
}

# ── 솔루션별 키워드 가중치 맵 ─────────────────────────────────────────────────
SOLUTION_MAP: Dict[str, Dict[str, float]] = {
    "ManufacturingDT": {
        "디지털트윈": 4, "디지털 트윈": 4, "시뮬레이션": 3, "공정": 2,
        "스마트팩토리": 3, "스마트공장": 3,
        "자율형공장": 4, "자율형 공장": 4, "자율제조": 4, "자율공장": 4,
        "manufacturing-x": 4, "ai팩토리": 4, "ai 팩토리": 4,
        "ai공장": 4, "ai 공장": 4,
        "디지털협업공장": 3, "ax실증": 4, "ax 실증": 4,
        "피지컬ai": 3, "클라우드제조": 3, "공동제조소": 3,
        "제조dx": 3, "제조 dx": 3,
        # v3: 실제 사업 기반 추가
        "자율운영": 4, "자율제어": 4, "자율가공": 4,
        "ax실증산단": 5, "ax 실증산단": 5,
        "밸류체인": 3, "뿌리공장": 4, "뿌리산업": 3,
        "copilot": 3, "코파일럿": 3, "인라인": 3,
        "closed-loop": 4, "통합관제": 3,
        "ai-ot": 4, "ai-ot 융합": 4, "ot융합": 4,
        "레전드50": 4, "레전드": 3,
        # v3.1: 2026 과제 키워드
        "제조dtaas": 4, "dtaas": 3, "자율공정": 4, "자율 공정": 4,
        "dx멘토": 3, "제조dx멘토": 4,
    },
    "RecipeAI": {
        "레시피": 4, "공정레시피": 4, "배합": 3, "조건최적화": 3,
        "공정최적화": 3, "공정 최적화": 3,
        "발효공정": 4, "사출공정": 3, "열공정": 3,
        "파운데이션모델": 2, "파운데이션 모델": 2,
        # v3: 실제 사업 기반 추가
        "배합조건": 4, "배합 조건": 4, "배합최적화": 4,
        "암묵지": 3, "제조암묵지": 4, "알룰로스": 3,
        "고무제조": 3, "열간단조": 3, "다이캐스팅": 3,
        "생산스케줄링": 4, "생산 스케줄링": 4, "스케줄링": 3,
        "열공정파운데이션": 5, "pinn": 4, "자율운영": 3,
        "closed-loop": 4, "클로즈드루프": 4,
    },
    "QualityAI": {
        "품질": 3, "불량": 3, "수율": 3,
        "이상탐지": 4, "이상 탐지": 4,
        "spc": 3, "제조안전": 2, "용접": 2, "용접ai": 4, "용접 ai": 4, "도장": 2,
        "quality.ai": 5,
        # v3: 실제 사업 기반 추가
        "품질예측": 5, "품질 예측": 5, "품질관리": 4, "품질 관리": 4,
        "품질최적화": 5, "품질 최적화": 5, "apqr": 5,
        "공정품질": 4, "공정품질이상": 5, "자율품질": 4,
        "용접품질": 5, "용접 품질": 5, "멀티모달": 3,
    },
    "InspectionAI": {
        "비전검사": 4, "비전 검사": 4, "외관검사": 4,
        "머신비전": 4, "머신 비전": 4,
        "비전": 2, "검사": 2, "비전ai": 4, "비전 ai": 4,
        "inspection.ai": 5,
    },
    "SafetyAI": {
        "안전": 3, "중대재해": 4, "위험": 2, "사고": 2,
        "안전모니터링": 3, "제조안전": 4, "산업안전": 3, "안전시스템": 4,
        "safety.ai": 5,
        # v3: 실제 사업 기반 추가
        "제조안전고도화": 5, "안전고도화": 4, "안전확보": 3,
        "4족보행": 3, "4족 보행": 3, "보행로봇": 3,
        "조선소안전": 4, "조선소 안전": 4, "안전환경": 3,
    },
    "GenAI": {
        "생성형ai": 4, "생성형 ai": 4, "llm": 4, "rag": 4, "gpt": 3,
        "멀티모달": 4, "ai에이전트": 4, "ai agent": 4,
        "파운데이션모델": 4, "파운데이션 모델": 4,
        "인공지능": 2, "제조인공지능": 4,
        "산업ai에이전트": 5, "산업 ai에이전트": 5,
        "산업ai솔루션": 4, "산업 ai솔루션": 4,
        "ai응용제품": 4, "ai 응용제품": 4,
        "경량화": 3, "학습데이터": 3,
        # v3: 실제 사업 기반 추가
        "산업문제해결형": 5, "산업문제해결": 5, "산업현장문제해결형": 5,
        "multi-ai agent": 5, "multi-ai": 4, "멀티에이전트": 4, "multi ai agent": 5,
        # v3.1: 에이전틱AI
        "에이전틱ai": 5, "에이전틱 ai": 5, "agentic ai": 5, "agentic": 4,
        "피지컬ai": 4, "피지컬 ai": 4, "physical ai": 4,
        "오케스트레이션": 4, "ai네이티브": 4, "ai 네이티브": 4,
        "도메인특화": 4, "도메인특화ai": 5, "도메인 특화": 4,
        "ai agent 융합": 5, "agent 융합": 4, "에이전트 융합": 4,
        "copilot": 3, "코파일럿": 3,
        "제조암묵지": 4, "암묵지": 3,
    },
    "InfraDS": {
        "데이터": 2, "api": 2, "mes": 3, "erp": 3, "plm": 2, "scm": 2,
        "ot": 3, "plc": 3, "scada": 3, "플랫폼": 2, "제조데이터": 3,
        "dpp": 3, "manufacturing-x": 3, "스마트제조혁신": 3,
        "aas": 4, "catena-x": 4, "데이터스페이스": 3,
        "gpu": 3, "학습데이터": 3, "학습 데이터": 3,
        "제조dx": 3, "제조 dx": 3, "솔루션실증": 3,
        # v3: 실제 사업 기반 추가
        "데이터표준화": 4, "데이터 표준화": 4, "참조모델": 3,
        "제조데이터표준화": 5, "제조데이터 표준화": 5,
        "지역특화제조데이터": 5, "빅데이터플랫폼": 4,
        "에너지진단": 3, "에너지진단플랫폼": 4,
        "한국형manufacturing-x": 5, "한국형 manufacturing-x": 5,
        # v3.1: DTaaS / AI반도체
        "제조dtaas": 5, "dtaas": 4, "ai반도체": 3, "ai 반도체": 3,
    },
    "PdM": {
        "예지보전": 4, "설비": 3, "모니터링": 3,
        "이상탐지": 3, "이상 탐지": 3, "iiot": 3,
        "센서": 3, "스마트센서": 4,
        "엣지ai": 3, "엣지 ai": 3, "온디바이스": 3, "온디바이스 ai": 3,
        # v3: 실제 사업 기반 추가
        "밸류체인협업": 4, "밸류체인 협업": 4,
        "설비예지보전": 5, "핵심설비": 4, "핵심 설비": 4,
        "통합예지보전": 5, "지능형iot": 4, "지능형 iot": 4,
    },
}

# ── 가점 키워드 ───────────────────────────────────────────────────────────────
# 공백 변형 쌍 (예: "제조ai" + "제조 ai") 모두 등록 — 한국 정부공고는 공백 표기 혼재
POSITIVE_KEYWORDS: Dict[str, float] = {
    # InterX 제품 브랜드명 (최고 가중치)
    "recipe.ai": 5, "quality.ai": 5, "inspection.ai": 5, "safety.ai": 5,
    # AX / 자율제조 계열
    "ax": 5, "ax-sprint": 5, "ax사업": 5, "ax실증": 5, "ax 실증": 5,
    "자율제조": 5, "자율공장": 5, "자율형공장": 5, "자율형 공장": 5,
    "ai 자율제조": 5, "manufacturing-x": 5,
    # AI 기반 제조
    "제조인공지능": 5, "제조ai": 5, "제조 ai": 5, "산업ai": 5, "산업 ai": 5,
    "피지컬ai": 5, "파운데이션모델": 5, "파운데이션 모델": 5,
    "멀티모달": 5, "ai에이전트": 5, "ai agent": 5,
    # [신규] AI 에이전트·솔루션·응용제품 (실제 공고에서 추출)
    "산업ai에이전트": 5, "산업 ai에이전트": 5, "산업ai에이전트기술개발": 5,
    "산업ai솔루션": 5, "산업 ai솔루션": 5, "솔루션실증": 5, "솔루션 실증": 5,
    "ai응용제품": 5, "ai 응용제품": 5, "ai응용": 4,
    # 스마트공장 / 디지털트윈
    "디지털트윈": 5, "디지털 트윈": 5,
    "스마트공장": 5, "스마트팩토리": 5, "자율형 스마트공장": 5,
    "ai팩토리": 5, "ai 팩토리": 5,
    "ai공장": 5, "ai 공장": 5,           # [신규] 제조AI특화 스마트공장 구축지원 핵심
    # [신규] 제조DX
    "제조dx": 4, "제조 dx": 4,
    # 솔루션 연관 키워드 (가중치 4)
    "aas": 4, "catena-x": 4, "발효공정": 4, "용접ai": 4, "용접 ai": 4,
    "비전ai": 4, "비전 ai": 4, "품질ai": 4, "품질 ai": 4,
    "신속상용화": 4, "신속 상용화": 4, "공동제조소": 4,
    "스마트제조혁신": 4, "예지보전": 4, "머신비전": 4, "머신 비전": 4,
    "비전검사": 4, "비전 검사": 4, "외관검사": 4,
    "이상탐지": 4, "이상 탐지": 4,
    "제조데이터": 4, "클라우드제조": 4, "디지털협업공장": 4,
    "공정최적화": 4, "공정 최적화": 4, "제조안전": 4, "중대재해": 4,
    "mes": 4, "plc": 4, "scada": 4,
    "협동로봇": 4, "스마트센서": 4,
    "엣지ai": 4, "엣지 ai": 4, "온디바이스": 4, "온디바이스 ai": 4,
    "버티컬ai": 4, "실증": 4, "상용화": 4, "고도화": 4,
    # [신규] AI 모델 개발 관련
    "학습데이터": 3, "학습 데이터": 3, "gpu": 3, "경량화": 3,
    # 일반 AI/제조 (가중치 3)
    "ai": 3, "인공지능": 3, "제조": 3, "품질": 3, "검사": 3, "iiot": 3,
    "공정": 3, "설비": 3, "모니터링": 3, "수율": 3,
    "불량": 3, "로봇": 3, "센서": 3, "자동화": 3, "안전": 3, "산업안전": 3,
    "생성형ai": 3, "생성형 ai": 3, "llm": 3, "rag": 3,
    "시뮬레이션": 3, "사출공정": 3, "이차전지": 3, "데이터스페이스": 3,
    # 일반 IT/사업 (가중치 2)
    "데이터": 2, "erp": 2, "plm": 2, "scm": 2, "플랫폼": 2, "gpt": 2,
    "비전": 2, "poc": 2, "r&d": 2, "r&bd": 2, "중견기업": 2,
    # 최소 신호 (가중치 1)
    "중소기업": 1, "클라우드": 1, "api": 1,
    # ── v3: 실제 수행 세부사업명 키워드 (최고 가중치) ──
    # TOP 빈도: AI응용제품(16건), 제조AI특화(12건), AI팩토리(12건), 자율형공장(10건)
    "ax실증산단": 6, "ax 실증산단": 6,
    "상생형 제조ax선도": 6, "제조ax선도": 6, "상생형제조ax": 6,
    "산업문제해결형ai": 6, "산업문제해결형": 5, "산업문제해결": 5,
    "ai agent 융합": 6, "agent 융합": 5, "에이전트 융합": 5, "에이전트융합": 5,
    "multi-ai agent": 6, "multi-ai": 5, "멀티에이전트": 5, "멀티 에이전트": 5,
    "제조암묵지": 5, "제조 암묵지": 5, "암묵지": 4,
    "제조ai특화": 6, "제조ai 특화": 6,
    "열공정파운데이션": 6, "열공정 파운데이션": 6,
    "제조안전고도화": 5, "안전고도화": 4,
    "ax혁신기업": 5, "ax혁신기업창의기술": 5, "ax혁신": 5,
    "레전드50": 5, "레전드": 4, "스마트공장레전드": 5,
    "ai네이티브": 5, "ai 네이티브": 5,
    "도메인특화ai": 5, "도메인특화": 4, "도메인 특화": 4,
    "지역주도형ai": 5, "지역주도형 ai": 5, "ai대전환": 5, "ai 대전환": 5,
    "뿌리산업": 4, "뿌리공장": 5, "올인원뿌리공장": 5,
    "로봇실증": 5, "ai로봇실증": 5, "ai로봇 실증": 5,
    "혁신공정장비": 4, "클라우드 단독형": 3,
    # ── v3: 실제 과제 기술 키워드 ──
    "자율운영": 5, "자율제어": 5, "자율가공": 5,
    "closed-loop": 5, "클로즈드루프": 5,
    "ai-ot": 5, "ai-ot 융합": 5, "ot융합": 4, "ot 융합": 4,
    "밸류체인": 4, "밸류체인 협업": 5,
    "pinn": 4, "copilot": 4, "코파일럿": 4,
    "오케스트레이션": 5, "ai 오케스트레이션": 5,
    "인라인": 3, "인라인검사": 4, "인라인 검사": 4,
    "생산스케줄링": 4, "생산 스케줄링": 4, "통합스케줄링": 4,
    "데이터표준화": 4, "데이터 표준화": 4, "참조모델": 3,
    "apqr": 4, "품질예측": 4, "품질관리": 3,
    "공정품질이상": 5, "품질이상": 4,
    "열간단조": 3, "다이캐스팅": 3, "절삭공정": 3, "사출공정": 3,
    "리드프레임": 3, "분리막": 3, "웨이퍼": 3, "임플란트": 3,
    "배합조건": 4, "배합 조건": 4, "배합최적화": 4,
    "알룰로스": 3, "고무제조": 3, "제지공정": 3,
    "4족보행": 3, "4족 보행": 3, "보행로봇": 3,
    "조선해양": 3, "조선소": 3,
    "통합관제": 4, "통합 관제": 4, "관제시스템": 4, "관제 시스템": 4,
    "지능형로봇": 5, "지능형 로봇": 5,
    # ── v3.1: 2026 신규 과제 키워드 ──
    # 에이전틱AI (새로운 핵심 키워드)
    "에이전틱ai": 6, "에이전틱 ai": 6, "에이전틱": 5, "agentic ai": 6, "agentic": 5,
    "능동행동형": 5, "능동행동형 에이전틱": 6,
    # 피지컬AI (새 공고 다수)
    "피지컬ai": 5, "피지컬 ai": 5, "physical ai": 5,
    "ai+x": 5, "ai + x": 5,
    # 제조DTaaS / 데이터 인프라
    "제조dtaas": 6, "dtaas": 5, "제조 dtaas": 6,
    "디지털전환 종합 플랫폼": 5, "디지털전환종합플랫폼": 5,
    # 자율공정 / 물류자동화
    "자율공정": 5, "자율 공정": 5,
    "물류자동화": 4, "물류 자동화": 4,
    # 엔드프로덕트 / 상용화 확장
    "엔드프로덕트": 5, "엔드 프로덕트": 5,
    # 소부장 / 테스트베드
    "소부장": 3, "테스트베드": 3, "테스트 베드": 3,
    # AI 선박 / AI 반도체
    "ai선박": 5, "ai 선박": 5,
    "ai반도체": 5, "ai 반도체": 5,
    # 혁신바우처 / 자율제안형
    "혁신바우처": 4, "혁신 바우처": 4,
    "자율제안형": 5, "자율 제안형": 5,
    # 지역혁신클러스터
    "지역혁신클러스터": 4, "지역혁신 클러스터": 4,
    # DX멘토단
    "dx멘토": 4, "제조dx멘토": 5, "제조dx멘토단": 5,
    # Multi AI Agent / PoC
    "multi ai agent": 6, "중소제조특화": 5, "중소제조 특화": 5,
    "poc시범": 4, "시범연구": 3,
    # 민간수요형 / 지역육성형
    "민간수요형": 4, "지역육성형": 4, "앵커기업": 3,
}

# ── 감점 키워드 3단계 (P6: bizinfo_datalist.py 대비 보강) ────────────────────
# strong: 완전 범위 외 (바이오/의료/건설/엔터) → neg_multiplier_strong (6.0)
# medium: 일부 관련 가능 (교육/인력/창업) → neg_multiplier_medium (4.0)
# weak:   간접 관련 가능 (식품/농업/일반) → neg_multiplier_weak (2.0)
NEGATIVE_KEYWORDS_STRONG: Dict[str, float] = {
    # 엔터테인먼트 / 비제조 콘텐츠 — 완전 범위 외
    "게임": 5, "웹툰": 5, "만화": 5, "영화": 5, "애니": 5,
    "캐릭터": 4, "축제": 4, "음악": 4, "공연": 4,
    "e스포츠": 5, "패션": 4, "뷰티": 4, "스포츠": 3,
    # 바이오/의료 — InterX 제조AI 완전 범위 외
    "바이오": 5, "신약": 6, "임상": 6, "의료기기": 5,
    "제약": 5, "유전체": 6, "세포치료": 6, "치유산업": 6,
    "청정바이오": 6,
    # 건설/토목 — 제조AI 범위 외
    "건설공사": 5, "건축": 4, "토목": 5, "도로공사": 5, "교량": 5,
    # 고용·일자리 (제조AI와 완전 무관)
    "일자리": 7, "고용장려": 6, "취업지원": 7, "구직": 5,
    "청년취업": 7, "청년일자리": 7, "고용보조금": 7,
    "사회적경제": 6, "협동조합": 5, "자활": 6,
    # 지역개발·도시재생
    "밀집지역": 7, "미니클러스터": 6, "도시재생": 5, "주거환경": 5,
    "마을기업": 6, "리빙랩": 6,
    # 금융·경제정책
    "한국은행": 7,
    # 이벤트/세미나/교육 (수주 대상 아님)
    "세미나": 7, "컨퍼런스": 6, "웨비나": 7,
    "참관단": 6, "참관객": 5, "수강생": 6,
    "사전등록": 5, "ir pitching": 5,
    "meet-up": 5, "meetup": 5, "biz meet": 5,
    "평가위원": 7, "평가위원회": 7, "심사위원": 7,  # 심사/평가위원 모집
    # 수요기업 모집 (InterX는 공급자)
    "수요기업": 12,
    # 비제조 패션
    "소잉": 7, "업사이클링": 6, "의류": 5,
    # ── v5.7: 비제조 산업 (테크노파크 공고 오탐 방지) ──
    # 해양/수산 — 제조AI 완전 범위 외
    "해양수산": 7, "해양": 5, "수산": 6, "수산물": 6, "어업": 6,
    "양식": 5, "수출시장개척단": 6, "국제수산": 6,
    # 에너지/탄소 — 제조AI 범위 외 (에너지 설비 제외)
    "탄소중립": 5, "탄소저감": 5, "re100": 5, "에너지전환": 5,
    "사용후배터리": 6, "전기차배터리": 5,
    # 농업/농촌 — 제조AI 범위 외
    "농촌": 5, "농업분야": 5, "농공단지": 5,
    # 우주/항공 (제조AI 범위 외)
    "우주대회": 7, "우주": 5, "항공우주": 5,
    # 지식산업센터/입주 — 임대사업
    "지식산업센터": 6, "입주기업모집": 6, "입주모집": 6,
    # 상장/IR/투자 — 금융사업
    "상장기업": 6, "ipo프로그램": 6, "스케일업": 4,
    # 화장품/뷰티
    "화장품": 5, "화장": 5, "코스메틱": 5,
}

NEGATIVE_KEYWORDS_MEDIUM: Dict[str, float] = {
    # 교육/인력 — 일부 제조 교육은 관련 가능
    "교육생모집": 6, "교육생 모집": 6, "데이터분석 교육": 6, "ai 교육": 4,
    "복지": 4, "돌봄": 5, "의료비": 5, "장학": 5,
    "인력양성": 4, "위탁운영": 5, "도약과정": 5,
    # 창업 생태계 — 제조 스타트업은 가끔 관련
    "소상공인": 6, "예비창업": 6, "창업보육": 6, "창업교육": 5,
    "입주기업": 4, "입주사": 4, "청년창업": 5,
    "ir피칭": 5, "창업경진": 5, "아이디어 공모": 5,
    "농촌창업": 6, "로컬푸드창업": 6,
    # 전시회/시찰/해외마케팅 — 파트너십 기회 가능
    "전시회": 4, "특별관": 5, "한국관": 5, "공동관": 4,
    "시찰단": 6, "창업가": 5, "육성과정": 5, "원데이": 4,
    "해외마케팅": 5, "판로개척": 5, "수출지원": 4,
    # 금융 — 기업 자금 지원은 간접 관련
    "금융지원": 4, "보증": 3, "대출": 4,
    "위기대응": 5, "경영위기": 5,
    "소셜벤처": 4,
    # 관광/여행
    "관광기업": 6, "여행지원": 5, "관광": 4,
    # SW 품질/테스팅 (제조AI 품질검사와 다름)
    "sw품질": 5, "sw테스팅": 5, "sw품질관리": 5, "sw서비스": 4,
    "컨설팅지원기관": 5,
}

NEGATIVE_KEYWORDS_WEAK: Dict[str, float] = {
    # 농업·식품 — 스마트팜/식품제조와 간접 관련 가능
    "농업": 4, "농식품": 5, "식품기업": 4, "농공단지": 4,
    # 일반 콘텐츠 — 제조 콘텐츠와 혼동 가능
    "전시": 3, "공모전": 3, "관광": 3,
    "문화": 2, "예술": 3, "방송": 3, "미디어": 2, "콘텐츠": 2,
}

# 하위 호환: 기존 NEGATIVE_KEYWORDS를 flat으로도 유지 (외부 참조용)
NEGATIVE_KEYWORDS: Dict[str, float] = {
    **NEGATIVE_KEYWORDS_STRONG,
    **NEGATIVE_KEYWORDS_MEDIUM,
    **NEGATIVE_KEYWORDS_WEAK,
}

# ── COMBO 키워드 그룹 (두 키워드가 동시에 존재할 때 추가 가점) ───────────────────
# scoring.yaml의 combo_keywords에서 로드됨 → _CFG["COMBO_KEYWORDS"]
# 아래는 YAML 로드 실패 시 fallback 기본값
_COMBO_KEYWORD_GROUPS_FALLBACK: List[tuple] = [
    # AI + 제조 결합 — 고가치 핵심 조합
    ("ai", "제조", 5),
    ("인공지능", "제조", 5),
    ("ai", "스마트공장", 5),
    ("ai", "스마트팩토리", 5),
    # AX / 자율제조 결합
    ("ax", "실증", 5),
    ("ax", "제조", 5),
    ("자율제조", "ai", 5),
    ("자율공장", "ai", 5),
    # 스마트공장 + 구축/보급
    ("스마트공장", "구축", 5),
    ("스마트공장", "보급", 4),
    ("스마트공장", "고도화", 4),
    ("스마트팩토리", "구축", 5),
    # 디지털트윈 + 제조/실증
    ("디지털트윈", "제조", 5),
    ("디지털트윈", "실증", 4),
    ("디지털 트윈", "제조", 5),
    # 바우처 + AI
    ("바우처", "ai", 4),
    ("바우처", "인공지능", 4),
    # 품질/검사 + AI
    ("품질", "ai", 4),
    ("품질", "인공지능", 4),
    ("검사", "ai", 4),
    ("비전검사", "ai", 5),
    # 예지보전 + 설비/센서
    ("예지보전", "설비", 4),
    ("예지보전", "ai", 5),
    ("이상탐지", "ai", 5),
    # 안전 + AI
    ("안전", "ai", 4),
    ("중대재해", "ai", 5),
    # R&D + 제조
    ("r&d", "제조", 3),
    ("기술개발", "ai", 4),
    ("기술개발", "제조", 3),
    # 데이터 + 제조
    ("데이터", "제조", 3),
    ("제조데이터", "ai", 5),
    # ── 추가 7쌍 (bizinfo_datalist.py 대비 보강) ─────────────────────────────
    # 상생형 + 선도모델 — 정부 핵심 정책 방향
    ("상생형", "선도모델", 8),
    ("상생형", "스마트공장", 6),
    # 공급망 + AI/디지털 — Catena-X / 데이터스페이스 공고
    ("공급망", "ai", 4),
    ("공급망", "디지털", 4),
    # 탄소중립 + 스마트공장 — ESG 연계 제조 공고
    ("탄소중립", "스마트공장", 5),
    # DX + 제조 — 제조DX 공고
    ("dx", "제조", 5),
    # 로봇 + AI — 지능형 로봇 제조 공고
    ("로봇", "ai", 4),
    # ── v3: 실제 수행 사업 기반 콤보 추가 ──
    # 자율운영/제어 계열
    ("자율운영", "제조", 6),
    ("자율제어", "ai", 6),
    ("자율가공", "ai", 6),
    # AI Agent 계열
    ("agent", "제조", 6),
    ("에이전트", "제조", 6),
    ("오케스트레이션", "agent", 5),
    ("오케스트레이션", "에이전트", 5),
    ("agent", "공정", 5),
    # 암묵지 + AI
    ("암묵지", "ai", 5),
    ("암묵지", "제조", 5),
    # 예지보전 + 밸류체인
    ("예지보전", "밸류체인", 5),
    ("예지보전", "철강", 4),
    # 뿌리 + AI
    ("뿌리", "ai", 5),
    ("뿌리", "로봇", 4),
    # 열공정 + 파운데이션
    ("열공정", "파운데이션", 5),
    # Closed-loop + 품질
    ("closed-loop", "품질", 5),
    ("closed-loop", "공정", 5),
    # 스케줄링 + AI
    ("스케줄링", "ai", 5),
    # 데이터표준화 + 제조
    ("데이터표준화", "제조", 4),
    ("표준화", "제조데이터", 4),
    # copilot + 공정/제조
    ("copilot", "공정", 5),
    ("copilot", "제조", 5),
    # PINN 물리모델
    ("pinn", "제조", 5),
    ("pinn", "공정", 5),
    # ── v3.1: 2026 신규 과제 기반 콤보 ──
    # 에이전틱AI 계열
    ("에이전틱", "ai", 6),
    ("에이전틱", "제조", 6),
    ("에이전틱", "실증", 5),
    ("agentic", "ai", 6),
    # 피지컬AI 계열
    ("피지컬", "ai", 6),
    ("피지컬", "제조", 5),
    ("피지컬", "응용제품", 6),
    # DTaaS
    ("dtaas", "제조", 6),
    ("dtaas", "클라우드", 5),
    # AI+X 융합
    ("ai", "융합", 4),
    ("인공지능", "융합", 4),
    # 자율공정 + AI
    ("자율공정", "ai", 6),
    ("자율공정", "제조", 5),
    # Multi AI Agent
    ("multi", "agent", 6),
    ("multi", "에이전트", 6),
    # AI 반도체/선박
    ("ai", "선박", 4),
    ("ai", "반도체", 4),
    # DX멘토 + 스마트공장
    ("dx멘토", "스마트공장", 5),
]

# ── 필수 신호 키워드 (가점 합이 낮을 때 최소 하나 있어야 통과) ──────────────────
_MIN_SIGNAL = {
    "ai", "인공지능", "제조", "실증", "자동화", "로봇", "품질", "안전",
    "데이터", "공정", "설비", "센서", "모니터링", "디지털트윈", "예지보전",
    "ai공장", "ai에이전트", "산업ai에이전트", "산업ai솔루션", "ai응용제품",
    "에이전틱", "피지컬ai", "dtaas", "자율공정", "엔드프로덕트",
}

# ── L3 제목 필수 키워드 (제목에 하나라도 있어야 L3 강공고 확정) ─────────────────
# body_text 오염(카테고리 목록 페이지 등)으로 인한 오탐 방지
_L3_TITLE_KEYWORDS = {
    "스마트공장", "스마트팩토리", "자율제조", "자율공장", "자율형공장",
    "자율형 공장", "제조ai", "제조 ai", "산업ai", "산업 ai",
    "제조인공지능", "디지털트윈", "디지털 트윈",
    "머신비전", "머신 비전", "비전검사", "비전 검사",
    "이상탐지", "이상 탐지", "예지보전",
    "공정최적화", "공정 최적화", "ai팩토리", "ai 팩토리",
    "ai공장", "ai 공장", "ax실증", "ax 실증",
    "산업ai에이전트", "산업ai솔루션", "ai응용제품",
    "제조dx", "제조 dx", "manufacturing-x",
    # 안전 솔루션 (Safety.AI)
    "중대재해", "제조안전", "산업안전",
    # v3: 실제 사업 기반 L3 제목 키워드
    "자율운영", "자율제어", "자율가공",
    "ax실증산단", "제조ax선도", "상생형 제조ax",
    "ai agent", "ai에이전트", "산업문제해결",
    "제조암묵지", "제조ai특화", "ai팩토리",
    "레전드50", "뿌리공장", "열공정파운데이션",
    "closed-loop", "ai-ot", "오케스트레이션",
    "밸류체인", "copilot", "코파일럿", "pinn",
    "제조안전고도화", "ax혁신", "ai네이티브",
}

# ── 제목 블랙리스트 — 제목에 포함 시 fitness/priority/grade 강제 D ────────────
# 이유: weight 기반 감점은 industry_score(솔루션 점수)를 상쇄하지 못함
# (예: InfraDS가 데이터/IoT 키워드만으로 industry=60 → priority ≥30 유지)
# 해결: 제목에 명확한 비조달 키워드가 있으면 priority/grade 강제 D
_TITLE_BLOCK_KEYWORDS = {
    "수요기업",   # 수요기업 모집 = InterX는 공급자, 대상 아님 (KEA IoT 등)
    "육성과정",   # 창업가/사업개발자 육성과정 = 교육 프로그램, 조달 대상 아님
    "시찰단",     # 해외 전시회 시찰단 모집 = 견학단체, 수주 대상 아님 (Hannover Messe 등)
}


# ═══════════════════════════════════════════════════════════════════════════════
#  v3 고도화 헬퍼 함수
# ═══════════════════════════════════════════════════════════════════════════════

# ── [고도화 2] 예산 구간 점수화 ──────────────────────────────────────────────
_BUDGET_RE = re.compile(r"(\d[\d,.]*)\s*(억|백만|만|천만)?")

def _parse_budget_score(budget_str: str) -> float:
    """예산 문자열을 파싱해 구간 점수 반환 (0~10)."""
    if not budget_str:
        return 0.0
    text = budget_str.replace(",", "").replace(" ", "")
    m = _BUDGET_RE.search(text)
    if not m:
        return 1.0  # 예산 필드 있지만 파싱 불가 → 최소 점수
    num = float(m.group(1))
    unit = m.group(2) or ""
    # 억 단위로 변환
    if unit == "억":
        eok = num
    elif unit == "천만":
        eok = num * 0.1
    elif unit == "백만":
        eok = num * 0.01
    elif unit == "만":
        eok = num * 0.0001
    else:
        # 단위 없으면 숫자 크기로 추정
        if num >= 100:
            eok = num * 0.0001  # 만원 단위로 추정 (ex: 50000 → 5억)
        elif num >= 1:
            eok = num  # 이미 억 단위
        else:
            eok = num
    # 구간별 점수
    if eok >= 50:
        return 10.0   # 50억 이상 (AI팩토리 급)
    elif eok >= 10:
        return 8.0    # 10~50억 (자율제조 대형)
    elif eok >= 5:
        return 6.0    # 5~10억
    elif eok >= 1:
        return 4.0    # 1~5억
    elif eok >= 0.5:
        return 2.0    # 5천만~1억
    else:
        return 1.0    # 5천만 미만


# ── [고도화 3] 공고 유형 분류 ────────────────────────────────────────────────
_TYPE_PATTERNS: Dict[str, List[str]] = {
    "실증": ["실증", "poc", "테스트베드", "시범", "파일럿", "상용화", "신속상용화"],
    "R&D": ["r&d", "r&bd", "기술개발", "연구개발", "과제", "핵심기술개발"],
    "구축": ["구축", "도입", "보급", "확산", "고도화", "지원사업"],
    "바우처": ["바우처", "구축지원", "도입지원"],
    "인력": ["교육", "인력양성", "교육생", "훈련", "육성", "멘토링"],
}
_TYPE_MULTIPLIER = {"실증": 1.25, "R&D": 1.15, "구축": 1.10, "바우처": 1.0, "인력": 0.5, "기타": 1.0}

def _classify_notice_type(title: str, summary: str = "") -> Tuple[str, float]:
    """공고 유형 분류 → (유형명, 배율)."""
    text = f"{title} {summary}".lower()
    best_type = "기타"
    best_count = 0
    for ntype, patterns in _TYPE_PATTERNS.items():
        count = sum(1 for p in patterns if p in text)
        if count > best_count:
            best_count = count
            best_type = ntype
    return best_type, _TYPE_MULTIPLIER.get(best_type, 1.0)


# ── [고도화 4] TF-IDF 코사인 유사도 ─────────────────────────────────────────
# InterX 솔루션 프로필 (브로슈어 핵심 텍스트)
_INTERX_PROFILE = (
    "디지털트윈 기반 자율제조 솔루션 Manufacturing DT 공정 시뮬레이션 "
    "Recipe AI 공정레시피 배합조건 최적화 발효 사출 열공정 "
    "Quality AI 품질 이상탐지 불량 수율 SPC 용접 도장 "
    "Inspection AI 비전검사 머신비전 외관검사 비전 AI "
    "Safety AI 제조안전 중대재해 산업안전 안전모니터링 "
    "GenAI 생성형AI LLM RAG 멀티모달 AI에이전트 파운데이션모델 "
    "데이터인프라 MES ERP PLC SCADA OT AAS 데이터스페이스 "
    "예지보전 설비 모니터링 이상탐지 센서 IoT 엣지AI "
    "스마트공장 스마트팩토리 자율형공장 AI팩토리 AX실증 "
    "자율운영 자율제어 자율가공 암묵지 밸류체인 오케스트레이션 "
    "AI Agent 산업AI에이전트 산업AI솔루션 AI응용제품 신속상용화 "
    "제조AI특화 제조DX Manufacturing-X Closed-loop PINN Copilot "
    "뿌리산업 뿌리공장 데이터표준화 참조모델 열공정파운데이션 "
    "로봇 협동로봇 4족보행 조선해양 배관안전 제조안전고도화"
)
_tfidf_vectorizer = None
_interx_vector = None

def _calc_tfidf_similarity(text: str) -> float:
    """InterX 프로필과의 TF-IDF 코사인 유사도 (0~1)."""
    global _tfidf_vectorizer, _interx_vector
    if not text or len(text.strip()) < 10:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        if _tfidf_vectorizer is None:
            _tfidf_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            both = _tfidf_vectorizer.fit_transform([_INTERX_PROFILE, text])
            _interx_vector = both[0]
            return float(cosine_similarity(both[0], both[1])[0][0])
        else:
            # 이미 fit된 vectorizer 사용
            notice_vec = _tfidf_vectorizer.transform([text])
            return float(cosine_similarity(_interx_vector, notice_vec)[0][0])
    except ImportError:
        log.debug("scikit-learn 미설치 — TF-IDF 유사도 비활성")
        return 0.0
    except Exception as e:
        log.debug("TF-IDF 유사도 계산 실패: %s", e)
        return 0.0


# ── [고도화 5] 키워드 밀도 ───────────────────────────────────────────────────
def _calc_keyword_density(text: str, hit_count: int) -> float:
    """키워드 밀도 = 히트 수 / 전체 단어 수 (0~1 클램핑)."""
    if not text:
        return 0.0
    word_count = len(text.split())
    if word_count == 0:
        return 0.0
    return min(1.0, hit_count / max(word_count, 1))


# ── [고도화 6] 긴급도 × 등급 교차 부스트 ────────────────────────────────────
def _calc_urgency_boost(grade: str, deadline_str: str) -> float:
    """A/B등급 + 마감 임박 → 우선순위 부스트."""
    if not deadline_str:
        return 0.0
    try:
        dday = (datetime.strptime(deadline_str, "%Y-%m-%d").date() - date.today()).days
    except (ValueError, TypeError):
        return 0.0
    if dday < 0:
        return 0.0  # 이미 마감
    # 등급별 부스트 배율
    grade_mult = {"A": 1.15, "B": 1.08, "C": 1.03, "D": 1.0}
    mult = grade_mult.get(grade, 1.0)
    # 긴급도에 따른 부스트
    if dday <= 3:
        return (mult - 1.0) * 100 * 1.5   # A등급+D-3 → +22.5점
    elif dday <= 7:
        return (mult - 1.0) * 100          # A등급+D-7 → +15점
    elif dday <= 14:
        return (mult - 1.0) * 100 * 0.5   # A등급+D-14 → +7.5점
    return 0.0


# ── [고도화 1] 위치별 키워드 점수 계산 ──────────────────────────────────────
def _score_by_position(kw: str, weight: float,
                        title: str, summary: str,
                        core_text: str, body: str) -> float:
    """키워드가 어디에서 매칭됐는지에 따라 차등 점수."""
    score = 0.0
    if kw in title:
        score = weight * 3.0     # 제목 매칭: ×3
    elif kw in summary:
        score = weight * 1.5     # 요약 매칭: ×1.5
    elif kw in core_text:
        score = weight * 1.2     # 구조화 데이터: ×1.2
    elif kw in body:
        score = weight * 0.5     # 본문: ×0.5
    return score


class PriorityScoringPolicy:
    """
    가점/감점 키워드, 솔루션 맵, structured 보너스를 종합해
    fitness(적합도), priority(우선순위), 솔루션별 점수를 계산한다.
    notice.l3_strong / partner_candidate / recommended_solution / recommended_action
    도 이 메서드 안에서 직접 설정한다.
    """

    def calculate(self, notice: Notice) -> ScoreCard:
        # ── 텍스트 준비 ──────────────────────────────────────────────────────
        title_text = notice.title.lower()
        summary_text = f"{notice.summary} {notice.business_type}".lower()
        core_text  = ""
        if notice.structured:
            core_text = (
                notice.structured.get("사업목적", "") + " " +
                notice.structured.get("지원내용", "")
            ).lower()
        body = notice.body_text.lower() if notice.body_text else ""

        # scored_text (하위 호환용), full_text (core 체크용)
        scored_text = f"{title_text} {summary_text} {core_text}"
        full_text   = f"{scored_text} {body}"

        # ── 코어 키워드 존재 여부 ─────────────────────────────────────────────
        core_found = any(kw in full_text for kw in CORE_KEYWORDS)

        # ══ [고도화 1] 위치 가중치 기반 가점 계산 ════════════════════════════
        pos_hits: List[str] = []
        pos_score = 0.0
        for kw, w in POSITIVE_KEYWORDS.items():
            s = _score_by_position(kw, w, title_text, summary_text, core_text, body)
            if s > 0:
                pos_hits.append(kw)
                pos_score += s

        # ── COMBO 보너스 (scored_text + body 모두 체크) ─────────────────────
        combo_bonus = 0.0
        combo_hits: List[str] = []
        for kw_a, kw_b, bonus in COMBO_KEYWORD_GROUPS:
            if kw_a in full_text and kw_b in full_text:
                combo_bonus += bonus
                combo_hits.append(f"{kw_a}+{kw_b}")

        # ── 감점 계산 3단계 (scored_text 기준 — body 제외) ─────────────────
        neg_hits: List[str] = []
        neg_score = 0.0
        for kw, w in NEGATIVE_KEYWORDS_STRONG.items():
            if kw in scored_text:
                neg_hits.append(kw)
                neg_score += w * (_CFG["NEG_MULT_STRONG"] / _CFG["NEG_MULT"])
        for kw, w in NEGATIVE_KEYWORDS_MEDIUM.items():
            if kw in scored_text:
                neg_hits.append(kw)
                neg_score += w * (_CFG["NEG_MULT_MEDIUM"] / _CFG["NEG_MULT"])
        for kw, w in NEGATIVE_KEYWORDS_WEAK.items():
            if kw in scored_text:
                neg_hits.append(kw)
                neg_score += w * (_CFG["NEG_MULT_WEAK"] / _CFG["NEG_MULT"])

        # ── 구조화 데이터 보너스 ───────────────────────────────────────────
        struct_bonus = 0.0
        for kw, w in POSITIVE_KEYWORDS.items():
            if kw in core_text:
                struct_bonus += w * _CFG["STRUCT_BONUS"]

        # ══ [고도화 2] 예산 구간 점수화 ══════════════════════════════════════
        budget_score = _parse_budget_score(notice.budget or "")
        # 예산 보너스: 기존 +3 고정 → 구간별 0~10
        budget_bonus = budget_score

        # ══ [고도화 3] 공고 유형 분류 ════════════════════════════════════════
        notice_type, type_mult = _classify_notice_type(notice.title, notice.summary)

        # ── 적합도(fitness) 계산 ──────────────────────────────────────────────
        if not core_found:
            raw_fit = 0.0
        elif pos_score <= 3.0 and not any(kw in scored_text for kw in _MIN_SIGNAL):
            raw_fit = 0.0
        else:
            raw_fit = (
                pos_score                               # 위치 가중치 적용된 가점
                - (neg_score * _CFG["NEG_MULT"])        # 감점
                + struct_bonus                           # 구조화 보너스
                + combo_bonus                            # 콤보 보너스
                + budget_bonus                           # 예산 구간 보너스
            )
            # [고도화 3] 유형별 배율 적용
            raw_fit *= type_mult

        fitness = round(max(0.0, min(100.0, raw_fit)), 1)

        # ── 솔루션별 점수 (위치 가중치 적용) ─────────────────────────────────
        sol_scores: Dict[str, float] = {}
        scale = _CFG["SCALE"]
        for sol, kws in SOLUTION_MAP.items():
            s = 0.0
            for kw, w in kws.items():
                s += _score_by_position(kw, w, title_text, summary_text, core_text, body)
            sol_scores[sol] = round(min(100.0, s * scale), 1) if core_found else 0.0

        # ── 산업 점수 & 우선순위 ──────────────────────────────────────────────
        _nonzero = [v for v in sol_scores.values() if v > 0]
        industry_score = round(
            sum(_nonzero) / max(len(_nonzero), 1), 1
        ) if _nonzero else 0.0

        # ══ [고도화 4] TF-IDF 유사도 보너스 ══════════════════════════════════
        tfidf_sim = _calc_tfidf_similarity(scored_text)
        # 유사도 0.3+ → 최대 +15점 보너스 (fitness에 직접 추가)
        tfidf_bonus = max(0, (tfidf_sim - 0.2)) * 50  # 0.2~1.0 → 0~40, cap 15
        tfidf_bonus = min(15.0, tfidf_bonus)
        if core_found and fitness > 0:
            fitness = round(min(100.0, fitness + tfidf_bonus), 1)

        # ══ [고도화 5] 키워드 밀도 보너스 ════════════════════════════════════
        kw_density = _calc_keyword_density(scored_text, len(pos_hits))
        # 밀도 0.1+ → 최대 +8점 (밀도 높은 = 핵심 공고)
        density_bonus = min(8.0, kw_density * 80)
        if core_found and fitness > 0:
            fitness = round(min(100.0, fitness + density_bonus), 1)

        # ── priority 계산 ────────────────────────────────────────────────────
        priority = round(fitness * _CFG["W_FIT"] + industry_score * _CFG["W_IND"], 1)

        # fitness=0 → priority 강제 0
        if fitness == 0.0:
            priority = 0.0

        grade = (
            "A" if priority >= _CFG["GRADE_A"] else
            "B" if priority >= _CFG["GRADE_B"] else
            "C" if priority >= _CFG["GRADE_C"] else "D"
        )

        # ── 제목 블랙리스트 강제 차단 ─────────────────────────────────────────
        if any(kw in title_text for kw in _TITLE_BLOCK_KEYWORDS):
            fitness = 0.0
            priority = 0.0
            grade = "D"
            log.debug("제목 블랙리스트 강제 차단: %s", notice.title[:40])

        # ══ [고도화 6] 긴급도 × 등급 교차 부스트 ═════════════════════════════
        urgency_boost = _calc_urgency_boost(grade, notice.deadline_date or "")
        if urgency_boost > 0:
            priority = round(min(100.0, priority + urgency_boost), 1)
            # 부스트로 등급 상승 가능
            grade = (
                "A" if priority >= _CFG["GRADE_A"] else
                "B" if priority >= _CFG["GRADE_B"] else
                "C" if priority >= _CFG["GRADE_C"] else "D"
            )

        # ── 본문 없는 A등급 → B등급 하향 (제목만으로 A등급은 신뢰도 부족) ────
        if grade == "A" and (not notice.body_text or len(notice.body_text.strip()) < 50):
            grade = "B"
            log.debug("본문 부실 A→B 하향: %s", notice.title[:40])

        # ── L3 강공고 판정 ───────────────────────────────────────────────────
        title_has_l3 = any(kw in title_text for kw in _L3_TITLE_KEYWORDS)
        is_l3 = (fitness >= L3_THRESHOLD) and title_has_l3

        # ── notice 필드 직접 설정 ────────────────────────────────────────────
        top3 = sorted(sol_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        notice.recommended_solution = " / ".join(s for s, v in top3 if v > 0) or "-"
        notice.recommended_action   = "제안 검토" if is_l3 else "모니터링"
        notice.l3_strong            = "Y" if is_l3 else "N"
        notice.partner_candidate    = (
            "Y" if (priority >= PARTNER_THRESHOLD and not is_l3) else "N"
        )

        return ScoreCard(
            execution_id=notice.execution_id,
            notice_id=notice.notice_id,
            site=notice.site,
            fitness_score=fitness,
            priority_score=priority,
            priority_grade=grade,
            solution_scores=sol_scores,
            positive_keywords=pos_hits[:15],    # v3: 10→15개
            negative_keywords=neg_hits[:5],
            industry_score=industry_score,
            # v3 신규 필드
            keyword_density=round(kw_density, 4),
            budget_score=budget_score,
            notice_type=notice_type,
            type_multiplier=type_mult,
            tfidf_similarity=round(tfidf_sim, 4),
            urgency_boost=round(urgency_boost, 1),
            combo_keywords=combo_hits[:10],
        )
