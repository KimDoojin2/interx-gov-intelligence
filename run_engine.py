# =============================================================================
# InterX Government Intelligence Engine - run_engine.py
# 단일 진입점 (v4.5) — run_pipeline.py 기능 통합
#
# 실행 방법:
#   python run_engine.py                            # 전체 사이트, daily 파이프라인
#   python run_engine.py --sites bizinfo,bipa,uipa  # 특정 사이트
#   python run_engine.py --max-pages 3              # 페이지 수 제한
#   python run_engine.py --no-sheets                # Sheets 비활성화
#   python run_engine.py --full                     # Full 파이프라인 (클러스터·알림 포함)
#   python run_engine.py --dry-run                  # Mock 데이터로 테스트 실행
#   python run_engine.py --no-alert                 # 알림 전송 비활성화
#
#   대시보드:
#   streamlit run src/interx_engine/interfaces/dashboard/app.py
# =============================================================================

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys

# Windows 콘솔 UTF-8 강제 (em-dash 등 BMP 문자 깨짐 방지)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── sys.path 설정 (src 디렉토리 추가) ─────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# ── .env 로드 (선택) ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# ── 설정 싱글턴 (환경변수 우선) ───────────────────────────────────────────────
from interx_engine.infrastructure.config.settings_loader import settings  # noqa: E402
settings.ensure_dirs()


