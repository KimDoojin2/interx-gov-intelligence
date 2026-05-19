"""
ML 수주예측 모델 학습 스크립트
실행: venv/Scripts/python scripts/train_win_model.py

데이터 소스 (우선순위 순):
  1. data/crm_memos.json — 영업팀 수주/탈락 결과
  2. data/exports/training/*.jsonl — 파이프라인 자동 Export
  3. data/interx_engine.db — SQLite 누적 데이터 (A/B→수주, C/D→탈락 가정)

최소 20건 이상 데이터 필요. 부족 시 안내 메시지 출력.
"""
import sys
from pathlib import Path

# 프로젝트 루트 경로 설정
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from interx_engine.application.use_cases.win_prediction import WinPredictionTrainer


def main():
    print("=" * 60)
    print("  InterX Win Prediction Model Training")
    print("=" * 60)

    trainer = WinPredictionTrainer()
    model_path = ROOT / "data" / "models" / "win_pred_lr.pkl"

    print(f"\n[1/3] Checking data sources...")
    print(f"  - CRM memos:  data/crm_memos.json")
    print(f"  - JSONL:       data/exports/training/*.jsonl")
    print(f"  - SQLite:      data/interx_engine.db")

    print(f"\n[2/3] Training model...")
    try:
        result = trainer.train()
        if result:
            print(f"\n[3/3] Model saved!")
            print(f"  - Path:     {model_path}")
            print(f"  - Accuracy: {result.get('accuracy', 'N/A')}")
            print(f"  - Samples:  {result.get('n_samples', 'N/A')}")
            print(f"  - Features: {result.get('feature_names', [])}")
            print(f"\n  Next pipeline run will auto-switch to ML mode.")
        else:
            print(f"\n[SKIP] Training skipped.")
            print(f"  Likely not enough data (min 20 samples).")
            print(f"  Current data can be boosted by:")
            print(f"    1. Running more pipeline cycles (dry-run counts)")
            print(f"    2. Adding CRM memos to data/crm_memos.json:")
            print(f'       [{{"notice_id":"XX","result":"수주"}},{{"notice_id":"YY","result":"탈락"}}]')
    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
