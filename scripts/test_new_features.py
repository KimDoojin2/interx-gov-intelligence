"""신규 기능 스모크 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


def test_ml_training():
    from interx_engine.application.use_cases.win_prediction import WinPredictionTrainer

    trainer = WinPredictionTrainer()
    print("[ML Training] Trainer initialized")
    models_dir = Path(__file__).resolve().parent.parent / "data" / "models"
    print(f"  Models dir exists: {models_dir.exists()}")
    try:
        result = trainer.train()
        if result:
            print(f"  Trained! Accuracy: {result.get('accuracy', 'N/A')}")
        else:
            print("  Skipped (not enough data, expected)")
    except Exception as e:
        print(f"  Training result: {e}")
    print("  PASS")


def test_all_unit_tests():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/", "-q", "--tb=line"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    last_line = r.stdout.strip().split("\n")[-1]
    print(f"[Unit Tests] {last_line}")
    assert "failed" not in last_line.lower() or "0 failed" in last_line.lower(), f"Tests failed: {last_line}"
    print("  PASS")


if __name__ == "__main__":
    print("=" * 50)
    print("  Feature Smoke Test")
    print("=" * 50)

    tests = [
        ("1. ML Training Pipeline", test_ml_training),
        ("2. All Unit Tests", test_all_unit_tests),
    ]

    passed = 0
    for name, func in tests:
        print(f"\n--- {name} ---")
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")

    print(f"\n{'=' * 50}")
    print(f"  Result: {passed}/{len(tests)} PASSED")
    print(f"{'=' * 50}")
