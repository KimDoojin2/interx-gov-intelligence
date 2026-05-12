# orphaned_root — 루트 레벨 고아 파일 보관소

이 디렉토리의 파일들은 리팩토링 과정에서 src/ 아래 올바른 위치로 이전됐거나
더 이상 파이프라인에서 참조되지 않는 구 버전 파일입니다.

| 파일 | 이전된 위치 | 비고 |
|------|------------|------|
| `score_notices.py` | `src/interx_engine/application/use_cases/score_notices.py` | 구 버전, 임계값 74/54 방식 |
| `priority_scoring_policy.py` | `src/interx_engine/core/rules/priority_scoring_policy.py` | 구 버전 (다른 인터페이스) |
| `l3_strong_policy.py` | `src/interx_engine/core/rules/l3_strong_policy.py` | 구 버전 |
| `scoring.yaml` | `configs/scoring.yaml` | 루트 버전은 orphaned |
| `l3_rules.yaml` | `configs/scoring.yaml`으로 통합 | 임계값 74/54 → configs/scoring.yaml 반영 완료 |
| `keywords_profile.yaml` | `src/.../priority_scoring_policy.py` 내 하드코딩으로 대체 | |