# ── 로거 ─────────────────────────────────────────────────────────────────────
def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("interx")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(
        Path(settings.log_dir) / f"interx_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


log = _setup_logger()


# ── 콜렉터 빌드 (collector_factory 위임) ─────────────────────────────────────
def build_collectors(site_keys: list[str] | None, max_pages: int, dry_run: bool = False) -> list:
    if dry_run:
        from interx_engine.infrastructure.collectors.sites.mock_notice_collector import MockNoticeCollector
        log.info("DRY RUN: MockNoticeCollector 사용")
        return [MockNoticeCollector()]

    from interx_engine.infrastructure.collectors.collector_factory import build_collectors as _build
    return _build(site_keys, max_pages)


# ── Google Sheets 게이트웨이 ──────────────────────────────────────────────────
def build_sheet_gateway(enable: bool = True):
    if not enable:
        log.info("Google Sheets 비활성화")
        return None
    try:
        from interx_engine.infrastructure.sheets.google_sheet_gateway import GoogleSheetGateway
        gw = GoogleSheetGateway(
            spreadsheet_name=settings.spreadsheet_name,
            service_account_json=settings.service_account,
            sheets_config_path=settings.sheets_config_path,
        )
        log.info("Google Sheets 연결: %s", settings.spreadsheet_name)
        return gw
    except Exception as e:
        err = str(e)
        if "invalid_grant" in err or "account not found" in err:
            log.error("=" * 60)
            log.error("Google Sheets 인증 실패 — service_account.json 재발급 필요")
            log.error("   1. GCP Console → IAM & Admin → Service Accounts")
            log.error("   2. 서비스 계정 선택 → Keys → Add Key → JSON 다운로드")
            log.error("   3. 파일을 %s 로 교체", settings.service_account)
            log.error("   4. 스프레드시트에 서비스 계정 이메일 편집자 권한 부여")
            log.error("=" * 60)
        elif "not found" in err.lower() or "does not exist" in err.lower():
            log.error("스프레드시트 '%s' 를 찾을 수 없음 — INTERX_SHEET_NAME 확인",
                      settings.spreadsheet_name)
        else:
            log.warning("Google Sheets 연결 실패 (%s)", e)
        log.warning("→ 콘솔 fallback 모드로 실행 (시트 업로드 없음)")
        from interx_engine.infrastructure.sheets.console_sheet_gateway import ConsoleSheetGateway
        return ConsoleSheetGateway()


# ── 멀티콜렉터 어댑터 ────────────────────────────────────────────────────────
class MultiCollectorAdapter:
    def __init__(self, collectors: list, max_workers: int = 8):
        self.collectors  = collectors
        self.max_workers = max_workers
        self.last_errors: list = []

    def _collect_with_retry(self, col, execution_id: str, max_retries: int = 2) -> list:
        import time
        site = getattr(col, "site_key", repr(col))
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                return col.collect(execution_id)
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    log.warning("[Retry] %-12s 실패 (attempt %d/%d), %ds 후 재시도: %s",
                                site, attempt + 1, max_retries + 1, wait, e)
                    time.sleep(wait)
        raise last_exc  # type: ignore

    def collect(self, execution_id: str) -> list:
        if not self.collectors:
            return []
        all_notices: list = []
        self.last_errors  = []
        n = min(len(self.collectors), self.max_workers)
        _PER_SITE_TIMEOUT = getattr(settings, "collector_timeout", 60) * 6
        _GLOBAL_TIMEOUT   = max(300, len(self.collectors) * 20)  # 사이트당 최소 20초 보장

        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = {ex.submit(self._collect_with_retry, c, execution_id): c
                       for c in self.collectors}
            try:
                for fut in as_completed(futures, timeout=_GLOBAL_TIMEOUT):
                    col  = futures[fut]
                    site = getattr(col, "site_key", repr(col))
                    try:
                        notices = fut.result(timeout=_PER_SITE_TIMEOUT)
                        all_notices.extend(notices)
                        log.info("[Collect] %-12s %d건", site, len(notices))
                    except Exception as e:
                        log.error("[Collect] %s 최종 실패: %s", site, e)
                        self.last_errors.append({
                            "site":          site,
                            "error_type":    type(e).__name__,
                            "error_message": str(e)[:300],
                        })
            except TimeoutError:
                # 전체 타임아웃 — 미완료 futures를 에러로 기록하고 계속 진행
                for fut, col in futures.items():
                    if not fut.done():
                        site = getattr(col, "site_key", repr(col))
                        log.warning("[Collect] %-12s 전체 타임아웃 → 건너뜀", site)
                        fut.cancel()
                        self.last_errors.append({
                            "site":          site,
                            "error_type":    "TimeoutError",
                            "error_message": f"전체 수집 타임아웃 ({_GLOBAL_TIMEOUT}s)",
                        })
        return all_notices


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main(
    site_keys: list[str] | None = None,
    max_pages: int | None = None,
    enable_sheets: bool = True,
    full_pipeline: bool = False,
    dry_run: bool = False,
    no_alert: bool = False,
) -> dict:
    max_pages = max_pages or settings.max_pages
    execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")

    # 알림 비활성화
    if no_alert:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("SLACK_WEBHOOK_URL",  None)

    log.info("=" * 60)
    log.info("InterX Government Intelligence Engine v4.5")
    log.info("execution_id  = %s", execution_id)
    log.info("대상 사이트   = %s", site_keys or "전체")
    log.info("max_pages     = %d", max_pages)
    log.info("full_pipeline = %s", full_pipeline)
    log.info("dry_run       = %s", dry_run)
    log.info("=" * 60)

    collectors = build_collectors(site_keys, max_pages, dry_run=dry_run)
    if not collectors:
        log.error("사용 가능한 수집기가 없습니다.")
        return {}

    multi_collector = MultiCollectorAdapter(collectors, settings.max_workers)
    sheet_gateway   = build_sheet_gateway(enable_sheets)

    if full_pipeline:
        from interx_engine.application.orchestrators.full_pipeline import FullPipelineOrchestrator
        orchestrator = FullPipelineOrchestrator(
            collector=multi_collector,
            base_dir=str(ROOT),
            sheet_gateway=sheet_gateway,
        )
    else:
        from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
        orchestrator = DailyPipelineOrchestrator(
            collector=multi_collector,
            sheet_gateway=sheet_gateway,
        )

    result = orchestrator.run(execution_id)

    # ── 결과 요약 출력 ────────────────────────────────────────────────────────
    skip = {"master_rows", "score_cards", "notices", "attachment_rows",
            "doc_mgmt_rows", "pipeline_rows", "score_model_rows"}
    print("\n" + "=" * 60)
    print("=== FINAL RESULT ===")
    print(json.dumps(
        {k: v for k, v in result.items() if k not in skip},
        ensure_ascii=False, indent=2, default=str,
    ))
    print("=" * 60)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="InterX Government Intelligence Engine v4.5",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--sites", type=str, default=None,
        help="수집 사이트 (쉼표 구분)\n예: bizinfo,bipa,uipa,iris,kiat,smba,nipa\n기본: 전체",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help=f"사이트당 최대 페이지 수 (기본: {settings.max_pages})",
    )
    parser.add_argument(
        "--no-sheets", action="store_true",
        help="Google Sheets 비활성화 (콘솔 출력만)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Full 파이프라인 실행 (클러스터링·파트너매칭·알림 포함)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mock 데이터로 실행 (수집 없이 파이프라인 테스트)",
    )
    parser.add_argument(
        "--no-alert", action="store_true",
        help="알림 전송 비활성화 (Telegram/Slack 환경변수 무시)",
    )
    parser.add_argument(
        "--no-detail", action="store_true",
        help="상세 페이지 방문 생략 (목록만 수집, 빠른 실행)",
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="파이프라인 완료 후 Streamlit 대시보드 자동 실행",
    )
    args = parser.parse_args()

    # --no-detail 플래그 → 환경변수로 전달 (BaseCollector가 참조)
    if args.no_detail:
        os.environ["INTERX_FETCH_DETAIL"] = "false"

    main(
        site_keys=[s.strip() for s in args.sites.split(",")] if args.sites else None,
        max_pages=args.max_pages,
        enable_sheets=not args.no_sheets,
        full_pipeline=args.full,
        dry_run=args.dry_run,
        no_alert=args.no_alert,
    )

    if args.dashboard:
        _launch_dashboard(ROOT)


