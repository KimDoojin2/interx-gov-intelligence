"""
설정 포트 — application 계층이 infrastructure 설정에 직접 의존하지 않도록
기본값 내장형 헬퍼 함수로 제공. 설정 파일 로드 실패 시 안전한 기본값 반환.
"""
from __future__ import annotations


def get_setting(method_name: str, default):
    """settings_loader의 메서드를 안전하게 호출. 실패 시 default 반환."""
    try:
        from interx_engine.infrastructure.config.settings_loader import settings
        return getattr(settings, method_name)()
    except Exception:
        return default


def sim_threshold() -> float:
    return get_setting("sim_threshold", 0.82)


def urgent_dday() -> int:
    return get_setting("urgent_dday", 7)



def summarize_enabled() -> bool:
    return get_setting("summarize_enabled", False)


def db_path() -> str:
    return get_setting("db_path", "data/interx_engine.db")


def collector_timeout_sec() -> int:
    return get_setting("collector_timeout_sec", 20)


def fetch_detail() -> bool:
    return get_setting("fetch_detail", True)


def retry_total() -> int:
    return get_setting("retry_total", 3)


def retry_backoff() -> float:
    return get_setting("retry_backoff", 1.0)


def retry_status_codes() -> list:
    return get_setting("retry_status_codes", [429, 500, 502, 503, 504])


def project_root() -> str:
    return get_setting("project_root", str(__import__("pathlib").Path.cwd()))


def top_k() -> int:
    return get_setting("top_k", 3)
