"""
CLI 진입점 — pyproject.toml [project.scripts] 에서 참조.
`pip install -e .` 후 `interx-engine` 명령어로 실행 가능.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # run_engine.py의 로직을 재사용
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    exec(open(root / "run_engine.py").read())


if __name__ == "__main__":
    main()