def _launch_dashboard(root: Path) -> None:
    """파이프라인 완료 후 Streamlit 대시보드 실행. Colab에서는 pyngrok URL 출력."""
    import subprocess, sys as _sys

    dashboard_py = root / "src" / "interx_engine" / "interfaces" / "dashboard" / "app.py"
    port = 8501

    # Colab 여부 감지
    try:
        import google.colab  # noqa: F401
        _is_colab = True
    except ImportError:
        _is_colab = False

    cmd = [
        _sys.executable, "-m", "streamlit", "run", str(dashboard_py),
        f"--server.port={port}",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]

    log.info("[Dashboard] 대시보드 기동 중... (port=%d)", port)
    subprocess.Popen(cmd, cwd=str(root))

    import time as _t
    _t.sleep(3)   # streamlit 기동 대기

    if _is_colab:
        print("\n" + "=" * 60)
        try:
            from pyngrok import ngrok  # type: ignore
            ngrok.set_auth_token(os.getenv("NGROK_TOKEN", ""))
            public_url = ngrok.connect(port)
            print(f"🌐 대시보드 공개 URL : {public_url}")
        except ImportError:
            print("pyngrok 미설치 — 아래 셀 실행 후 재시도:")
            print("  !pip install -q pyngrok")
            print("  import pyngrok; pyngrok.ngrok.set_auth_token('YOUR_TOKEN')")
            # Colab 내장 프록시 시도
            try:
                from google.colab.output import eval_js  # type: ignore
                url = eval_js(f"google.colab.kernel.proxyPort({port})")
                print(f"🌐 Colab 프록시 URL : {url}")
            except Exception:
                print(f"🌐 포트 {port} 에서 실행 중 (터널 설정 필요)")
        print("=" * 60 + "\n")
    else:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        print(f"\n🌐 대시보드: http://localhost:{port}\n")
