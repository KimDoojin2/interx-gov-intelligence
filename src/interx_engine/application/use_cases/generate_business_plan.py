"""
사업계획서 AI 자동 생성기 — 공고 맞춤형 DOCX 출력 (하이브리드).

두 가지 모드 지원:
  MODE 1 (양식 업로드): HWP/HWPX/PDF 양식 → 섹션 추출 → AI가 내용 채움
  MODE 2 (공고 분석):   공고 본문에서 요구사항/목차 → AI가 구조+내용 생성

핵심 원칙:
  - 사업마다 성격이 다르므로, 고정 템플릿 대신 공고별 동적 구조 생성
  - 비용/예산/금액 정보는 절대 포함하지 않음
  - Gemini 2.0 Flash 무료 API (15 RPM)
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.business_plan")


# ═════════════════════════════════════════════════════════════════════════════
#  InterX 솔루션 역량 DB
# ═════════════════════════════════════════════════════════════════════════════

INTERX_CAPABILITIES = {
    "ManufacturingDT": {
        "name": "제조 디지털트윈",
        "desc": "실시간 공정 시뮬레이션 및 최적화 플랫폼",
        "keywords": ["디지털트윈", "시뮬레이션", "가상공장", "DT", "Digital Twin"],
        "tech": "Unity 3D / OPC-UA / MQTT / Azure IoT",
        "strengths": [
            "3D 공정 시뮬레이션 기반 디지털트윈 플랫폼 구축 경험",
            "실시간 센서 데이터 수집 → 가상 공장 동기화 기술",
            "공정 변경 시나리오 사전 시뮬레이션으로 리스크 최소화",
        ],
    },
    "RecipeAI": {
        "name": "레시피 AI",
        "desc": "공정 조건 최적화 및 배합 예측 AI",
        "keywords": ["레시피", "공정최적화", "배합", "파라미터"],
        "tech": "XGBoost / LSTM / Bayesian Optimization / MLOps",
        "strengths": [
            "다변량 공정 파라미터 최적화 AI 모델 개발 경험",
            "레시피 자동 추천 및 품질 예측 정확도 95%+",
            "실시간 공정 조건 피드백 루프 구현",
        ],
    },
    "QualityAI": {
        "name": "품질 AI",
        "desc": "불량 검출 및 품질 예측 시스템 (정확도 99%+)",
        "keywords": ["불량검출", "품질예측", "SPC", "품질관리", "품질"],
        "tech": "CNN / YOLO / Anomaly Detection / Edge AI",
        "strengths": [
            "제조 불량 자동 검출 AI (정확도 99%+)",
            "SPC 통계적 공정 관리 자동화",
            "품질 이상 조기 경보 시스템 구축",
        ],
    },
    "InspectionAI": {
        "name": "비전 검사 AI",
        "desc": "머신비전 기반 자동 외관 검사 (미세결함 0.1mm 탐지)",
        "keywords": ["비전검사", "외관검사", "머신비전", "비전", "검사"],
        "tech": "YOLO v8 / Detectron2 / OpenCV / GigE Vision",
        "strengths": [
            "멀티 카메라 비전 검사 시스템 구축 경험 다수",
            "미세 결함(0.1mm 이하) 탐지 딥러닝 모델",
            "라인 속도 대응 실시간 검사 (100ms 이내 판정)",
        ],
    },
    "SafetyAI": {
        "name": "안전 AI",
        "desc": "중대재해 예방 및 작업자 안전 모니터링",
        "keywords": ["안전", "중대재해", "재해예방", "안전관리"],
        "tech": "Pose Estimation / Object Detection / IoT Gateway",
        "strengths": [
            "중대재해처벌법 대응 AI 안전 관리 솔루션",
            "CCTV 기반 위험 행동 실시간 탐지",
            "IoT 센서 연계 위험 환경 자동 경보",
        ],
    },
    "GenAI": {
        "name": "제조 GenAI / AI Agent",
        "desc": "생성형 AI 기반 제조 지식 자동화 및 AI 에이전트",
        "keywords": ["생성형AI", "LLM", "챗봇", "RAG", "자연어", "Agent", "에이전트", "Copilot"],
        "tech": "LLM / LangChain / RAG / Vector DB / ReAct",
        "strengths": [
            "제조 도메인 특화 LLM/RAG 시스템 구축",
            "Agentic AI 기반 자율 작업 지원 시스템 개발 경험",
            "설비 매뉴얼 자동 QA 챗봇 및 공정 보고서 자동 생성",
        ],
    },
    "PdM": {
        "name": "예지보전",
        "desc": "설비 고장 예측 및 최적 정비 (정확도 90%+)",
        "keywords": ["예지보전", "고장예측", "RUL", "설비진단", "PHM", "보전"],
        "tech": "LSTM / Transformer / PHM / Edge Computing",
        "strengths": [
            "진동/온도/전류 데이터 기반 고장 예측 모델",
            "설비 잔여 수명(RUL) 예측 정확도 90%+",
            "정비 비용 30%+ 절감 실적",
        ],
    },
    "InfraDS": {
        "name": "데이터 인프라",
        "desc": "제조 데이터 스페이스 및 클라우드 인프라",
        "keywords": ["데이터", "인프라", "클라우드", "플랫폼", "MES", "ERP"],
        "tech": "Catena-X / K8s / Kafka / MinIO",
        "strengths": [
            "Catena-X / AAS 기반 데이터 스페이스 구축 경험",
            "제조 데이터 레이크 설계 및 ETL 파이프라인",
            "클라우드-엣지 하이브리드 아키텍처",
        ],
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  Step 1: 공고 본문에서 요구 섹션 구조 추출 (AI 기반)
# ═════════════════════════════════════════════════════════════════════════════

def extract_sections_from_notice(notice: Notice) -> List[Dict]:
    """
    공고 본문을 분석하여 사업계획서 요구 섹션 구조를 추출한다.
    Gemini가 본문에서 '사업계획서 작성 요령', '제출 서류', '양식' 등을 찾아
    목차 구조를 JSON으로 반환.

    Returns:
        [{"title": "1. 사업개요", "subsections": ["1.1 목적", ...], "guidance": "..."}, ...]
    """
    text = _prepare_notice_text(notice)
    if not text or len(text) < 50:
        return _default_sections(notice)

    try:
        from interx_engine.infrastructure.ai.gemini_client import generate, is_available
        if not is_available():
            return _default_sections(notice)
    except ImportError:
        return _default_sections(notice)

    system = (
        "당신은 한국 정부지원사업 전문가입니다. "
        "아래 공고 본문을 분석하여, 이 사업의 사업계획서에 들어가야 할 "
        "섹션 구조(목차)를 추출하세요.\n\n"
        "반드시 JSON 배열로만 응답하세요. 다른 텍스트 없이.\n"
        "형식:\n"
        '[{"title":"1. 섹션제목","subsections":["1.1 소제목","1.2 소제목"],"guidance":"이 섹션에서 요구하는 내용 설명"}]\n\n'
        "규칙:\n"
        "- 공고에서 명시적으로 요구하는 항목을 최우선으로 추출\n"
        "- 공고에 양식/목차가 없으면, 사업 성격에 맞는 표준 구조를 생성\n"
        "- 비용/예산/사업비 관련 섹션은 제외\n"
        "- 5~8개 대섹션이 적절\n"
    )

    prompt = f"[공고 정보]\n제목: {notice.title}\n기관: {notice.agency or '-'}\n\n[본문]\n{text[:4000]}"

    try:
        raw = generate(prompt=prompt, system_instruction=system,
                       temperature=0.3, max_tokens=2048, timeout=40)
        sections = _parse_sections_json(raw)
        if sections:
            log.info("[BusinessPlan] 공고 분석 → %d개 섹션 추출", len(sections))
            return sections
    except Exception as e:
        log.warning("[BusinessPlan] 섹션 추출 실패: %s", e)

    return _default_sections(notice)


def extract_sections_from_template(template_text: str, notice_title: str = "") -> List[Dict]:
    """
    업로드된 양식 텍스트에서 섹션 구조를 추출한다.
    """
    if not template_text or len(template_text) < 30:
        return []

    try:
        from interx_engine.infrastructure.ai.gemini_client import generate, is_available
        if not is_available():
            return _parse_sections_regex(template_text)
    except ImportError:
        return _parse_sections_regex(template_text)

    system = (
        "당신은 한국 정부지원사업 사업계획서 양식 분석 전문가입니다. "
        "아래 텍스트는 사업계획서 양식입니다. "
        "이 양식의 섹션 구조(목차)를 추출하세요.\n\n"
        "반드시 JSON 배열로만 응답하세요.\n"
        '[{"title":"섹션제목","subsections":["소제목1","소제목2"],"guidance":"이 섹션에서 작성해야 할 내용"}]\n\n'
        "규칙:\n"
        "- 양식의 빈칸/작성란을 기반으로 구조 파악\n"
        "- 비용/예산/사업비 관련 섹션은 제외\n"
        "- 표지, 서약서, 인감 등 행정 양식은 제외\n"
    )

    prompt = f"[양식 제목] {notice_title}\n\n[양식 텍스트]\n{template_text[:5000]}"

    try:
        raw = generate(prompt=prompt, system_instruction=system,
                       temperature=0.2, max_tokens=2048, timeout=40)
        sections = _parse_sections_json(raw)
        if sections:
            log.info("[BusinessPlan] 양식 분석 → %d개 섹션 추출", len(sections))
            return sections
    except Exception as e:
        log.warning("[BusinessPlan] 양식 섹션 추출 실패: %s", e)

    return _parse_sections_regex(template_text)


# ═════════════════════════════════════════════════════════════════════════════
#  Step 2: 각 섹션 AI 내용 생성
# ═════════════════════════════════════════════════════════════════════════════

def generate_section_content(
    section: Dict,
    notice: Notice,
    solutions: List[str],
    company_name: str = "(주)인터엑스",
) -> str:
    """한 섹션의 내용을 Gemini로 생성."""
    try:
        from interx_engine.infrastructure.ai.gemini_client import generate, is_available
        if not is_available():
            return _fallback_content(section, notice, solutions, company_name)
    except ImportError:
        return _fallback_content(section, notice, solutions, company_name)

    sol_info = _solutions_text(solutions)
    guidance = section.get("guidance", "")

    system = (
        f"당신은 '{notice.title}' 사업의 사업계획서 작성 전문가입니다.\n"
        f"기업명: {company_name}\n\n"
        "작성 규칙:\n"
        "1. 한국어, 공식 문서 어투\n"
        "2. 비용/예산/금액 정보는 절대 포함하지 마세요\n"
        "3. 구체적이고 실무적인 내용 (뻔한 일반론 X)\n"
        "4. 번호 매기기, 불릿 활용하여 가독성 확보\n"
        "5. 해당 섹션에 적합한 내용만 작성\n"
        "6. 600자 이내\n"
    )

    subsec_str = ""
    if section.get("subsections"):
        subsec_str = "\n소제목:\n" + "\n".join(f"  - {s}" for s in section["subsections"])

    prompt = (
        f"[공고 정보]\n"
        f"공고명: {notice.title}\n"
        f"주관기관: {notice.agency or '-'}\n"
        f"사업 요약: {(notice.summary or notice.body_text[:300])[:300]}\n\n"
        f"[기업 솔루션]\n{sol_info}\n\n"
        f"[작성 요청]\n"
        f"섹션: {section['title']}\n"
        f"{subsec_str}\n"
        f"{'작성 지침: ' + guidance if guidance else ''}\n\n"
        f"위 정보를 바탕으로 이 섹션의 내용을 작성하세요."
    )

    try:
        result = generate(prompt=prompt, system_instruction=system,
                          temperature=0.5, max_tokens=1200, timeout=35)
        if result and len(result) > 30:
            return result
    except Exception as e:
        log.warning("[BusinessPlan] 섹션 생성 실패 (%s): %s", section["title"], e)

    return _fallback_content(section, notice, solutions, company_name)


# ═════════════════════════════════════════════════════════════════════════════
#  Step 3: DOCX 문서 조립
# ═════════════════════════════════════════════════════════════════════════════

def build_docx(
    notice: Notice,
    sections: List[Dict],
    section_contents: Dict[str, str],
    score_card: Optional[ScoreCard] = None,
    solutions: List[str] = None,
    company_name: str = "(주)인터엑스",
) -> Optional[str]:
    """
    섹션 구조 + 생성된 내용 → DOCX 파일 조립.

    Returns:
        생성된 파일 경로
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
    except ImportError:
        log.error("[BusinessPlan] python-docx 미설치")
        return None

    doc = Document()

    # ── 기본 스타일 ───────────────────────────────────────────────────────
    style = doc.styles["Normal"]
    style.font.name = "맑은 고딕"
    style.font.size = Pt(10)
    style.paragraph_format.space_after = Pt(6)

    # ── 표지 ──────────────────────────────────────────────────────────────
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(notice.title)
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x0A, 0x16, 0x28)

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("사 업 계 획 서")
    run.bold = True
    run.font.size = Pt(28)
    run.font.color.rgb = RGBColor(0x00, 0x4E, 0x92)

    for _ in range(4):
        doc.add_paragraph()

    for line in [
        f"신 청 기 업 : {company_name}",
        f"작 성 일 자 : {date.today().isoformat()}",
        f"공 고 기 관 : {notice.agency or notice.ministry or '-'}",
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(line)
        run.font.size = Pt(13)

    doc.add_page_break()

    # ── 목차 ──────────────────────────────────────────────────────────────
    doc.add_heading("목 차", level=1)
    for sec in sections:
        doc.add_paragraph(sec["title"], style="List Number")
        for sub in sec.get("subsections", []):
            p = doc.add_paragraph(f"    {sub}")
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
    doc.add_page_break()

    # ── 공고 요약 정보 테이블 ─────────────────────────────────────────────
    doc.add_heading("공고 요약 정보", level=1)
    info_rows = [
        ("공고명", notice.title),
        ("주관기관", notice.agency or notice.ministry or "-"),
        ("마감일", notice.deadline_date or "-"),
        ("사업유형", notice.category or "-"),
        ("출처", notice.site),
    ]
    table = doc.add_table(rows=len(info_rows), cols=2)
    table.style = "Light Shading Accent 1"
    for i, (k, v) in enumerate(info_rows):
        table.rows[i].cells[0].text = k
        table.rows[i].cells[1].text = v
        for paragraph in table.rows[i].cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    # 적합도 정보
    if score_card:
        doc.add_paragraph()
        grade = score_card.priority_grade or "-"
        p = doc.add_paragraph()
        run = p.add_run(f"InterX 적합도: {grade} 등급 | "
                        f"적합도 {score_card.fitness_score:.0f}점 | "
                        f"우선순위 {score_card.priority_score:.0f}점")
        run.bold = True
        run.font.size = Pt(11)

    doc.add_page_break()

    # ── 본문 섹션 ─────────────────────────────────────────────────────────
    for sec in sections:
        doc.add_heading(sec["title"], level=1)

        content = section_contents.get(sec["title"], "")

        if not content:
            doc.add_paragraph(f"[작성 필요: {sec['title']}]")
            continue

        # 소제목이 있으면 heading level 2로
        for sub in sec.get("subsections", []):
            # content에 소제목이 포함되어 있으면 그냥 본문에 넣기
            pass

        # 내용 파싱 및 추가
        _add_content_to_doc(doc, content)

        doc.add_paragraph()  # 섹션 간 여백

    # ── 부록: 공고 원문 ───────────────────────────────────────────────────
    doc.add_page_break()
    doc.add_heading("부록: 공고 원문 참조", level=1)
    url = notice.detail_url or notice.notice_link or ""
    if url:
        doc.add_paragraph(f"공고 링크: {url}")
    body = notice.body_text or notice.summary or ""
    if body:
        excerpt = body[:2500]
        for line in excerpt.split("\n"):
            line = line.strip()
            if line:
                doc.add_paragraph(line)

    # ── 면책 ──────────────────────────────────────────────────────────────
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run(
        "※ 본 문서는 AI가 자동 생성한 사업계획서 초안입니다. "
        "실제 제출 전 반드시 검토/수정하세요. "
        "비용/예산 정보는 의도적으로 제외되었습니다."
    )
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    run.italic = True

    # ── 저장 ──────────────────────────────────────────────────────────────
    import tempfile
    out_dir = Path(tempfile.gettempdir()) / "interx_business_plans"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe = "".join(c for c in notice.title[:35] if c.isalnum() or c in " _-").strip()
    safe = safe or notice.notice_id
    fname = out_dir / f"사업계획서_{safe}.docx"
    doc.save(str(fname))
    log.info("[BusinessPlan] 저장: %s", fname.name)
    return str(fname)


# ═════════════════════════════════════════════════════════════════════════════
#  통합 실행 함수
# ═════════════════════════════════════════════════════════════════════════════

def generate_business_plan(
    notice: Notice,
    score_card: Optional[ScoreCard] = None,
    template_text: str = "",
    company_name: str = "(주)인터엑스",
    progress_callback=None,
) -> Optional[str]:
    """
    공고 맞춤형 사업계획서 생성 (통합 진입점).

    Args:
        notice: 대상 공고
        score_card: 점수 카드 (없으면 키워드 기반 매칭)
        template_text: 업로드된 양식 텍스트 (빈 문자열이면 공고 분석 모드)
        company_name: 기업명
        progress_callback: 진행률 콜백 fn(pct, msg)

    Returns:
        생성된 DOCX 파일 경로
    """
    def _progress(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)
        log.info("[BusinessPlan] [%d%%] %s", pct, msg)

    _progress(5, "솔루션 매칭 중...")
    solutions = _detect_relevant_solutions(notice, score_card)

    # Step 1: 섹션 구조 추출
    _progress(10, "섹션 구조 분석 중...")
    if template_text:
        sections = extract_sections_from_template(template_text, notice.title)
        _progress(25, f"양식 분석 완료 → {len(sections)}개 섹션")
    else:
        sections = extract_sections_from_notice(notice)
        _progress(25, f"공고 분석 완료 → {len(sections)}개 섹션")

    if not sections:
        _progress(25, "기본 섹션 구조 사용")
        sections = _default_sections(notice)

    # Step 2: 각 섹션 내용 생성
    section_contents = {}
    total = len(sections)
    for i, sec in enumerate(sections):
        pct = 30 + int(60 * i / max(total, 1))
        _progress(pct, f"섹션 생성 중: {sec['title']}")
        content = generate_section_content(sec, notice, solutions, company_name)
        section_contents[sec["title"]] = content

    # Step 3: DOCX 조립
    _progress(92, "DOCX 문서 조립 중...")
    path = build_docx(
        notice=notice,
        sections=sections,
        section_contents=section_contents,
        score_card=score_card,
        solutions=solutions,
        company_name=company_name,
    )

    _progress(100, "완료!")
    return path


# ═════════════════════════════════════════════════════════════════════════════
#  유틸리티 함수들
# ═════════════════════════════════════════════════════════════════════════════

def _prepare_notice_text(notice: Notice) -> str:
    """공고 분석용 텍스트 준비."""
    parts = []
    if notice.summary:
        parts.append(notice.summary)
    if notice.body_text:
        parts.append(notice.body_text[:4000])
    if notice.structured:
        for k, v in notice.structured.items():
            if v:
                parts.append(f"{k}: {v[:500]}")
    return "\n".join(parts)


def _detect_relevant_solutions(notice: Notice, sc: Optional[ScoreCard]) -> List[str]:
    """공고에 적합한 솔루션 Top 3."""
    text = f"{notice.title} {notice.summary} {notice.body_text[:2000]}".lower()

    # ScoreCard 솔루션 점수 우선
    if sc and sc.solution_scores:
        ranked = sorted(
            [(k, v) for k, v in sc.solution_scores.items() if v > 0],
            key=lambda x: -x[1],
        )
        if ranked:
            return [k for k, _ in ranked[:3]]

    # 키워드 매칭 fallback
    scores = {}
    for sol_key, sol_info in INTERX_CAPABILITIES.items():
        scores[sol_key] = sum(1 for kw in sol_info["keywords"] if kw.lower() in text)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [k for k, v in ranked[:3] if v > 0] or ["QualityAI", "PdM"]


def _solutions_text(solutions: List[str]) -> str:
    """솔루션 정보를 텍스트로 정리."""
    lines = []
    for s in solutions:
        cap = INTERX_CAPABILITIES.get(s, {})
        if cap:
            lines.append(f"- {cap['name']}: {cap['desc']}")
            lines.append(f"  기술스택: {cap['tech']}")
            for st_item in cap.get("strengths", [])[:2]:
                lines.append(f"  역량: {st_item}")
    return "\n".join(lines) if lines else "범용 제조 AI 솔루션"


def _parse_sections_json(raw: str) -> List[Dict]:
    """Gemini 응답에서 JSON 배열 추출."""
    import json

    # ```json ... ``` 블록 추출
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # 순수 JSON 배열 추출
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            raw = m.group(0)

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            result = []
            for item in data:
                if isinstance(item, dict) and "title" in item:
                    result.append({
                        "title": item["title"],
                        "subsections": item.get("subsections", []),
                        "guidance": item.get("guidance", ""),
                    })
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _parse_sections_regex(text: str) -> List[Dict]:
    """정규식으로 양식 텍스트에서 번호 매겨진 섹션 제목 추출."""
    # "1. 제목", "Ⅰ. 제목", "가. 제목" 등 패턴
    patterns = [
        r"^(\d+[\.\)]\s+.+)$",                    # 1. 제목
        r"^([IⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[\.\)]\s+.+)$",  # Ⅰ. 제목
        r"^([가나다라마바사아자차카타파하][\.\)]\s+.+)$",  # 가. 제목
    ]
    sections = []
    for line in text.split("\n"):
        line = line.strip()
        for pat in patterns:
            if re.match(pat, line):
                # 비용/예산 관련 제외
                if any(kw in line for kw in ["사업비", "예산", "비용", "재원", "출연금"]):
                    continue
                sections.append({
                    "title": line,
                    "subsections": [],
                    "guidance": "",
                })
                break
    return sections


def _default_sections(notice: Notice) -> List[Dict]:
    """공고 분석 실패 시 기본 섹션 (사업 성격 추론)."""
    title_lower = f"{notice.title} {notice.summary}".lower()

    # 스마트공장 계열
    if any(kw in title_lower for kw in ["스마트공장", "스마트 공장", "제조ai", "스마트팩토리"]):
        return [
            {"title": "1. 스마트공장 구축 개요", "subsections": ["1.1 구축 목표", "1.2 현재 수준 진단", "1.3 목표 수준"], "guidance": ""},
            {"title": "2. 기업 현황", "subsections": ["2.1 기업 개요", "2.2 주요 생산품 및 공정", "2.3 기존 정보화 현황"], "guidance": ""},
            {"title": "3. 구축 내용", "subsections": ["3.1 핵심 기술 적용 방안", "3.2 시스템 구성", "3.3 데이터 수집/활용 계획"], "guidance": ""},
            {"title": "4. 추진 체계 및 일정", "subsections": ["4.1 추진 체계", "4.2 단계별 일정", "4.3 투입 인력"], "guidance": ""},
            {"title": "5. 기대효과 및 성과지표", "subsections": ["5.1 정량적 기대효과", "5.2 정성적 기대효과", "5.3 KPI"], "guidance": ""},
        ]

    # R&D 계열
    if any(kw in title_lower for kw in ["연구개발", "r&d", "기술개발", "연구과제"]):
        return [
            {"title": "1. 필요성 및 현황", "subsections": ["1.1 기술/제품 개요", "1.2 국내외 기술 현황", "1.3 시장 현황"], "guidance": ""},
            {"title": "2. 과제 목표 및 내용", "subsections": ["2.1 최종목표", "2.2 연차별 목표", "2.3 수행일정"], "guidance": ""},
            {"title": "3. 추진전략 및 추진체계", "subsections": ["3.1 추진전략", "3.2 추진체계", "3.3 기술개발팀 편성"], "guidance": ""},
            {"title": "4. 성과 활용방안", "subsections": ["4.1 활용방안", "4.2 기대효과"], "guidance": ""},
            {"title": "5. 사업화 전략", "subsections": ["5.1 사업화 전략", "5.2 시장 진출 계획"], "guidance": ""},
        ]

    # 일반
    return [
        {"title": "1. 사업 개요", "subsections": ["1.1 사업 목적", "1.2 사업 범위", "1.3 추진 필요성"], "guidance": ""},
        {"title": "2. 기업 현황 및 역량", "subsections": ["2.1 기업 개요", "2.2 기술 역량", "2.3 수행 실적"], "guidance": ""},
        {"title": "3. 기술 개발 내용", "subsections": ["3.1 핵심 기술", "3.2 적용 방안", "3.3 차별성"], "guidance": ""},
        {"title": "4. 추진 체계 및 일정", "subsections": ["4.1 추진 체계", "4.2 추진 일정"], "guidance": ""},
        {"title": "5. 기대효과", "subsections": ["5.1 기술적 효과", "5.2 경제적 효과"], "guidance": ""},
    ]


def _fallback_content(
    section: Dict,
    notice: Notice,
    solutions: List[str],
    company_name: str,
) -> str:
    """Gemini 실패 시 기본 템플릿."""
    sol_names = [INTERX_CAPABILITIES.get(s, {}).get("name", s) for s in solutions]
    title = section["title"].lower()

    if "개요" in title or "목적" in title or "배경" in title or "필요성" in title:
        return (
            f"본 사업은 '{notice.title}'에 따라 {company_name}가 보유한 "
            f"{', '.join(sol_names)} 기술을 활용하여 추진합니다.\n\n"
            "[작성 필요: 사업의 구체적 목적, 배경, 필요성을 기술하세요]"
        )

    if "기업" in title or "현황" in title or "역량" in title:
        lines = [f"{company_name}은 제조 AI 전문기업입니다.\n\n주요 역량:"]
        for s, n in zip(solutions, sol_names):
            cap = INTERX_CAPABILITIES.get(s, {})
            lines.append(f"- {n}: {cap.get('desc', '')}")
        lines.append("\n[작성 필요: 기업 상세 현황, 연혁, 인력 등]")
        return "\n".join(lines)

    if "기술" in title or "구축" in title or "개발" in title:
        lines = ["핵심 기술 적용 방안:\n"]
        for s, n in zip(solutions, sol_names):
            cap = INTERX_CAPABILITIES.get(s, {})
            lines.append(f"- {n}: {cap.get('desc', '')}")
            lines.append(f"  기술스택: {cap.get('tech', '')}")
        lines.append("\n[작성 필요: 상세 기술 내용, 시스템 구성도]")
        return "\n".join(lines)

    if "추진" in title:
        return (
            f"추진 체계:\n"
            f"- 총괄 PM: {company_name}\n"
            f"- 기술 개발: AI/데이터 팀\n"
            f"- 현장 적용: 수요기업 협력\n\n"
            "[작성 필요: 상세 추진 일정, 인력 투입 계획]"
        )

    if "기대" in title or "성과" in title or "KPI" in title or "효과" in title:
        return (
            "기대효과:\n"
            "- 생산성 향상\n"
            "- 불량률 감소\n"
            "- 공정 효율 개선\n"
            "- 데이터 기반 의사결정 체계 구축\n\n"
            "[작성 필요: 구체적 수치 목표 (예: 생산성 20%↑, 불량률 30%↓)]"
        )

    if "사업화" in title or "시장" in title or "활용" in title:
        return (
            "사업화 전략:\n"
            "- 과제 성과를 기반으로 유사 제조 현장 확산\n"
            "- 솔루션 패키지화를 통한 B2B 모델 구축\n\n"
            "[작성 필요: 구체적 사업화 계획]"
        )

    return f"[작성 필요: {section['title']}]"


def _add_content_to_doc(doc, content: str):
    """텍스트 내용을 DOCX 문단으로 변환."""
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 마크다운 볼드 → 일반 텍스트
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        # 마크다운 헤더 → 굵은 텍스트
        header_match = re.match(r"^#{1,3}\s+(.+)", line)
        if header_match:
            from docx.shared import Pt
            p = doc.add_paragraph()
            run = p.add_run(header_match.group(1))
            run.bold = True
            run.font.size = Pt(11)
            continue
        # 불릿 아이템
        if re.match(r"^[-*]\s", line):
            doc.add_paragraph(line.lstrip("-* "), style="List Bullet")
        elif re.match(r"^\d+[\.\)]\s", line):
            doc.add_paragraph(line, style="List Number")
        else:
            doc.add_paragraph(line)


def parse_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """
    업로드된 파일(PDF/HWP/HWPX/TXT)에서 텍스트 추출.

    Returns:
        추출된 텍스트
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("cp949", errors="replace")

    if ext == ".pdf":
        return _extract_pdf_text(file_bytes)

    if ext == ".hwpx":
        return _extract_hwpx_text(file_bytes)

    if ext == ".hwp":
        return _extract_hwp_text(file_bytes)

    log.warning("[BusinessPlan] 미지원 파일 형식: %s", ext)
    return ""


def _extract_pdf_text(data: bytes) -> str:
    """PDF 텍스트 추출."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        texts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
        return "\n".join(texts)
    except ImportError:
        log.warning("[BusinessPlan] pypdf 미설치")
    except Exception as e:
        log.warning("[BusinessPlan] PDF 파싱 실패: %s", e)
    return ""


def _extract_hwpx_text(data: bytes) -> str:
    """HWPX (ZIP+XML) 텍스트 추출."""
    import zipfile
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            texts = []
            for name in sorted(zf.namelist()):
                if name.startswith("Contents/section") and name.endswith(".xml"):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(zf.open(name))
                        root = tree.getroot()
                        # 모든 텍스트 노드 수집
                        for elem in root.iter():
                            if elem.text and elem.text.strip():
                                texts.append(elem.text.strip())
                    except Exception:
                        pass
            return "\n".join(texts)
    except Exception as e:
        log.warning("[BusinessPlan] HWPX 파싱 실패: %s", e)
    return ""


def _extract_hwp_text(data: bytes) -> str:
    """HWP (바이너리 OLE) 텍스트 추출 — 노이즈 필터링 포함."""
    try:
        import olefile
        import zlib
        import io

        ole = olefile.OleFileIO(io.BytesIO(data))
        texts = []
        for entry in ole.listdir():
            name = "/".join(entry)
            if name.startswith("BodyText/Section"):
                raw = ole.openstream(name).read()
                try:
                    decompressed = zlib.decompress(raw, -15)
                except zlib.error:
                    decompressed = raw
                try:
                    t = decompressed.decode("utf-16-le", errors="replace")
                except Exception:
                    t = decompressed.decode("cp949", errors="replace")
                # 한글/영문/숫자/기본 문장부호만 추출
                clean = re.findall(
                    r'[가-힣ㄱ-ㆎa-zA-Z0-9 \-~\.\,\(\)\[\]\/\:\;\!\?\%\+\=\@\#\&\*\"\']+',
                    t,
                )
                clean_text = " ".join(c.strip() for c in clean if len(c.strip()) > 1)
                if clean_text:
                    texts.append(clean_text)
        ole.close()
        return "\n".join(texts)
    except ImportError:
        log.warning("[BusinessPlan] olefile 미설치")
    except Exception as e:
        log.warning("[BusinessPlan] HWP 파싱 실패: %s", e)
    return ""
