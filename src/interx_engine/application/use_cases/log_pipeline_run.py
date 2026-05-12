from __future__ import annotations
from datetime import datetime

class LogPipelineRunUseCase:
    def __init__(self, sheet_gateway):
        self.sheet_gateway = sheet_gateway

    def execute(self, execution_id: str, notices, result: dict):
        if not self.sheet_gateway:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        run_rows = [{
            "실행ID": execution_id,
            "실행시각": now,
            "단계": "daily_pipeline",
            "상태": "SUCCESS",
            "메시지": f"notice={result.get('notice_count',0)}, download={result.get('download_summary',{})}, parse={result.get('parse_summary',{})}",
        }]
        self.sheet_gateway.upsert_rows_by_execution_id("94_실행로그", run_rows, execution_id)

        site_count = {}
        for n in notices:
            site_count[n.site] = site_count.get(n.site, 0) + 1
        collect_rows = []
        for site, cnt in site_count.items():
            collect_rows.append({
                "실행ID": execution_id, "사이트": site, "수집건수": cnt,
                "성공여부": "Y", "메시지": "수집 완료", "실행시각": now,
            })
        if collect_rows:
            self.sheet_gateway.upsert_rows_by_execution_id("95_수집로그", collect_rows, execution_id)

        err_rows = []
        for n in notices:
            for att in getattr(n, "attachment_items", []) or []:
                if att.get("download_status") == "failed":
                    err_rows.append({
                        "실행ID": execution_id, "사이트": n.site, "공고ID": n.notice_id,
                        "에러유형": "attachment_download", "에러메시지": att.get("download_error", "")[:400],
                        "실행시각": now,
                    })
                if att.get("parsing_status") == "failed":
                    err_rows.append({
                        "실행ID": execution_id, "사이트": n.site, "공고ID": n.notice_id,
                        "에러유형": "attachment_parse", "에러메시지": att.get("parsing_error", "")[:400],
                        "실행시각": now,
                    })
        if err_rows:
            self.sheet_gateway.upsert_rows_by_execution_id("96_수집에러로그", err_rows, execution_id)
