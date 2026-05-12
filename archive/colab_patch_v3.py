"""
🔧 InterX 패치 셀 v3 — 6개 기능 추가 (Playwright·Retry·상시공고·예산정규화·TF-IDF중복·대시보드)
Colab에 붙여넣고 실행 → 이후 아래 셀에서 설치 + main.py 실행

실행 순서:
  1. 이 셀 (파일 패치)
  2. !pip install playwright && playwright install chromium
  3. exec(open("main.py").read())
"""
import pathlib, textwrap, shutil

ROOT = pathlib.Path("/content/drive/MyDrive/interx_gov_intelligence")
SRC  = ROOT / "src/interx_engine"

# ── utils 디렉토리 생성 ─────────────────────────────────────────────────────
(SRC / "infrastructure/utils").mkdir(parents=True, exist_ok=True)
(SRC / "infrastructure/utils/__init__.py").write_text("", encoding="utf-8")

# ── [1] budget_parser.py (신규) ─────────────────────────────────────────────
(SRC / "infrastructure/utils/budget_parser.py").write_text(textwrap.dedent('''\
import re
from typing import Optional

_OPEN_ENDED = ["상시","예산소진","별도공지","추후공지","미정","협의",
               "해당없음","마감없음","해당 없음","수시","상시접수"]

def is_open_ended(deadline_str: str) -> bool:
    if not deadline_str: return False
    s = deadline_str.strip()
    for p in _OPEN_ENDED:
        if p in s: return True
    has_date = bool(re.search(r"\\d{4}[-./]\\d{1,2}[-./]\\d{1,2}", s)
                    or re.search(r"\\d{8}", s)
                    or re.search(r"\\d{4}년\\s*\\d{1,2}월", s))
    if not has_date and len(s) >= 2 and not s.isdigit():
        return True
    return False

def parse_budget_eok(raw: str) -> Optional[float]:
    if not raw: return None
    s = str(raw).strip().replace(",","").replace(" ","").replace("\\xa0","")
    m = re.search(r"([0-9.]+)조", s)
    if m: return round(float(m.group(1))*10000, 2)
    m = re.search(r"([0-9.]+)억([0-9.]+)천만", s)
    if m: return round(float(m.group(1))+float(m.group(2))*0.1, 2)
    m = re.search(r"([0-9.]+)억", s)
    if m: return round(float(m.group(1)), 2)
    m = re.search(r"([0-9.]+)천만", s)
    if m: return round(float(m.group(1))*0.1, 2)
    m = re.search(r"([0-9.]+)백만", s)
    if m: return round(float(m.group(1))/100, 2)
    m = re.search(r"([0-9.]+)천원", s)
    if m: return round(float(m.group(1))/100000, 2)
    m = re.search(r"([0-9.]+)만원?", s)
    if m: return round(float(m.group(1))/10000, 2)
    m = re.match(r"^([0-9.]+)원?$", s)
    if m: return round(float(m.group(1))/100_000_000, 2)
    return None

def normalize_budget(raw: str) -> str:
    val = parse_budget_eok(raw)
    if val is None or val <= 0: return raw
    if val >= 1:
        return f"{int(val)}억" if val == int(val) else f"{val:.1f}억"
    return f"{round(val*10000)}만원"
'''), encoding="utf-8")
print("✅ [1] budget_parser.py")

# ── [2] notice.py — open_ended + duplicate_flag 필드 추가 ───────────────────
notice_path = SRC / "core/entities/notice.py"
code = notice_path.read_text(encoding="utf-8")
if "open_ended" not in code:
    code = code.replace(
        'status: str = ""                        # 검토상태',
        'status: str = ""                        # 검토상태\n'
        '    open_ended: bool = False                # 상시모집/예산소진시 등 비정형 마감\n'
        '    duplicate_flag: str = "N"              # TF-IDF 중복 감지 플래그'
    )
    code = code.replace(
        'def is_closed(self) -> bool:\n        if not self.deadline_date:',
        'def is_closed(self) -> bool:\n        if self.open_ended:\n            return False\n        if not self.deadline_date:'
    )
    notice_path.write_text(code, encoding="utf-8")
    print("✅ [2] notice.py (open_ended, duplicate_flag 추가)")
else:
    print("✅ [2] notice.py (이미 패치됨)")

