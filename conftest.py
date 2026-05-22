"""
Root conftest.py — pytest가 자동 로드.
pyproject.toml의 pythonpath = ["src"] 설정과 함께
sys.path에 src/ 를 추가하여 모든 테스트에서 import 가능.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
