"""
launch_dashboard.py  —  Colab + 로컬 겸용 대시보드 런처

Colab 사용법:
    셀 1: 드라이브 마운트 + 디렉토리 이동
        from google.colab import drive; drive.mount('/content/drive')
        %cd /content/drive/MyDrive/interx_gov_intelligence

    셀 2: 패키지 설치
        %pip install -q streamlit pyngrok gspread google-auth \
            scikit-learn plotly pandas openpyxl python-dotenv PyYAML \
            requests beautifulsoup4 lxml

    셀 3: ngrok 토큰 설정 (https://dashboard.ngrok.com 에서 발급)
        import os
        os.environ["NGROK_TOKEN"] = "your_ngrok_token_here"

    셀 4: 대시보드 실행
        %run launch_dashboard.py

로컬 사용법:
    python launch_dashboard.py
    → 브라우저 자동 오픈 http://localhost:8501
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

DASHBOARD = ROOT / "src" / "interx_engine" / "interfaces" / "dashboard" / "app.py"
PORT      = int(os.getenv("DASHBOARD_PORT", "8501"))


def _is_colab() -> bool:
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def _start_streamlit() -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(DASHBOARD),
        f"--server.port={PORT}",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--theme.base=dark",
    ]
    print(f"[Dashboard] streamlit 기동: port={PORT}")
    return subprocess.Popen(cmd, cwd=str(ROOT))


def _ngrok_url() -> str:
    token = os.getenv("NGROK_TOKEN", "")
    try:
        from pyngrok import ngrok, conf  # type: ignore
        if token:
            conf.get_default().auth_token = token
        tunnels = ngrok.get_tunnels()
        for t in tunnels:
            if str(PORT) in t.public_url:
                return t.public_url
        url = ngrok.connect(PORT, "http")
        return str(url.public_url)
    except ImportError:
        return ""


def _colab_proxy_url() -> str:
    try:
        from google.colab.output import eval_js  # type: ignore
        return eval_js(f"google.colab.kernel.proxyPort({PORT})")
    except Exception:
        return ""


def main() -> None:
    proc = _start_streamlit()
    time.sleep(4)  # streamlit 초기화 대기

    print("\n" + "=" * 60)
    print("  InterX BD Intelligence Dashboard")
    print("=" * 60)

    if _is_colab():
        url = _ngrok_url()
        if url:
            print(f"  🌐 공개 URL  : {url}")
        else:
            url = _colab_proxy_url()
            if url:
                print(f"  🌐 Colab URL : {url}")
            else:
                print(f"  ⚠️  pyngrok 미설치 — !pip install pyngrok 후 재실행")
                print(f"     또는 NGROK_TOKEN 환경변수 설정 필요")
        print("\n  데이터 소스 선택:")
        print("  • Google Sheets → 사이드바에서 'Google Sheets' 선택")
        print("  • 로컬 DB      → 사이드바에서 'SQLite (로컬)' 선택")
        print("  • 데모          → 사이드바에서 '데모 데이터' 선택")
    else:
        import webbrowser
        url = f"http://localhost:{PORT}"
        webbrowser.open(url)
        print(f"  🌐 로컬 URL : {url}")

    print("=" * 60)
    print("  종료: Ctrl+C\n")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n[Dashboard] 종료")


if __name__ == "__main__":
    main()
