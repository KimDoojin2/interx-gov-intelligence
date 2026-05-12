from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.scoring")

# ── 기본 임계값 (scoring.yaml 로드 실패 시 fallback) ──────────────────────────
_L3_DEFAULT      = 35
_PARTNER_DEFAULT = 20
_GRADE_A         = 55
_GRADE_B         = 40
_GRADE_C         = 25
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
            return {
                "L3_THRESHOLD":      t.get("l3_strong",        _L3_DEFAULT),
                "PARTNER_THRESHOLD": t.get("partner_candidate", _PARTNER_DEFAULT),
                "GRADE_A":           t.get("grade_a",          _GRADE_A),
                "GRADE_B":           t.get("grade_b",          _GRADE_B),
                "GRADE_C":           t.get("grade_c",          _GRADE_C),
                "NEG_MULT":          t.get("neg_multiplier",   _NEG_MULT),
                "POS_MULT":          t.get("pos_multiplier",   _POS_MULT),
                "STRUCT_BONUS":      t.get("struct_bonus_factor", _STRUCT_BONUS),
                "BUDGET_BONUS":      t.get("budget_bonus",     _BUDGET_BONUS),
                "SCALE":             sol.get("scale_factor",   _SCALE),
                "W_FIT":             pf.get("w_fitness",       _W_FIT),
                "W_IND":             pf.get("w_industry",      _W_IND),
            }
        except Exception as e:
            log.warning("scoring.yaml 로드 실패 (%s): %s — fallback 기본값 사용", p, e)
            continue
    return {
        "L3_THRESHOLD": _L3_DEFAULT, "PARTNER_THRESHOLD": _PARTNER_DEFAULT,
        "GRADE_A": _GRADE_A, "GRADE_B": _GRADE_B, "GRADE_C": _GRADE_C,
        "NEG_MULT": _NEG_MULT, "POS_MULT": _POS_MULT,
        "STRUCT_BONUS": _STRUCT_BONUS, "BUDGET_BONUS": _BUDGET_BONUS,
        "SCALE": _SCALE, "W_FIT": _W_FIT, "W_IND": _W_IND,
    }


_CFG = _load_thresholds()
L3_THRESHOLD      = _CFG["L3_THRESHOLD"]
PARTNER_THRESHOLD = _CFG["PARTNER_THRESHOLD"]

# ── 제조/AI 필수 코어 키워드 (하나도 없으면 0점) ──────────────────────────────
CORE_KEYWORDS = {
    "제조", "스마트공장", "스마트팩토리", "디지털트윈", "디지털 트윈", "예지보전",
    "산업ai", "산업 ai", "제조ai", "제조 ai", "공정", "설비", "머신비전", "머신 비전",
    "자율제조", "자율공장", "자율형공장", "aas",
    "ax", "ai", "인공지능", "데이터", "실증", "자동화", "iot", "센서",
    "로봇", "품질", "안전", "클라우드", "플랫폼", "poc",
    # 신규 추가
    "ai공장", "ai 공장", "산업ai에이전트", "산업ai솔루션",
    "ai응용제품", "ai 응용제품", "제조dx", "학습데이터",
}

