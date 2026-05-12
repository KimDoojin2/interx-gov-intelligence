from datetime import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.append(str(SRC_ROOT))

from interx_engine.application.orchestrators.daily_pipeline import DailyPipelineOrchestrator
from interx_engine.application.use_cases.download_attachments import DownloadAttachmentsUseCase
from interx_engine.application.use_cases.parse_documents import ParseDocumentsUseCase
from interx_engine.application.use_cases.log_pipeline_run import LogPipelineRunUseCase
from interx_engine.infrastructure.collectors.collector_factory import build_collector
from interx_engine.infrastructure.sheets.google_sheet_gateway import GoogleSheetGateway
from interx_engine.infrastructure.storage.file_downloader import FileDownloader
from interx_engine.infrastructure.config.settings_loader import load_settings
from interx_engine.infrastructure.persistence.sqlite_writer import SQLitePipelineWriter

def main():
    execution_id = datetime.now().strftime("EXEC-%Y%m%d-%H%M%S")
    settings = load_settings(str(PROJECT_ROOT / "configs" / "settings.yaml"))
    p = settings.get("pipeline", {})
    s = settings.get("storage", {})

    source_site = p.get("source_site", "bizinfo")
    download_mode = p.get("download_mode", "best_effort")
    parse_mode = p.get("parse_mode", "best_effort")
    max_pages = int(p.get("max_pages", 3))
    backend = s.get("backend", "sheets")
    sqlite_path = s.get("sqlite_path", str(PROJECT_ROOT / "data" / "interx_pipeline.db"))

    collector = build_collector(source_site=source_site, max_pages=max_pages, timeout=45)

    sheet_gateway = None
    if backend in ("sheets", "dual"):
        sheet_gateway = GoogleSheetGateway(
            spreadsheet_name="InterX_BD_CRM_v10_fresh_template",
            service_account_json="/content/drive/MyDrive/Colab Notebooks/service_account.json",
            sheets_config_path=str(PROJECT_ROOT / "configs" / "sheets.yaml"),
        )

    download_uc = None
    if download_mode != "off" and hasattr(collector, "session"):
        download_uc = DownloadAttachmentsUseCase(
            downloader=FileDownloader(timeout=90, session=collector.session),
            base_dir=str(PROJECT_ROOT / "data" / "attachments"),
        )

    parse_uc = ParseDocumentsUseCase(max_chars=3000) if parse_mode != "off" else None

    result = DailyPipelineOrchestrator(
        collector=collector,
        sheet_gateway=sheet_gateway,
        attachment_download_use_case=download_uc,
        document_parse_use_case=parse_uc,
    ).run(execution_id=execution_id)

    if sheet_gateway:
        LogPipelineRunUseCase(sheet_gateway).execute(execution_id, result.get("notices", []), result)

    if backend in ("sqlite", "dual"):
        SQLitePipelineWriter(sqlite_path).save(execution_id, source_site, result)

    print("\n=== PIPELINE RESULT ===")
    print(f"execution_id={execution_id}")
    print(f"source_site={source_site}")
    print(f"storage_backend={backend}")
    print(f"notice_count={result['notice_count']}")
    print(f"score_count={result['score_count']}")
    print(f"l3_rows={len(result.get('l3_rows', []))}")
    print(f"partner_rows={len(result.get('partner_rows', []))}")
    print(f"download_summary={result['download_summary']}")
    print(f"parse_summary={result['parse_summary']}")
    print(f"pipeline_rows={len(result.get('pipeline_rows', []))}")
    print(f"score_model_rows={len(result.get('score_model_rows', []))}")
    print(f"summary_rows={len(result.get('summary_rows', []))}, exec_rows={len(result.get('exec_rows', []))}, kpi_rows={len(result.get('kpi_rows', []))}")
    print("master upload complete")

if __name__ == "__main__":
    main()
