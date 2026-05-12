# =============================================================================
# InterX Government Intelligence Engine — Google Colab 실행 코드
# 각 셀을 위에서 아래로 순서대로 실행하세요.
# =============================================================================

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 1] 구글 드라이브 마운트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from google.colab import drive
drive.mount("/content/drive")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 2] 프로젝트 경로 설정 (본인 드라이브 경로에 맞게 수정)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import os, sys

# ★ 드라이브 내 프로젝트 폴더 경로 (본인 설정에 맞게 수정)
PROJECT_DIR = "/content/drive/MyDrive/interx_gov_intelligence"

os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "src"))

print(f"작업 디렉토리: {os.getcwd()}")
print(f"폴더 내용: {os.listdir('.')}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 3] 패키지 설치 (처음 실행 시 또는 런타임 재시작 후 실행)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 핵심 패키지 (필수)
get_ipython().system("pip install -q requests beautifulsoup4 lxml PyYAML gspread google-auth python-dotenv nest-asyncio scikit-learn openpyxl pandas python-dateutil")

# 문서 파싱 (첨부파일 분석용)
get_ipython().system("pip install -q pypdf python-docx olefile")

# Playwright 설치 (kiat·dicia 사이트 JS 렌더링 필요)
get_ipython().system("pip install -q playwright")
get_ipython().system("playwright install chromium --with-deps -q")

print("패키지 설치 완료")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 4] 환경변수 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import os

# ── Google Sheets 연동 ────────────────────────────────────────────────────────
# service_account.json 파일이 PROJECT_DIR 에 있어야 합니다.
os.environ["INTERX_SA_JSON"]      = os.path.join(PROJECT_DIR, "service_account.json")
os.environ["INTERX_SHEET_NAME"]   = "InterX_BD_CRM_v10_fresh_template"  # ★ 시트 이름

# ── 저장 경로 ─────────────────────────────────────────────────────────────────
os.environ["INTERX_DB_PATH"]      = os.path.join(PROJECT_DIR, "data", "interx_engine.db")
os.environ["INTERX_ATT_DIR"]      = os.path.join(PROJECT_DIR, "data", "attachments")
os.environ["INTERX_LOG_DIR"]      = os.path.join(PROJECT_DIR, "logs")

# ── 수집 설정 ─────────────────────────────────────────────────────────────────
os.environ["INTERX_MAX_PAGES"]    = "3"    # 사이트당 최대 페이지 수
os.environ["INTERX_WORKERS"]      = "4"    # 병렬 수집 워커 수
os.environ["INTERX_TIMEOUT"]      = "30"   # HTTP 타임아웃(초)
os.environ["INTERX_FETCH_DETAIL"] = "true" # 상세 페이지 방문 여부

# ── 알림 (선택) ────────────────────────────────────────────────────────────────
# Slack을 사용하려면 아래 주석 해제 후 실제 Webhook URL 입력
# os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/xxx/yyy/zzz"

# Telegram을 사용하려면 아래 주석 해제 후 실제 값 입력
# os.environ["TELEGRAM_BOT_TOKEN"] = "1234567890:ABCdef..."
# os.environ["TELEGRAM_CHAT_ID"]   = "-100123456789"

print("환경변수 설정 완료")
print(f"  시트명: {os.environ['INTERX_SHEET_NAME']}")
print(f"  DB 경로: {os.environ['INTERX_DB_PATH']}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 5] asyncio 충돌 방지 (Colab 필수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import nest_asyncio
nest_asyncio.apply()
print("nest_asyncio 적용 완료")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 6] 엔진 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ★ 실행할 사이트 목록 (주석 참고)
# 전체 : None
# 일부 : ["bizinfo", "bipa", "nipa", "smba", "iris", "kiat", "innopolis",
#          "uipa", "ttp", "gjtp", "gbtp", "jntp", "jbtp", "gicon", "dicia"]

SITES      = None   # None = 전체 사이트
MAX_PAGES  = 3      # 사이트당 최대 페이지

# 실행 (Google Sheets 연동)
import importlib, run_engine
importlib.reload(run_engine)

result = run_engine.main(
    site_keys     = SITES,
    max_pages     = MAX_PAGES,
    enable_sheets = True,    # False: 시트 업로드 없이 로컬만 저장
    full_pipeline = False,   # True: 클러스터링·파트너매칭 포함 (느림)
    dry_run       = False,
    no_alert      = False,   # True: 알림 발송 안 함
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 7] 결과 확인
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n" + "="*55)
print("  수집 건수  :", result.get("notice_count", 0))
print("  L3 강공고  :", len(result.get("l3_rows", [])))
print("  긴급마감   :", len(result.get("urgent_rows", [])))
print("  신규 공고  :", result.get("new_count", 0))
print("  변경 공고  :", result.get("changed_count", 0))
print("  중복 제거  :", result.get("dup_count", 0))
print("  마감 제거  :", result.get("expired_count", 0))
print("  오류 건수  :", result.get("error_count", 0))
print("="*55)

# L3 강공고 목록 출력
l3 = result.get("l3_rows", [])
if l3:
    print(f"\n▶ L3 강공고 {len(l3)}건")
    for row in l3[:10]:
        print(f"  [{row.get('우선순위등급')}] {row.get('공고명','')[:40]}")
        print(f"      마감: {row.get('마감일','')}  예산: {row.get('예산','')}  적합도: {row.get('적합도점수','')}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 8 — 선택] 특정 사이트만 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 원하는 사이트만 빠르게 테스트할 때 사용 (상세 페이지 제외 → 빠름)
# os.environ["INTERX_FETCH_DETAIL"] = "false"  # 목록만 수집 (빠름)
#
# result = run_engine.main(
#     site_keys     = ["bipa", "nipa"],
#     max_pages     = 1,
#     enable_sheets = False,
#     no_alert      = True,
# )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [셀 9 — 선택] Dry-run (실제 수집 없이 파이프라인 테스트)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# result = run_engine.main(
#     dry_run       = True,
#     enable_sheets = False,
#     no_alert      = True,
# )
