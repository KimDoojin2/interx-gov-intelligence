from __future__ import annotations

import logging
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials
import yaml

from interx_engine.application.ports.sheet_gateway_port import SheetGatewayPort

log = logging.getLogger("interx.sheets")

# 유지할 시트 목록 (이 외 나머지는 cleanup 시 삭제)
# BD 베테랑 판단 기준:
#   - 수집/영업 운영: 01, 02, 03, 05
#   - 대시보드/보고: 20
#   - KPI/로그:      22, 93, 94, 96
KEEP_SHEETS = {
    "01_영업기회_정보",   # 핵심 수집 원본
    "01_사업마스터_원본", # 원본 보존용
    "02_L3강공고",        # L3 딜러 필터
    "03_파트너전달",       # 파트너 협업
    "05_긴급마감_공고",   # D-7 긴급 액션
    "20_요약대시보드",    # 경영진/팀 보고
    "22_KPI현황",         # 자동 누적 KPI
    "93_사이트별수집통계", # 수집 품질 모니터링
    "94_실행로그",        # 파이프라인 운영 로그
    "96_수집에러로그",    # 수집 실패 추적
}


class GoogleSheetGateway(SheetGatewayPort):
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(
        self,
        spreadsheet_name: str,
        service_account_json: str,
        sheets_config_path: str,
    ) -> None:
        self.spreadsheet_name     = spreadsheet_name
        self.service_account_json = service_account_json
        self.sheets_config_path   = sheets_config_path

        self._client        = self._build_client()
        self._spreadsheet   = self._client.open(self.spreadsheet_name)
        self._sheets_config = self._load_sheets_config()

    # ── 인증 ──────────────────────────────────────────────────────────────────
    def _build_client(self) -> gspread.Client:
        creds = Credentials.from_service_account_file(
            self.service_account_json, scopes=self.SCOPES
        )
        return gspread.authorize(creds)

    def _load_sheets_config(self) -> dict:
        with open(self.sheets_config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ── 컬럼 해석 ─────────────────────────────────────────────────────────────
    def _resolve_columns(self, worksheet_name: str) -> List[str]:
        sheets = self._sheets_config.get("sheets", {})
        for _, meta in sheets.items():
            if meta.get("name") == worksheet_name:
                if meta.get("columns"):
                    return meta["columns"]
                same_key = meta.get("same_as")
                if same_key and same_key in sheets:
                    return sheets[same_key].get("columns", [])
        return []

    def _dict_to_row(self, columns: List[str], row_dict: Dict[str, Any]) -> List[Any]:
        return [row_dict.get(col, "") for col in columns]

    # ── 워크시트 획득 (없으면 자동 생성) ────────────────────────────────────
    def _ws(self, name: str) -> gspread.Worksheet:
        try:
            return self._spreadsheet.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            log.info("워크시트 자동 생성: %s", name)
            return self._spreadsheet.add_worksheet(title=name, rows=2000, cols=50)

    # ── replace_rows (헤더 + 데이터 전체 교체) ───────────────────────────────
    def replace_rows(self, worksheet_name: str, rows: List[Dict[str, Any]]) -> None:
        ws      = self._ws(worksheet_name)
        columns = self._resolve_columns(worksheet_name)

        if rows:
            if not columns:
                columns = list(rows[0].keys())
            values = [columns] + [self._dict_to_row(columns, r) for r in rows]
        else:
            if not columns:
                ws.clear()
                return
            values = [columns]   # 헤더만 남기고 데이터 행 없음

        try:
            ws.clear()
            # gspread 5.x / 6.x 모두 호환: 명시적 range_name 지정
            ws.update(range_name="A1", values=values,
                      value_input_option="USER_ENTERED")
            log.debug("replace_rows [%s]: %d행 작성", worksheet_name, len(values))
        except Exception as e:
            log.error("replace_rows 실패 [%s]: %s", worksheet_name, e)
            raise

    # ── append_rows ───────────────────────────────────────────────────────────
    def append_rows(self, worksheet_name: str, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        ws      = self._ws(worksheet_name)
        columns = self._resolve_columns(worksheet_name)

        if columns:
            values = [self._dict_to_row(columns, r) for r in rows]
        else:
            values = [list(r.values()) for r in rows]

        try:
            ws.append_rows(values, value_input_option="USER_ENTERED")
        except Exception as e:
            log.error("append_rows 실패 [%s]: %s", worksheet_name, e)
            raise

    def append_row(self, worksheet_name: str, row: Dict[str, Any]) -> None:
        self.append_rows(worksheet_name, [row])

    # ── cleanup: KEEP_SHEETS 외 나머지 시트 삭제 ─────────────────────────────
    def cleanup_old_sheets(self) -> None:
        """KEEP_SHEETS에 없는 모든 워크시트를 삭제한다."""
        worksheets = self._spreadsheet.worksheets()
        # 마지막 1개는 삭제 불가 → 삭제 대상만 추린 뒤 처리
        to_delete = [ws for ws in worksheets if ws.title not in KEEP_SHEETS]

        if not to_delete:
            log.info("cleanup: 삭제할 시트 없음")
            return

        # 먼저 유지 시트가 없으면 기본 시트 1개 만들어두기
        remaining_titles = {ws.title for ws in worksheets} - {ws.title for ws in to_delete}
        if not remaining_titles:
            self._spreadsheet.add_worksheet(title="01_영업기회_정보", rows=2000, cols=50)

        for ws in to_delete:
            try:
                self._spreadsheet.del_worksheet(ws)
                log.info("cleanup: 시트 삭제 → %s", ws.title)
            except Exception as e:
                log.warning("cleanup: %s 삭제 실패 — %s", ws.title, e)

    # ── get_header ───────────────────────────────────────────────────────────
    def get_header(self, worksheet_name: str) -> List[str]:
        return self._ws(worksheet_name).row_values(1)
