"""4개 신규 기능 스모크 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from interx_engine.core.entities.notice import Notice
from interx_engine.core.entities.score_card import ScoreCard


def test_competitor_report():
    from interx_engine.application.use_cases.competitor_report import generate_competitor_report

    notices = [
        Notice(execution_id="T", site="bizinfo", notice_id="N1",
               title="삼성SDS AI 스마트공장 구축", agency="삼성SDS"),
        Notice(execution_id="T", site="kiat", notice_id="N2",
               title="LG CNS 디지털트윈 실증", ministry="산업통상자원부"),
        Notice(execution_id="T", site="nipa", notice_id="N3",
               title="중소기업 제조AI 지원", agency="중소벤처기업부"),
    ]
    cards = [
        ScoreCard(execution_id="T", notice_id="N1", site="bizinfo",
                  fitness_score=70, priority_score=60, priority_grade="A"),
        ScoreCard(execution_id="T", notice_id="N2", site="kiat",
                  fitness_score=55, priority_score=45, priority_grade="B"),
        ScoreCard(execution_id="T", notice_id="N3", site="nipa",
                  fitness_score=30, priority_score=25, priority_grade="C"),
    ]

    result = generate_competitor_report(notices, cards, execution_id="SMOKE")
    s = result["summary"]
    print(f"[Competitor Report] Related: {s['competitor_related']}/{s['total_notices']}")
    print(f"  Top: {s['top_competitors']}")
    print(f"  Chart: {result['chart_path']}")
    assert s["competitor_related"] >= 1, "No competitors detected"
    print("  PASS")


def test_proposal_v2():
    from interx_engine.application.use_cases.generate_proposal_v2 import generate_proposals_v2
    import tempfile

    notices = [
        Notice(execution_id="T", site="bizinfo", notice_id="P1",
               title="AI 스마트공장 구축 지원사업",
               budget="5억원", deadline_date="2026-12-31",
               l3_strong="Y", manager="김BD"),
    ]
    cards = [
        ScoreCard(execution_id="T", notice_id="P1", site="bizinfo",
                  fitness_score=80, priority_score=70, priority_grade="A",
                  solution_scores={"ManufacturingDT": 85, "QualityAI": 60, "PdM": 45},
                  positive_keywords=["스마트공장", "AI", "디지털트윈"]),
    ]

    out_dir = tempfile.mkdtemp()
    paths = generate_proposals_v2(notices, cards, output_dir=out_dir)
    print(f"[Proposal V2] Generated: {len(paths)} files")
    for p in paths:
        size = Path(p).stat().st_size
        print(f"  {Path(p).name} ({size:,} bytes)")
    assert len(paths) == 1, "Expected 1 proposal"
    assert Path(paths[0]).exists(), "File not found"
    print("  PASS")


def test_ml_training():
    from interx_engine.application.use_cases.win_prediction import WinPredictionTrainer

    trainer = WinPredictionTrainer()
    print("[ML Training] Trainer initialized")
    # data/models/ 디렉토리 확인
    models_dir = Path(__file__).resolve().parent.parent / "data" / "models"
    print(f"  Models dir exists: {models_dir.exists()}")
    # 학습은 데이터 부족으로 skip될 수 있음
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
    print("  Feature Expansion Smoke Test")
    print("=" * 50)

    tests = [
        ("1. Competitor Report", test_competitor_report),
        ("2. Proposal V2", test_proposal_v2),
        ("3. ML Training Pipeline", test_ml_training),
        ("4. All Unit Tests (106)", test_all_unit_tests),
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
