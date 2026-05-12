# =============================================================================
# run_pipeline.py — DEPRECATED
# =============================================================================
# 이 파일은 더 이상 사용하지 않습니다.
# run_engine.py 하나로 통합되었습니다.
#
# 이전 명령어 → 대체 명령어
#   python run_pipeline.py                → python run_engine.py --full
#   python run_pipeline.py --dry-run      → python run_engine.py --full --dry-run
#   python run_pipeline.py --no-alert     → python run_engine.py --full --no-alert
#   python run_pipeline.py --no-sheets    → python run_engine.py --full --no-sheets
#   python run_pipeline.py --site bizinfo → python run_engine.py --full --sites bizinfo
# =============================================================================
import sys

raise SystemExit(
    "\n[DEPRECATED] run_pipeline.py는 더 이상 사용하지 않습니다.\n"
    "대신 run_engine.py를 사용하세요:\n"
    "  python run_engine.py --full           # Full 파이프라인\n"
    "  python run_engine.py --full --dry-run # Mock 데이터 테스트\n"
    "  python run_engine.py --help           # 전체 옵션 확인\n"
)
