"""
InterX 설정 로더 — 단일 진입점
우선순위: 환경변수 > .env > configs/settings.yaml > 기본값
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("interx.config")


def _find_project_root() -> Path:
    """이 파일 위치에서 위쪽으로 올라가며 configs/ 디렉토리가 있는 루트 탐색."""
    here = Path(__file__).resolve()
    for _ in range(8):
        if (here / "configs").is_dir():
            return here
        here = here.parent
    # fallback: cwd
    return Path.cwd()


PROJECT_ROOT: Path = Path(os.getenv("INTERX_PROJECT_ROOT", str(_find_project_root())))


def load_yaml(rel_path: str) -> dict:
    """configs/ 하위 yaml 파일 로드. 실패 시 빈 dict."""
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        log.debug("설정 파일 없음: %s", p)
        return {}
    try:
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        log.warning("설정 로드 실패 [%s]: %s", p, e)
        return {}


class Settings:
    """
    환경변수 + yaml config 통합 설정 객체.
    외부에서 `from interx_engine.infrastructure.config.settings_loader import settings` 로 import.
    """

    def __init__(self) -> None:
        # ── 환경변수 (최우선) ──────────────────────────────────────────────────
        self.project_root       = PROJECT_ROOT
        self.spreadsheet_name   = os.getenv("INTERX_SHEET_NAME",  "InterX_BD_CRM_v10_fresh_template")
        self.service_account    = os.getenv("INTERX_SA_JSON",     str(PROJECT_ROOT / "service_account.json"))
        self.db_path            = os.getenv("INTERX_DB_PATH",     str(PROJECT_ROOT / "data" / "interx_engine.db"))
        self.attachment_dir     = os.getenv("INTERX_ATT_DIR",     str(PROJECT_ROOT / "data" / "attachments"))
        self.log_dir            = os.getenv("INTERX_LOG_DIR",     str(PROJECT_ROOT / "logs"))
        self.max_pages          = int(os.getenv("INTERX_MAX_PAGES", "5"))
        self.max_workers        = int(os.getenv("INTERX_WORKERS",   "8"))
        self.collector_timeout  = int(os.getenv("INTERX_TIMEOUT",   "20"))  # yaml로 오버라이드 가능
        self.sheets_config_path = str(PROJECT_ROOT / "configs" / "sheets.yaml")
        self.scoring_config_path = str(PROJECT_ROOT / "configs" / "scoring.yaml")

        # ── yaml configs ───────────────────────────────────────────────────────
        self._cfg      = load_yaml("configs/settings.yaml")
        self._scoring  = load_yaml("configs/scoring.yaml")
        self._sheets   = load_yaml("configs/sheets.yaml")
        self._sites    = load_yaml("configs/sites.yaml")
        self._keywords = load_yaml("configs/keywords_profile.yaml") \
                         or load_yaml("keywords_profile.yaml")

    # ── 편의 접근자 ────────────────────────────────────────────────────────────
    def scoring(self) -> dict:
        return self._scoring

    def l3_threshold(self) -> int:
        return int(self._scoring.get("thresholds", {}).get("l3_strong", 74))

    def partner_threshold(self) -> int:
        return int(self._scoring.get("thresholds", {}).get("partner_candidate", 54))

    def sim_threshold(self) -> float:
        return float(self._cfg.get("dedup", {}).get("sim_threshold", 0.82))

    def top_k(self) -> int:
        return int(self._cfg.get("matching", {}).get("top_k", 3))

    def urgent_dday(self) -> int:
        return int(self._cfg.get("alert", {}).get("urgent_dday", 7))

    def proposal_output_dir(self) -> Path:
        rel = self._cfg.get("proposal", {}).get("output_dir", "data/proposals")
        return self.project_root / rel

    def retry_total(self) -> int:
        return int(self._cfg.get("collector", {}).get("retry_total", 3))

    def retry_backoff(self) -> float:
        return float(self._cfg.get("collector", {}).get("retry_backoff", 1.0))

    def retry_status_codes(self) -> list:
        return list(self._cfg.get("collector", {}).get("retry_status_codes",
                                                        [429, 500, 502, 503, 504]))

    def collector_timeout_sec(self) -> int:
        yaml_val = self._cfg.get("collector", {}).get("timeout", None)
        if yaml_val is not None:
            return int(yaml_val)
        return self.collector_timeout

    def fetch_detail(self) -> bool:
        """상세 페이지 방문 여부. 환경변수 INTERX_FETCH_DETAIL=false 로 끄기 가능."""
        env = os.getenv("INTERX_FETCH_DETAIL", "").lower()
        if env in ("false", "0", "no"):
            return False
        if env in ("true", "1", "yes"):
            return True
        return bool(self._cfg.get("collector", {}).get("fetch_detail", True))

    def detail_workers(self) -> int:
        return int(self._cfg.get("collector", {}).get("detail_workers", 3))

    def summarize_enabled(self) -> bool:
        return bool(self._cfg.get("summarize", {}).get("enabled", True))

    def summarize_model(self) -> str:
        return str(self._cfg.get("summarize", {}).get("model", "claude-haiku-4-5-20251001"))

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def ensure_dirs(self) -> None:
        for d in [self.db_path, self.attachment_dir, self.log_dir]:
            Path(d).parent.mkdir(parents=True, exist_ok=True)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.attachment_dir).mkdir(parents=True, exist_ok=True)


# ── 싱글턴 ────────────────────────────────────────────────────────────────────
settings = Settings()