# ── 솔루션별 키워드 가중치 맵 ─────────────────────────────────────────────────
SOLUTION_MAP: Dict[str, Dict[str, float]] = {
    "ManufacturingDT": {
        "디지털트윈": 4, "디지털 트윈": 4, "시뮬레이션": 3, "공정": 2,
        "스마트팩토리": 3, "스마트공장": 3,
        "자율형공장": 4, "자율형 공장": 4, "자율제조": 4, "자율공장": 4,
        "manufacturing-x": 4, "ai팩토리": 4, "ai 팩토리": 4,
        "ai공장": 4, "ai 공장": 4,        # [신규]
        "디지털협업공장": 3, "ax실증": 4, "ax 실증": 4,
        "피지컬ai": 3, "클라우드제조": 3, "공동제조소": 3,
        "제조dx": 3, "제조 dx": 3,        # [신규]
    },
    "RecipeAI": {
        "레시피": 4, "공정레시피": 4, "배합": 3, "조건최적화": 3,
        "공정최적화": 3, "공정 최적화": 3,
        "발효공정": 4, "사출공정": 3, "열공정": 3,
        "파운데이션모델": 2, "파운데이션 모델": 2,
    },
    "QualityAI": {
        "품질": 3, "불량": 3, "수율": 3,
        "이상탐지": 4, "이상 탐지": 4,
        "spc": 3, "제조안전": 2, "용접": 2, "용접ai": 4, "용접 ai": 4, "도장": 2,
        "quality.ai": 5,
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
    },
    "GenAI": {
        "생성형ai": 4, "생성형 ai": 4, "llm": 4, "rag": 4, "gpt": 3,
        "멀티모달": 4, "ai에이전트": 4, "ai agent": 4,
        "파운데이션모델": 4, "파운데이션 모델": 4,
        "인공지능": 2, "제조인공지능": 4,
        # [신규] AI 에이전트·응용제품 공고 핵심어
        "산업ai에이전트": 5, "산업 ai에이전트": 5,
        "산업ai솔루션": 4, "산업 ai솔루션": 4,
        "ai응용제품": 4, "ai 응용제품": 4,
        "경량화": 3, "학습데이터": 3,
    },
    "InfraDS": {
        "데이터": 2, "api": 2, "mes": 3, "erp": 3, "plm": 2, "scm": 2,
        "ot": 3, "plc": 3, "scada": 3, "플랫폼": 2, "제조데이터": 3,
        "dpp": 3, "manufacturing-x": 3, "스마트제조혁신": 3,
        "aas": 4, "catena-x": 4, "데이터스페이스": 3,
        # [신규]
        "gpu": 3, "학습데이터": 3, "학습 데이터": 3,
        "제조dx": 3, "제조 dx": 3, "솔루션실증": 3,
    },
    "PdM": {
        "예지보전": 4, "설비": 3, "모니터링": 3,
        "이상탐지": 3, "이상 탐지": 3, "iiot": 3,
        "센서": 3, "스마트센서": 4,
        "엣지ai": 3, "엣지 ai": 3, "온디바이스": 3, "온디바이스 ai": 3,
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
}

# ── 감점 키워드 ───────────────────────────────────────────────────────────────
NEGATIVE_KEYWORDS: Dict[str, float] = {
    # 엔터테인먼트 / 비제조 콘텐츠
    "게임": 5, "웹툰": 5, "만화": 5, "영화": 5, "애니": 5,
    "캐릭터": 4, "축제": 4, "전시": 3, "음악": 4, "공연": 4,
    "e스포츠": 5, "공모전": 3, "관광": 3, "패션": 4, "뷰티": 4,
    "스포츠": 3, "문화": 2, "예술": 3, "방송": 3, "미디어": 2, "콘텐츠": 2,
    # 고용·일자리·창업 지원 (제조AI와 무관)
    "일자리": 7, "고용장려": 6, "취업지원": 7, "구직": 5,
    "청년취업": 7, "청년일자리": 7, "고용보조금": 7,
    "사회적경제": 6, "협동조합": 5, "자활": 6,
    # 창업 생태계 지원 (스타트업/보육/소상공인 — 제조AI 납품 대상 아님)
    "소상공인": 6, "예비창업": 6, "창업보육": 6, "창업교육": 5,
    "입주기업": 4, "입주사": 4,
    "ir피칭": 5, "창업경진": 5, "아이디어 공모": 5,
    "농촌창업": 6, "로컬푸드창업": 6,
    # 지역개발·도시재생
    "밀집지역": 7, "미니클러스터": 6, "도시재생": 5, "주거환경": 5,
    "마을기업": 6, "소셜벤처": 4,
    # 금융·경제정책
    "한국은행": 7, "금융지원": 4, "보증": 3, "대출": 4,
    "위기대응": 5, "경영위기": 5,
    # 보건·복지·교육
    "복지": 4, "돌봄": 5, "의료비": 5, "장학": 5, "교육생모집": 6, "교육생 모집": 6,
    # 비제조 산업 (패션·관광·농업·에너지·바이오 전용)
    "소잉": 7, "업사이클링": 6, "의류": 5,
    "관광기업": 6, "여행지원": 5, "농공단지": 4,
    # 이벤트·세미나 (공고가 아닌 참가 모집 — 수주 대상 아님)
    "세미나": 7, "컨퍼런스": 6, "웨비나": 7,
    "참관단": 6, "참관객": 5, "수강생": 6,
    "사전등록": 5, "ir pitching": 5, "전시회": 4,
    "특별관": 5, "meet-up": 5, "meetup": 5, "biz meet": 5,
    "한국관": 5, "공동관": 4,
    # 해외 전시회 시찰단 / 교육 행사 (수주 대상 아님)
    "시찰단": 6, "창업가": 5, "육성과정": 5,
    "원데이": 4,  # 원데이 교육/세미나 이벤트 (ex: 디지털 트윈 원데이 기본 교육)
    # 수요기업 모집 (InterX는 공급자 — 수요기업 모집 공고는 대상 아님)
    "수요기업": 12,  # 5→8→12: penalty=72로 상향 (IoT/데이터 positive 점수 상쇄)
    # 농업·식품 분야 (InterX 제조AI 범위 외)
    "농업": 4, "농식품": 5, "식품기업": 4,
    # 비제조 교육 프로그램
    "데이터분석 교육": 6, "ai 교육": 4,
}

# ── 필수 신호 키워드 (가점 합이 낮을 때 최소 하나 있어야 통과) ──────────────────
_MIN_SIGNAL = {
    "ai", "인공지능", "제조", "실증", "자동화", "로봇", "품질", "안전",
    "데이터", "공정", "설비", "센서", "모니터링", "디지털트윈", "예지보전",
    "ai공장", "ai에이전트", "산업ai에이전트", "산업ai솔루션", "ai응용제품",
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
        base_text  = f"{notice.title} {notice.summary} {notice.business_type}".lower()
        core_text  = ""
        if notice.structured:
            core_text = (
                notice.structured.get("사업목적", "") + " " +
                notice.structured.get("지원내용", "")
            ).lower()
        body = notice.body_text.lower() if notice.body_text else ""

        # scored_text: 제목+요약+구조화 데이터만 — body_text 제외
        # (gjtp 등 카테고리 목록 페이지를 detail_url 로 사용하는 사이트의
        #  body_text 오염으로 인한 점수 과대평가 방지)
        scored_text = f"{base_text} {core_text}"
        # full_text: core_found 체크에만 사용 (body 포함)
        full_text   = f"{base_text} {core_text} {body}"

        # ── 코어 키워드 존재 여부 ─────────────────────────────────────────────
        core_found = any(kw in full_text for kw in CORE_KEYWORDS)

        # ── 가점 계산 (scored_text 기준) ──────────────────────────────────────
        pos_hits: List[str] = []
        pos_score = 0.0
        for kw, w in POSITIVE_KEYWORDS.items():
            if kw in scored_text:
                pos_hits.append(kw)
                pos_score += w

        # ── 감점 계산 (scored_text 기준 — 제목/요약에 명확히 비제조 주제인 경우) ──
        neg_hits: List[str] = []
        neg_score = 0.0
        for kw, w in NEGATIVE_KEYWORDS.items():
            if kw in scored_text:
                neg_hits.append(kw)
                neg_score += w

        # ── 구조화 데이터 보너스 (사업목적/지원내용에 히트하면 1.5배) ───────────
        struct_bonus = 0.0
        for kw, w in POSITIVE_KEYWORDS.items():
            if kw in core_text:
                struct_bonus += w * _CFG["STRUCT_BONUS"]
        if notice.budget:
            struct_bonus += _CFG["BUDGET_BONUS"]

        # ── 적합도(fitness) 계산 ──────────────────────────────────────────────
        if not core_found:
            raw_fit = 0.0
        elif pos_score <= 3.0 and not any(kw in scored_text for kw in _MIN_SIGNAL):
            raw_fit = 0.0
        else:
            raw_fit = (pos_score * _CFG["POS_MULT"]) - (neg_score * _CFG["NEG_MULT"]) + struct_bonus

        fitness = round(max(0.0, min(100.0, raw_fit)), 1)

        # ── 솔루션별 점수 (scored_text 기준) ─────────────────────────────────
        sol_scores: Dict[str, float] = {}
        scale = _CFG["SCALE"]
        for sol, kws in SOLUTION_MAP.items():
            s = sum(
                w * (_CFG["STRUCT_BONUS"] if kw in core_text else 1.0)
                for kw, w in kws.items()
                if kw in scored_text
            )
            sol_scores[sol] = round(min(100.0, s * scale), 1) if core_found else 0.0

        # ── 산업 점수 & 우선순위 ──────────────────────────────────────────────
        # 0점 솔루션 제외 후 평균 — body_text 제외 이후 점수 희석 보정
        # 예: ManufacturingDT=45, 나머지=0 → 45/7=6.4(X) → 45/1=45(O)
        _nonzero = [v for v in sol_scores.values() if v > 0]
        industry_score = round(
            sum(_nonzero) / max(len(_nonzero), 1), 1
        ) if _nonzero else 0.0
        priority = round(fitness * _CFG["W_FIT"] + industry_score * _CFG["W_IND"], 1)

        # ── fitness=0 이면 industry_score 기여 차단 ──────────────────────────────
        # industry_score는 제조 관련 공고를 부스트하기 위한 설계이므로,
        # 감점 키워드로 인해 fitness=0이 된 공고가 industry_score×W_IND 만으로
        # B등급(≥30)에 진입하는 것을 방지 (fitness=0 → priority 강제 0)
        if fitness == 0.0:
            priority = 0.0

        grade = (
            "A" if priority >= _CFG["GRADE_A"] else
            "B" if priority >= _CFG["GRADE_B"] else
            "C" if priority >= _CFG["GRADE_C"] else "D"
        )

        # ── 제목 블랙리스트 강제 차단 ─────────────────────────────────────────
        # 가중치 기반 감점은 industry_score(솔루션 점수)를 상쇄하지 못하므로
        # 제목에 블랙리스트 키워드가 있으면 fitness/priority/grade를 강제로 D로 내림
        if any(kw in title_text for kw in _TITLE_BLOCK_KEYWORDS):
            fitness = 0.0
            priority = 0.0
            grade = "D"
            log.debug("제목 블랙리스트 강제 차단: %s (hit=%s)",
                      notice.title[:40],
                      [kw for kw in _TITLE_BLOCK_KEYWORDS if kw in title_text])

        # ── L3 강공고 판정: fitness 임계값 + 제목에 핵심 L3 키워드 필수 ─────────
        # body_text 오염 방지: 제목에 L3 키워드가 없으면 L3 아님
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
            positive_keywords=pos_hits[:10],
            negative_keywords=neg_hits[:5],
            industry_score=industry_score,
        )
