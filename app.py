# app.py — 루트 레벨 Streamlit 진입점
# 실행: streamlit run app.py
#
# 실제 대시보드는 아래 경로에 있습니다:
#   src/interx_engine/interfaces/dashboard/app.py
# 직접 실행하려면:
#   streamlit run src/interx_engine/interfaces/dashboard/app.py

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from interx_engine.interfaces.dashboard import app  # noqa: F401, E402
