# InterX Government Intelligence Engine

정부지원사업 공고를 자동 수집·점수화·분류해 Google Sheets CRM에 업로드하는 파이프라인.

## 실행

```bash
# 전체 파이프라인 (기본)
venv/Scripts/python run_engine.py

# 옵션
venv/Scripts/python run_engine.py --full          # 클러스터링·파트너매칭·알림 포함
venv/Scripts/python run_engine.py --dry-run       # Mock 데이터로 테스트
venv/Scripts/python run_engine.py --no-sheets     # Sheets 업로드 없이 실행
venv/Scripts/python run_engine.py --no-alert      # 알림 비활성화
venv/Scripts/python run_engine.py --no-detail     # 상세 페이지 방문 생략 (빠른 실행)
venv/Scripts/python run_engine.py --sites bizinfo,bipa,kiat  # 특정 사이트만

# 테스트
venv/Scripts/python -m pytest tests/unit/ -v --tb=short
venv/Scripts/python -m pytest tests/ -v

# 대시보드
streamlit run src/interx_engine/interfaces/dashboard/app.py
```

## 디렉토리 구조

```
interx_gov_intelligence/
├── run_engine.py                        # 단일 진입점
├── configs/
│   ├── settings.yaml                    # 전역 설정 (페이지수, 타임아웃 등)
│   ├── scoring.yaml                     # 점수 가중치 및 등급 기준
│   ├── sites.yaml                       # 수집 대상 사이트 목록 (enabled 플래그)
│   ├── sheets.yaml                      # Google Sheets 컬럼 매핑
│   ├── manager_rules.yaml               # 담당자 자동 배정 규칙
│   └── competitors.yaml                 # 경쟁사 추적 대상
│
└── src/interx_engine/
    ├── core/                            # 도메인 (외부 의존성 없음)
    │   ├── entities/
    │   │   ├── notice.py                # 공고 엔티티
    │   │   ├── score_card.py            # 채점 결과
    │   │   ├── partner.py               # 파트너사
    │   │   ├── recommendation.py        # BD 추천 액션
    │   │   ├── cluster.py               # 공고 클러스터
    │   │   ├── prediction_result.py     # 수주 예측 결과
    │   │   ├── analysis_report.py       # 포트폴리오 분석 리포트
    │   │   └── attachment.py            # 첨부파일
    │   └── rules/
    │       ├── priority_scoring_policy.py  # 점수 계산 핵심 로직
    │       ├── l3_strong_policy.py         # L3 강공고 필터
    │       └── recommendation_rules.py     # BD 액션 추천 규칙
    │
    ├── application/                     # Use Cases & Orchestrators
    │   ├── ports/
    │   │   ├── notice_collector_port.py
    │   │   ├── sheet_gateway_port.py
    │   │   ├── alert_gateway_port.py
    │   │   └── partner_repository_port.py
    │   ├── use_cases/
    │   │   ├── score_notices.py         # 스코어링
    │   │   ├── deduplicate_notices.py   # TF-IDF 중복 제거
    │   │   ├── detect_changes.py        # 공고 변경 감지
    │   │   ├── assign_manager.py        # 담당자 자동 배정
    │   │   ├── assign_milestone.py      # BD 마일스톤 배정
    │   │   ├── track_competitors.py     # 경쟁사 트래킹
    │   │   ├── match_partners.py        # 파트너사 매칭
    │   │   ├── recommend_notices.py     # BD 추천 생성
    │   │   ├── cluster_notices.py       # 공고 클러스터링
    │   │   ├── alert_notices.py         # 알림 발송
    │   │   ├── site_quality_grader.py   # 사이트 품질 등급
    │   │   ├── deep_parsing.py          # 첨부파일 정밀 파싱 (PDF/HWP)
    │   │   ├── portfolio_analysis.py    # 포트폴리오 분석
    │   │   ├── win_prediction.py        # 수주 가능성 예측 (ML)
    │   │   ├── generate_proposal.py     # 제안서 초안 자동 생성
    │   │   ├── export_training_data.py  # ML 학습데이터 JSONL 저장
    │   │   ├── summarize_l3.py          # L3 공고 Claude API 요약
    │   │   ├── auto_analysis.py         # 비지도학습 자동 분석
    │   │   ├── download_attachments.py  # 첨부파일 다운로드
    │   │   └── log_pipeline_run.py      # 파이프라인 실행 로그
    │   ├── mappers/
    │   │   ├── notice_mapper.py         # Notice → Sheets 행 변환
    │   │   ├── kpi_mapper.py            # KPI/통계/로그 행 빌더
    │   │   └── attachment_mapper.py     # 첨부파일 행 변환
    │   └── orchestrators/
    │       ├── daily_pipeline.py        # 수집→스코어링→업로드 전체 흐름
    │       └── full_pipeline.py         # daily + 클러스터링·파트너매칭·알림
    │
    ├── infrastructure/                  # 외부 구현체
    │   ├── config/
    │   │   └── settings_loader.py       # 설정 싱글턴
    │   ├── collectors/
    │   │   ├── collector_factory.py     # 사이트별 콜렉터 팩토리
    │   │   ├── html_utils.py            # HTML 파싱 공통 유틸
    │   │   └── sites/
    │   │       ├── base_collector.py    # BaseCollector / PlaywrightBaseCollector
    │   │       ├── bizinfo_collector.py # 기업마당
    │   │       ├── iris_collector.py    # IRIS (국가과학기술지식정보서비스)
    │   │       ├── kiat_collector.py    # 한국산업기술진흥원
    │   │       ├── smba_collector.py    # 중소벤처기업부
    │   │       ├── nipa_collector.py    # 정보통신산업진흥원
    │   │       ├── innopolis_collector.py  # 연구개발특구진흥재단
    │   │       ├── bipa_collector.py    # 부산정보산업진흥원
    │   │       ├── uipa_collector.py    # 울산정보산업진흥원
    │   │       ├── gicon_collector.py   # 광주정보문화산업진흥원
    │   │       ├── ttp_collector.py     # 대전테크노파크
    │   │       ├── dicia_collector.py   # 한국첨단의료산업진흥재단
    │   │       ├── gjtp_collector.py    # 광주테크노파크
    │   │       ├── gbtp_collector.py    # 경북테크노파크
    │   │       ├── jntp_collector.py    # 전남테크노파크
    │   │       ├── jbtp_collector.py    # 전북테크노파크
    │   │       ├── jejutp_collector.py  # 제주테크노파크
    │   │       ├── new_collectors.py    # NRF·KISED·KETEP·KOIIA
    │   │       ├── ntis_collector.py    # NTIS (스캐폴드)
    │   │       └── mock_notice_collector.py  # 테스트용 Mock
    │   ├── sheets/
    │   │   ├── google_sheet_gateway.py  # 실제 Google Sheets 연동
    │   │   └── console_sheet_gateway.py # 콘솔 Fallback
    │   ├── persistence/
    │   │   └── sqlite_writer.py         # SQLite 영속성
    │   ├── alert/
    │   │   ├── telegram_gateway.py      # Telegram 알림
    │   │   └── slack_gateway.py         # Slack 알림
    │   ├── clustering/
    │   │   ├── tfidf_clusterer.py       # TF-IDF 클러스터링
    │   │   └── embedding_clusterer.py   # Sentence-Transformers 클러스터링
    │   ├── matching/
    │   │   └── csv_partner_repository.py  # CSV 파트너 저장소
    │   ├── storage/
    │   │   ├── csv_writer.py            # CSV Fallback 저장
    │   │   └── file_downloader.py       # 첨부파일 다운로더
    │   ├── analysis/
    │   │   ├── pandas_analyzer.py       # pandas 분석
    │   │   └── sklearn_clusterer.py     # sklearn 클러스터링
    │   └── utils/
    │       ├── budget_parser.py         # 예산 문자열 정규화
    │       └── morpheme_scorer.py       # 형태소 점수 계산
    │
    └── interfaces/
        └── dashboard/
            └── app.py                   # Streamlit 대시보드

tests/
├── unit/                                # 엔티티·매퍼·정책 단위 테스트
└── integration/                         # 파이프라인 dry-run, settings 검증
```

## 핵심 원칙

- **도메인 규칙은 `core/`에만** — infrastructure에 비즈니스 로직 넣지 말 것
- **설정값은 `configs/` YAML에** — 코드에 하드코딩 금지
- **각 크롤러는 `base_collector.py` 상속** — `collect()` 메서드 구현
- `service_account.json` — Git에 올리면 안 됨 (Google 인증키)
- Playwright 필요 사이트: `kiat`, `dicia`, `bizinfo` (`playwright install chromium`)
