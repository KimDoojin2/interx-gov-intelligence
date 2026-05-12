from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from interx_engine.application.ports.sheet_gateway_port import SheetGatewayPort

log = logging.getLogger("interx.sheets.console")


class ConsoleSheetGateway(SheetGatewayPort):
    """Google Sheets 연결 불가 시 콘솔에 출력하는 Fallback"""

    def append_rows(self, worksheet_name: str, rows: List[Dict[str, Any]]) -> None:
        log.info("[Console Sheet] %s ← %d rows", worksheet_name, len(rows))
        if rows:
            log.debug(json.dumps(rows[0], ensure_ascii=False, default=str)[:200])

    def append_row(self, worksheet_name: str, row: Dict[str, Any]) -> None:
        self.append_rows(worksheet_name, [row])

    def replace_rows(self, worksheet_name: str, rows: List[Dict[str, Any]]) -> None:
        log.info("[Console Sheet] REPLACE %s ← %d rows", worksheet_name, len(rows))

    def upsert_rows_by_execution_id(
        self,
        worksheet_name: str,
        rows: List[Dict[str, Any]],
        execution_id: str,
        key_col: str = "실행ID",
    ) -> None:
        log.info("[Console Sheet] UPSERT %s ← %d rows (exec=%s)", worksheet_name, len(rows), execution_id)

    def get_header(self, worksheet_name: str) -> List[str]:
        return []
