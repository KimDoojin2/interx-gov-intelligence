"""
InterX REST API — FastAPI 앱 팩토리.
개발팀이 바로 프론트엔드에 연결할 수 있는 엔드포인트 제공.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# ── src 경로 등록 ──────────────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_root.parent / ".env", override=False)
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from interx_engine.api.routes import router

log = logging.getLogger("interx.api")

app = FastAPI(
    title="InterX Government Intelligence API",
    version="5.9.0",
    description="정부지원사업 공고 수집·점수화·분류 엔진 REST API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — 개발 중에는 전체 허용, 프로덕션에서 환경변수로 제한
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    """헬스체크 엔드포인트."""
    return {"status": "ok", "version": "5.9.0"}