# ── [3] notice_mapper.py ────────────────────────────────────────────────────
(SRC / "application/mappers/notice_mapper.py").write_text(textwrap.dedent('''\
from __future__ import annotations
from datetime import date
from typing import Optional
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard
from interx_engine.infrastructure.utils.budget_parser import is_open_ended, normalize_budget

def _calc_dday(deadline: str) -> str:
    if not deadline: return ""
    if is_open_ended(deadline): return "상시"
    try:
        return str((date.fromisoformat(deadline[:10]) - date.today()).days)
    except Exception: return ""

def notice_to_master_row(notice: Notice, score: Optional[ScoreCard] = None) -> dict:
    budget_norm = normalize_budget(notice.budget) if notice.budget else ""
    dup_flag    = getattr(notice, "duplicate_flag", "N")
    open_ended  = getattr(notice, "open_ended", False)
    memo        = "⚠️중복의심" if dup_flag == "Y" else ""
    return {
        "실행ID":      notice.execution_id,
        "사이트":      notice.site,
        "공고명":      notice.title,
        "마감일":      "상시모집" if open_ended else notice.deadline_date,
        "D-day":      _calc_dday(notice.deadline_date),
        "마감여부":     "상시" if open_ended else ("Y" if notice.is_closed() else "N"),
        "주무부처":     notice.ministry,
        "수행기관":     notice.agency,
        "예산":        budget_norm,
        "적합도점수":   score.fitness_score  if score else "",
        "우선순위등급":  score.priority_grade if score else "",
        "추천솔루션":   notice.recommended_solution or "-",
        "추천액션":     notice.recommended_action   or "검토",
        "적합키워드":   " | ".join(score.positive_keywords[:5]) if score else "",
        "L3강공고":     notice.l3_strong,
        "파트너후보":   notice.partner_candidate,
        "담당자":      notice.manager or "",
        "검토상태":     notice.status  or "",
        "메모":        memo,
        "상세URL":     notice.detail_url,
    }

def notice_to_urgent_row(notice: Notice, score: Optional[ScoreCard] = None) -> dict:
    return {
        "사이트":      notice.site,
        "공고명":      notice.title,
        "마감일":      notice.deadline_date,
        "D-day":      _calc_dday(notice.deadline_date),
        "우선순위등급": score.priority_grade  if score else "",
        "적합도점수":   score.fitness_score   if score else "",
        "추천솔루션":   notice.recommended_solution or "-",
        "추천액션":     notice.recommended_action   or "검토",
        "예산":        normalize_budget(notice.budget) if notice.budget else "",
        "담당자":       notice.manager or "",
        "상세URL":     notice.detail_url,
    }
'''), encoding="utf-8")
print("✅ [3] notice_mapper.py (예산정규화 + 상시공고 처리)")

# ── [4] deduplicate_notices.py (신규) ───────────────────────────────────────
(SRC / "application/use_cases/deduplicate_notices.py").write_text(textwrap.dedent('''\
from __future__ import annotations
import logging
from typing import List, Tuple
from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard

log = logging.getLogger("interx.dedup")
_SIM_THRESHOLD = 0.82

def deduplicate_by_tfidf(notices: List[Notice], score_cards: List[ScoreCard]) -> Tuple[List[Notice], int]:
    if len(notices) < 2: return notices, 0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        log.warning("[Dedup] scikit-learn 없음 — 스킵")
        return notices, 0
    score_map = {s.notice_id: (s.fitness_score or 0) for s in score_cards}
    try:
        vec   = TfidfVectorizer(analyzer="char_wb", ngram_range=(2,3), min_df=1)
        tfidf = vec.fit_transform([n.title for n in notices])
        sim   = cosine_similarity(tfidf)
    except Exception as e:
        log.warning("[Dedup] 계산 실패: %s", e); return notices, 0
    dup_count, flagged = 0, set()
    for i in range(len(notices)):
        if i in flagged: continue
        for j in range(i+1, len(notices)):
            if j in flagged: continue
            if notices[i].site == notices[j].site: continue
            if sim[i,j] >= _SIM_THRESHOLD:
                dup_idx = j if score_map.get(notices[i].notice_id,0) >= score_map.get(notices[j].notice_id,0) else i
                flagged.add(dup_idx)
                notices[dup_idx].duplicate_flag = "Y"
                dup_count += 1
                log.debug("[Dedup] %.2f: \'%s\' ↔ \'%s\'", sim[i,j], notices[i].title[:30], notices[j].title[:30])
    if dup_count: log.info("[Dedup] 중복 의심 %d건 플래그", dup_count)
    return notices, dup_count
'''), encoding="utf-8")
print("✅ [4] deduplicate_notices.py")

