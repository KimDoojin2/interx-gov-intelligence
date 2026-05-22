"""python -m interx_engine.api 로 실행 가능."""
from __future__ import annotations

import argparse
import sys


def _cli() -> None:
    parser = argparse.ArgumentParser(description="InterX REST API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="개발 모드 (auto-reload)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("uvicorn 미설치 — pip install 'interx-gov-intelligence[api]'")
        sys.exit(1)

    uvicorn.run(
        "interx_engine.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    _cli()
