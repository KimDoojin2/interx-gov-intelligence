import os
from typing import List, Dict
from config.settings import SPREADSHEET_NAME, BASE_DIR

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

class SheetClient:
    def __init__(self):
        self.client = None
        self.sheet = None  # 속성 에러 방지
        key_path = BASE_DIR / "service_account.json"
        
        if not GSPREAD_AVAILABLE:
            print("⚠️ [Sheets] gspread 라이브러리가 설치되지 않았습니다.")
            return
            
        if not key_path.exists():
            print("⚠️ [Sheets] service_account.json 파일이 없어 구글 시트 연동을 건너뜁니다.")
            return
            
        try:
            # 💡 권한 범위(Scopes)에 드라이브(drive) 권한 추가! (403 에러 해결)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(str(key_path), scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open(SPREADSHEET_NAME)
        except Exception as e:
            print(f"❌ [Sheets] 인증 실패: {e}")

    def append_data(self, sheet_name: str, rows: List[Dict]):
        # client나 sheet가 정상적으로 로드되지 않았으면 깔끔하게 종료
        if not self.client or not self.sheet or not rows: 
            return
        
        try:
            worksheet = self.sheet.worksheet(sheet_name)
            values = [list(row.values()) for row in rows]
            worksheet.append_rows(values, value_input_option="USER_ENTERED")
            print(f"✅ [Sheets] '{sheet_name}' 시트에 {len(rows)}건 추가 완료!")
        except Exception as e:
            print(f"❌ [Sheets] 저장 실패 ({sheet_name}): {e}")
