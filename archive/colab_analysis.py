"""
InterX BD Intelligence — 포트폴리오 분석 Colab 실행 셀
======================================================
이 파일을 Colab에 붙여넣고 순서대로 실행하세요.
"""

# ══ 셀 1: 라이브러리 설치 ═════════════════════════════════════════════════════
"""
!pip install -q wordcloud matplotlib
!apt-get install -y -q fonts-nanum
"""

# ══ 셀 2: 분석 실행 ══════════════════════════════════════════════════════════
import sys
from pathlib import Path

ROOT    = Path("/content/drive/MyDrive/interx_gov_intelligence")
SA_PATH = str(ROOT / "service_account.json")
sys.path.insert(0, str(ROOT / "src"))

from interx_engine.interfaces.analysis.portfolio_analysis import run_all

results = run_all(
    sheet_name = "InterX_BD_CRM_v10",   # ← 실제 스프레드시트 이름으로 변경
    sa_path    = SA_PATH,
)

# ══ 셀 3: 수주가능성 Top 20 확인 ══════════════════════════════════════════════
results["predicted"].head(20)

# ══ 셀 4: 클러스터별 공고 확인 ════════════════════════════════════════════════
if "cluster_label" in results["clustered"].columns:
    results["clustered"].groupby("cluster_label")[["공고명","사이트","우선순위등급"]].apply(
        lambda x: x.head(3)
    )

# ══ 셀 5: 분석 이미지 Drive 저장 ══════════════════════════════════════════════
"""
import shutil
for f in ["analysis_1_timeseries.png","analysis_2_wordcloud.png",
          "analysis_3_clustering.png","analysis_4_win_prediction.png"]:
    if Path(f).exists():
        shutil.copy(f, str(ROOT / f"analysis/{f}"))
        print(f"✅ Drive 저장: {f}")
"""
