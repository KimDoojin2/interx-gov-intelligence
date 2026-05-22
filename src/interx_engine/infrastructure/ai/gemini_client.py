"""
Gemini API 클라이언트 — 무료 Tier (Gemini 2.0 Flash).

무료 한도: 15 RPM / 100만 토큰/일 / 1500 RPD
API 키 발급: https://aistudio.google.com/apikey (Google 계정만 있으면 무료)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger("interx.ai.gemini")

_DEFAULT_MODEL = "gemini-2.0-flash"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# ── Rate-limit 관리 (무료: 15 RPM) ──────────────────────────────────────────
_last_call_ts: float = 0
_MIN_INTERVAL = 4.2  # 60/15 = 4초 간격


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "무료 발급: https://aistudio.google.com/apikey"
        )
    return key


def _rate_limit():
    """무료 15 RPM 초과 방지."""
    global _last_call_ts
    now = time.time()
    elapsed = now - _last_call_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_ts = time.time()


def generate(
    prompt: str,
    system_instruction: str = "",
    model: str = _DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> str:
    """
    Gemini API 호출 (REST, 라이브러리 의존 없음).

    Args:
        prompt: 사용자 프롬프트
        system_instruction: 시스템 지시문
        model: 모델명 (기본 gemini-2.0-flash)
        temperature: 창의성 (0~2)
        max_tokens: 최대 출력 토큰
        timeout: 요청 타임아웃 (초)

    Returns:
        생성된 텍스트
    """
    _rate_limit()
    api_key = _get_api_key()

    url = f"{_API_BASE}/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # 응답 파싱
        candidates = data.get("candidates", [])
        if not candidates:
            error_msg = data.get("error", {}).get("message", "응답 없음")
            log.warning("[Gemini] 응답 없음: %s", error_msg)
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return text.strip()

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 0
        if status == 429:
            log.warning("[Gemini] Rate limit 도달 — 잠시 후 재시도")
        elif status == 403:
            log.error("[Gemini] API 키 무효 — GEMINI_API_KEY 확인 필요")
        else:
            log.error("[Gemini] HTTP %d: %s", status, e)
        return ""
    except requests.exceptions.Timeout:
        log.warning("[Gemini] 타임아웃 (%ds)", timeout)
        return ""
    except Exception as e:
        log.error("[Gemini] 요청 실패: %s", e)
        return ""


def is_available() -> bool:
    """Gemini API 키가 설정되어 있는지 확인."""
    return bool(os.getenv("GEMINI_API_KEY", ""))
