"""
InterX 대시보드 실행 스크립트
사용법: python scripts/run_dashboard.py
또는:   streamlit run src/interx_engine/interfaces/dashboard/app.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
APP  = ROOT / "src" / "interx_engine" / "interfaces" / "dashboard" / "app.py"

# PYTHONPATH 설정
env = os.environ.copy()
env["PYTHONPATH"] = str(ROOT / "src")

cmd = [
    sys.executable, "-m", "streamlit", "run",
    str(APP),
    "--server.port=8501",
    "--server.headless=false",
    "--browser.gatherUsageStats=false",
]
print(f"대시보드 시작: http://localhost:8501")
print(f"앱 경로: {APP}")
subprocess.run(cmd, env=env)
