# =============================================================================
# InterX Government Intelligence Engine — main.py
# Colab 진입점 (Google Colab에서 exec(open("main.py").read()) 로 실행)
#
# 실제 엔진은 run_engine.py에 있으며, 이 파일은 아래만 수행합니다:
#   1. sys.path에 프로젝트 루트를 등록
#   2. run_engine.main() 호출
#
# Colab 사용법:
#   import os
#   os.chdir("/content/drive/MyDrive/interx_gov_intelligence")
#   exec(open("main.py").read())
#
# CLI 사용법 (로컬):
#   python run_engine.py [--sites bizinfo,bipa] [--max-pages 3] [--no-sheets]
# =============================================================================
from __future__ import annotations

import os
import sys
from pathlib import Path

# 프로젝트 루트 결정 (exec() 환경에서는 __file__ 없음 → os.getcwd() 사용)
try:
    _ROOT = Path(__file__).resolve().parent
except NameError:
    _ROOT = Path(os.getcwd())

# sys.path 등록
for _p in [str(_ROOT), str(_ROOT / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# run_engine.py 동적 로드
import importlib.util as _ilu

_engine_path = _ROOT / "run_engine.py"
_spec = _ilu.spec_from_file_location("run_engine", _engine_path)
_mod  = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 공개 API 노출
main                = _mod.main
build_collectors    = _mod.build_collectors
build_sheet_gateway = _mod.build_sheet_gateway

# 자동 실행 (exec() 또는 python main.py 모두 처리)
if __name__ == "__main__":
    main()
