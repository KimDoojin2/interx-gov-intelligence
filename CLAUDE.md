# InterX Government Intelligence Engine

## 프로젝트 개요
정부지원사업 공고를 자동 수집·점수화·분류해 Google Sheets CRM에 업로드하는 파이프라인.

## 아키텍처 (클린 아키텍처 기반)
```
src/interx_engine/
├── core/           # 도메인 엔티티 & 비즈니스 규칙 (외부 의존성 없음)
│   ├── entities/   # Notice, Partner, ScoreCard, Cluster 등
│   └── rules/      # 점수 정책, L3 강정책, 추천 규칙
├── application/    # Use Cases, Ports, Orchestrators, Mappers
│   ├── use_cases/  # 각 기능 단위 (score, deduplicate, match_partners 등)
│   ├── ports/      # 외부 연동 인터페이스 (수집, 알림, 시트, 파트너)
│   └── orchestrators/ # daily_pipeline, full_pipeline
└── infrastructure/ # 외부 구현체
    ├── collectors/sites/  # 사이트별 크롤러 (20개+)
    ├── alert/      # Slack, Telegram
    ├── analysis/   # pandas, sklearn
    └── clustering/ # TF-IDF
```

## 설정 파일 (`configs/`)
| 파일 | 역할 |
|---|---|
| `settings.yaml` | 전역 설정, API 키 경로 |
| `scoring.yaml` | 점수 가중치 및 기준 |
| `sites.yaml` | 수집 대상 사이트 목록 |
| `sheets.yaml` | Google Sheets 컬럼 매핑 |
| `manager_rules.yaml` | 담당자 자동 배정 규칙 |
| `competitors.yaml` | 경쟁사 추적 대상 |

## 실행
```bash
# 전체 파이프라인 (유일한 진입점)
venv/Scripts/python run_engine.py

# 옵션 예시
# venv/Scripts/python run_engine.py --full          # FullPipelineOrchestrator
# venv/Scripts/python run_engine.py --dry-run       # 수집만, 시트 미업로드
# venv/Scripts/python run_engine.py --no-alert      # 알림 없이 실행

# 테스트
venv/Scripts/python -m pytest tests/unit/ -v --tb=short
venv/Scripts/python -m pytest tests/ -v
```

## 핵심 규칙
- **도메인 규칙은 `core/`에만** — infrastructure에 비즈니스 로직 넣지 말 것
- **설정값은 `configs/` YAML에** — 코드에 하드코딩 금지
- **각 크롤러는 `base_collector.py` 상속** — `collect()` 메서드 구현
- **Google Sheets 인증**: `service_account.json.json` (루트 디렉토리)
- `venv/` 사용 — `python` 직접 호출 말고 `venv/Scripts/python` 사용

## 테스트 구조
```
tests/
├── unit/       # 엔티티, 매퍼, 정책 단위 테스트
└── integration/ # 파이프라인 dry-run, settings 검증
```

## 주의사항
- `service_account.json.json` — Git에 올리면 안 됨
- `archive/` — 레거시 코드 보관, 수정 불필요
- Playwright 필요 사이트: kiat, dicia, smart_factory, iitp, gbtp, ketep (설치: `playwright install chromium`)