# ── [5] daily_pipeline.py ───────────────────────────────────────────────────
(SRC / "application/orchestrators/daily_pipeline.py").write_text(textwrap.dedent('''\
from __future__ import annotations
import logging, time
from interx_engine.application.use_cases.collect_notices import CollectNoticesUseCase
from interx_engine.application.use_cases.score_notices import ScoreNoticesUseCase
from interx_engine.application.use_cases.deduplicate_notices import deduplicate_by_tfidf
from interx_engine.application.mappers.notice_mapper import notice_to_master_row, notice_to_urgent_row, _calc_dday
from interx_engine.application.mappers.kpi_mapper import (
    build_kpi_rows, build_exec_log_row, build_site_stats_rows, build_collect_error_rows)

log = logging.getLogger("interx.pipeline")
_URGENT_DDAY = 7

class DailyPipelineOrchestrator:
    def __init__(self, collector, sheet_gateway=None, **_):
        self.collect_use_case = CollectNoticesUseCase(collector)
        self.score_use_case   = ScoreNoticesUseCase()
        self.sheet_gateway    = sheet_gateway

    def run(self, execution_id):
        t0 = time.monotonic()
        log.info("[Pipeline] 수집 시작 (%s)", execution_id)
        notices = self.collect_use_case.execute(execution_id)
        log.info("[Pipeline] %d건 수집 완료", len(notices))

        # 중복 제거
        seen, unique = set(), []
        for n in notices:
            if n.notice_id not in seen:
                seen.add(n.notice_id); unique.append(n)
        if len(unique) < len(notices):
            log.info("[Pipeline] 중복 제거: %d → %d건", len(notices), len(unique))
        notices = unique

        # 스코어링
        notices, score_cards = self.score_use_case.execute(notices)
        score_map = {s.notice_id: s for s in score_cards}

        # TF-IDF 중복 감지
        notices, dup_count = deduplicate_by_tfidf(notices, score_cards)

        # 행 빌드
        master_rows, l3_rows, urgent_rows = [], [], []
        for notice in notices:
            score = score_map.get(notice.notice_id)
            row   = notice_to_master_row(notice, score)
            master_rows.append(row)
            if notice.l3_strong == "Y":
                l3_rows.append(row.copy())
            dday_str = _calc_dday(notice.deadline_date)
            if dday_str and dday_str != "상시":
                try:
                    if 0 <= int(dday_str) <= _URGENT_DDAY:
                        urgent_rows.append(notice_to_urgent_row(notice, score))
                except ValueError:
                    pass

        # KPI / 통계 / 에러
        elapsed    = round(time.monotonic() - t0, 1)
        kpi_rows   = build_kpi_rows(execution_id, notices, score_cards)
        site_stats = build_site_stats_rows(execution_id, notices, score_cards)
        collector_obj = getattr(self.collect_use_case, "collector", None)
        raw_errors    = getattr(collector_obj, "last_errors", [])
        error_rows    = build_collect_error_rows(execution_id, raw_errors)
        exec_log_row  = build_exec_log_row(
            execution_id, "pipeline_complete", "OK", elapsed,
            f"총 {len(notices)}건 처리 완료 (L3={len(l3_rows)}, 긴급={len(urgent_rows)}, 중복의심={dup_count}, 에러={len(error_rows)})")

        if self.sheet_gateway:
            self._upload(master_rows, l3_rows, urgent_rows,
                         kpi_rows, site_stats, error_rows, exec_log_row, elapsed, len(notices))

        return {"notice_count":len(notices),"master_rows":master_rows,
                "l3_rows":l3_rows,"urgent_rows":urgent_rows,
                "dup_count":dup_count,"error_count":len(error_rows)}

    def _upload(self, master_rows, l3_rows, urgent_rows,
                kpi_rows, site_stats, error_rows, exec_log_row, elapsed, total):
        gw = self.sheet_gateway
        try:
            if hasattr(gw, "cleanup_old_sheets"): gw.cleanup_old_sheets()
        except Exception as e:
            log.warning("[Pipeline] cleanup 실패: %s", e)
        try:
            gw.replace_rows("01_영업기회_정보", master_rows)
            gw.replace_rows("02_L3강공고",      l3_rows)
            gw.replace_rows("05_긴급마감_공고",  urgent_rows)
            if kpi_rows:   gw.append_rows("22_KPI현황",         kpi_rows)
            if site_stats: gw.append_rows("93_사이트별수집통계", site_stats)
            gw.append_rows("94_실행로그", [exec_log_row])
            if error_rows: gw.append_rows("96_수집에러로그",     error_rows)
            log.info("[Pipeline] 업로드 완료 (%.1fs, %d건)", elapsed, total)
        except Exception as exc:
            log.error("[Pipeline] 업로드 실패: %s", exc); raise
'''), encoding="utf-8")
print("✅ [5] daily_pipeline.py (TF-IDF 중복감지 + 상시공고 D-day)")

# ── [6] PlaywrightBaseCollector + KiatCollector/DiciaCollector 수정 ─────────
mc_path = SRC / "infrastructure/collectors/sites/multi_site_collectors.py"
mc_code = mc_path.read_text(encoding="utf-8")

