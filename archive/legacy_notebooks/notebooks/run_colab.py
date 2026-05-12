"""
Google Colab 실행 스크립트
Google Drive에서 프로젝트 마운트 후 실행

# Colab에서 실행 방법:
# 1. 이 파일을 Google Drive에 업로드
# 2. 아래 셀을 순서대로 실행

# ── Cell 1: Drive 마운트 ─────────────────────────────────────────────────────
from google.colab import drive
drive.mount('/content/drive')

# ── Cell 2: 경로 설정 & 패키지 설치 ─────────────────────────────────────────
import subprocess, sys, os
from pathlib import Path

PROJECT = Path('/content/drive/MyDrive/interx_gov_intelligence')
sys.path.insert(0, str(PROJECT / 'src'))

os.environ['INTERX_SA_JSON']    = str(PROJECT / 'service_account.json')
os.environ['INTERX_DB_PATH']    = str(PROJECT / 'data/interx_engine.db')
os.environ['INTERX_ATT_DIR']    = str(PROJECT / 'data/attachments')
os.environ['INTERX_LOG_DIR']    = str(PROJECT / 'logs')
os.environ['INTERX_MAX_PAGES']  = '3'   # Colab은 3페이지로 제한
os.environ['INTERX_WORKERS']    = '4'

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r',
                str(PROJECT / 'requirements.txt')])
print('패키지 설치 완료')

# ── Cell 3: 파이프라인 실행 ──────────────────────────────────────────────────
import sys
sys.path.insert(0, str(PROJECT / 'src'))

from run_engine import main   # noqa — run_engine.py를 sys.path에서 찾음

# 특정 사이트만 실행하려면: site_keys=['bizinfo', 'bipa', 'uipa']
result = main(max_pages=3, enable_sheets=True)
print(f"수집 완료: {result.get('notice_count', 0)}건")
print(f"L3 강공고: {len(result.get('l3_rows', []))}건")
print(f"파트너 후보: {len(result.get('partner_rows', []))}건")

# ── Cell 4: 대시보드 실행 (ngrok 터널링) ─────────────────────────────────────
# !pip install -q pyngrok streamlit
# from pyngrok import ngrok
# import subprocess, os
# os.environ['PYTHONPATH'] = str(PROJECT / 'src')
# proc = subprocess.Popen([
#     'streamlit', 'run', str(PROJECT / 'src/interx_engine/interfaces/dashboard/app.py'),
#     '--server.port=8501', '--server.headless=true'
# ])
# public_url = ngrok.connect(8501)
# print(f'대시보드: {public_url}')
"""
