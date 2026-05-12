import os
from pathlib import Path

BASE_DIR = Path("/content/drive/MyDrive/interx_gov_intelligence")
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

MAX_PAGES = int(os.getenv("INTERX_MAX_PAGES", "5"))
COLLECTOR_TIMEOUT = int(os.getenv("INTERX_TIMEOUT", "15"))
MAX_WORKERS = int(os.getenv("INTERX_WORKERS", "8"))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DB_PATH = str(DATA_DIR / "interx_engine.db")
SPREADSHEET_NAME = os.getenv("INTERX_SHEET_NAME", "InterX_BD_CRM_v10_fresh_template")

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