PLAYWRIGHT_CLASS = '''
# =============================================================================
# PlaywrightBaseCollector — JS 렌더링 필요 사이트용
# playwright 미설치 시 requests fallback 자동
# =============================================================================
class PlaywrightBaseCollector(BaseCollector):
    def collect(self, execution_id):
        try:
            return self._collect_playwright(execution_id)
        except ImportError:
            log.warning("[%s] playwright 미설치 → requests fallback", self.site_key)
            return super().collect(execution_id)
        except Exception as e:
            log.warning("[%s] playwright 실패 (%s) → requests fallback", self.site_key, e)
            return super().collect(execution_id)

    def _collect_playwright(self, execution_id):
        from playwright.sync_api import sync_playwright
        notices, seen_ids = [], set()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx  = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR")
            page = ctx.new_page()
            for pg in range(1, self.max_pages + 1):
                url = self._page_url(pg)
                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(2000)
                    soup  = BeautifulSoup(page.content(), "lxml")
                    items = self._parse_page(soup, execution_id)
                except Exception as e:
                    log.error("[%s] playwright p%d: %s", self.site_key, pg, e); break
                if not items: break
                new = [n for n in items if n.notice_id not in seen_ids]
                if not new: break
                for n in new: seen_ids.add(n.notice_id)
                notices.extend(new)
                time.sleep(random.uniform(1.0, 2.0))
            browser.close()
        log.info("[%s] playwright %d건", self.site_key.upper(), len(notices))
        return notices

'''

# PlaywrightBaseCollector 삽입 (이미 없는 경우만)
if "PlaywrightBaseCollector" not in mc_code:
    # KIAT 섹션 주석 바로 앞에 삽입
    insert_marker = "# =============================================================================\n# ③ KIAT"
    mc_code = mc_code.replace(insert_marker, PLAYWRIGHT_CLASS + insert_marker)
    print("✅ [6a] PlaywrightBaseCollector 삽입")
else:
    print("✅ [6a] PlaywrightBaseCollector 이미 존재")

# KiatCollector 부모 변경
if "class KiatCollector(BaseCollector)" in mc_code:
    mc_code = mc_code.replace("class KiatCollector(BaseCollector)", "class KiatCollector(PlaywrightBaseCollector)")
    print("✅ [6b] KiatCollector → PlaywrightBaseCollector")

# DiciaCollector 부모 변경
if "class DiciaCollector(BaseCollector)" in mc_code:
    mc_code = mc_code.replace("class DiciaCollector(BaseCollector)", "class DiciaCollector(PlaywrightBaseCollector)")
    print("✅ [6c] DiciaCollector → PlaywrightBaseCollector")

mc_path.write_text(mc_code, encoding="utf-8")

# ── [7] run_engine.py — 콜렉터 레벨 retry ───────────────────────────────────
re_path = ROOT / "run_engine.py"
re_code = re_path.read_text(encoding="utf-8")

if "_collect_with_retry" not in re_code:
    OLD_COLLECT = "    def collect(self, execution_id: str) -> list:\n        if not self.collectors:\n            return []\n        all_notices: list = []\n        self.last_errors  = []"
    NEW_COLLECT = '''\
    def _collect_with_retry(self, col, execution_id: str, max_retries: int = 2) -> list:
        site, last_exc = getattr(col, "site_key", repr(col)), None
        for attempt in range(max_retries + 1):
            try: return col.collect(execution_id)
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    log.warning("[Retry] %-12s (attempt %d/%d) %ds후 재시도: %s", site, attempt+1, max_retries+1, wait, e)
                    time.sleep(wait)
        raise last_exc

    def collect(self, execution_id: str) -> list:
        if not self.collectors:
            return []
        all_notices: list = []
        self.last_errors  = []'''
    if OLD_COLLECT in re_code:
        re_code = re_code.replace(OLD_COLLECT, NEW_COLLECT)
        # futures도 _collect_with_retry 사용으로 교체
        re_code = re_code.replace(
            "futures = {ex.submit(c.collect, execution_id): c for c in self.collectors}",
            "futures = {ex.submit(self._collect_with_retry, c, execution_id): c for c in self.collectors}"
        )
        re_path.write_text(re_code, encoding="utf-8")
        print("✅ [7] run_engine.py (retry 추가)")
    else:
        print("⚠️  [7] run_engine.py — 패턴 불일치 (수동 확인)")
else:
    print("✅ [7] run_engine.py (이미 패치됨)")

print("\n" + "="*55)
print("🎉 패치 v3 완료!")
print("="*55)
print("\n▶ 다음 셀에서 실행하세요:")
print("  !pip install -q playwright")
print("  !playwright install chromium")
print("  exec(open('main.py').read())")
