<div align="center">

# InterX Government Intelligence Engine

**정부지원사업 공고를 자동 수집 · AI 점수화 · 등급 분류하는 풀파이프라인 엔진**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://interx-gov-intel.streamlit.app)
[![Tests](https://img.shields.io/badge/Tests-157%20passed-brightgreen?logo=pytest)](tests/)
[![License](https://img.shields.io/badge/License-Private-lightgrey)]()

[Live Demo](https://interx-gov-intel.streamlit.app) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [Features](#-features)

</div>

---

## What It Does

```
27개 정부사이트 자동 크롤링
  → 키워드 기반 적합도 스코어링 (A/B/C/D 등급)
    → 수주 확률 예측 (Rule + ML 자동 전환)
      → Google Sheets CRM 자동 업로드
        → Telegram/Slack 실시간 알림
```

<br>

## 📊 At a Glance

| | |
|---|---|
| **수집 사이트** | 27개 (requests 22 + Playwright 5) |
| **파이프라인** | 18단계 자동화 |
| **스코어링** | 가점/감점/콤보 80쌍 + 3단계 감점 |
| **수주 예측** | Rule v1 → sklearn ML 자동 전환 |
| **정기공고** | 18그룹 120+ aliases 패턴 매칭 |
| **AI Agent** | Gemini 무료 (분석 + 챗봇 + 브리핑) |
| **웹 대시보드** | Streamlit Cloud (12페이지, 무료) |
| **테스트** | 157 unit + P1-P6 통합 전체 통과 |
| **비용** | **완전 무료** — 유료 API 없음 |

<br>

## 🚀 Quick Start

```bash
# 1. Clone & Setup
git clone https://github.com/KimDoojin2/interx-gov-intelligence.git
cd interx-gov-intelligence
python -m venv venv && venv/Scripts/activate
pip install -r requirements.txt

# 2. Run Pipeline
python run_engine.py              # 기본 (수집→스코어링→업로드)
python run_engine.py --dry-run    # Mock 테스트
python run_engine.py --full       # 전체 (클러스터링+알림 포함)

# 3. Dashboard
streamlit run streamlit_app.py    # http://localhost:8501
```

<details>
<summary><b>더 많은 실행 옵션</b></summary>

```bash
python run_engine.py --no-sheets      # Sheets 업로드 생략
python run_engine.py --no-alert       # 알림 생략
python run_engine.py --no-detail      # 상세 페이지 생략 (빠른 실행)
python run_engine.py --sites bizinfo,kiat,nipa  # 특정 사이트만

# Docker
docker compose --profile engine up     # 파이프라인
docker compose --profile dashboard up  # 대시보드 (localhost:8501)
docker compose --profile api up        # REST API (localhost:8000/docs)

# Test
pytest tests/unit/ -v --tb=short       # 단위 테스트
pytest tests/ -v                       # 전체 테스트
```

</details>

<br>

## 🏗 Architecture

**Clean Architecture 3-Layer** — 의존 방향: `infrastructure → application → core` (역방향 금지)

```
┌─────────────────────────────────────────────┐
│  core/                                       │  순수 도메인 로직
│    entities/   Notice, ScoreCard, Partner     │  외부 의존성 없음
│    rules/      ScoringPolicy, L3Policy        │
├─────────────────────────────────────────────┤
│  application/                                │  비즈니스 유스케이스
│    use_cases/  score, dedupe, predict, ...    │  25개 유스케이스
│    ports/      인터페이스 정의                  │
│    orchestrators/  DailyPipeline              │
├─────────────────────────────────────────────┤
│  infrastructure/                             │  외부 시스템 연동
│    collectors/   27개 사이트 크롤러             │  requests + Playwright
│    sheets/       Google Sheets API            │
│    alert/        Telegram + Slack             │
│    persistence/  SQLite                       │
└─────────────────────────────────────────────┘
```

<br>

## ✨ Features

### 1. 자동 수집 (27개 사이트)

2단계 수집: **목록 페이지 순회 → 상세 페이지 보강** (본문 8,000자 + 예산 + 첨부파일)

| 수집 방식 | 사이트 | 비고 |
|----------|--------|------|
| **Playwright** | bizinfo, kiat, ketep, smart_factory, iitp | JS/SPA 렌더링 |
| **requests** | nipa, innopolis, bipa, gjtp, kised, koiia + 테크노파크 12개 | HTML 파싱 |

<details>
<summary>전체 사이트 목록 (27개)</summary>

| 코드 | 기관명 | 방식 |
|------|--------|------|
| `bizinfo` | 기업마당 | Playwright |
| `kiat` | 한국산업기술진흥원 | Playwright |
| `nipa` | 정보통신산업진흥원 | requests |
| `innopolis` | 연구개발특구진흥재단 | requests |
| `smart_factory` | 스마트제조혁신추진단 | Playwright |
| `bipa` | 부산정보산업진흥원 | requests |
| `uipa` | 울산정보산업진흥원 | requests |
| `gicon` | 광주전남연구원 | requests |
| `ttp` | 대전테크노파크 | requests |
| `gjtp` | 광주테크노파크 | requests |
| `kised` | 창업진흥원 | requests |
| `ketep` | 에너지기술평가원 | Playwright |
| `koiia` | 산업지능화협회 | requests |
| `jejutp` | 제주테크노파크 | requests |
| `iitp` | 정보통신기획평가원 | Playwright |
| `seoultp` | 서울테크노파크 | requests |
| `gtp` | 경기테크노파크 | requests |
| `gdtp` | 경기대진테크노파크 | requests |
| `itp` | 인천테크노파크 | requests |
| `gwtp` | 강원테크노파크 | requests |
| `sjtp` | 세종테크노파크 | requests |
| `cbtp` | 충북테크노파크 | requests |
| `ctp` | 충남테크노파크 | requests |
| `btp` | 부산테크노파크 | requests |
| `utp` | 울산테크노파크 | requests |
| `gntp` | 경남테크노파크 | requests |
| `ptp` | 포항테크노파크 | requests |

</details>

---

### 2. AI 스코어링 엔진

```
scored_text = 제목 + 요약 + 사업목적 + 지원내용

Step 1  코어 키워드 체크 → 없으면 fitness=0 → D등급
Step 2  가점 (POSITIVE_KEYWORDS × 5.0)
Step 3  콤보 보너스 (80쌍 동시 출현 가점)
Step 4  감점 3단계 (Strong ×6.0 / Medium ×4.0 / Weak ×2.0)
Step 5  fitness = 가점 - 감점 (0~100)
Step 6  솔루션 점수 (8개) → industry_score
Step 7  priority = fitness × 0.6 + industry × 0.4
Step 8  등급: A(≥48) / B(≥30) / C(≥18) / D(<18)
```

**8개 솔루션 매칭:**

| 솔루션 | 영역 |
|--------|------|
| ManufacturingDT | 디지털트윈, 스마트공장 |
| RecipeAI | 공정 최적화, 배합 AI |
| QualityAI | 불량 검출, 이상탐지 |
| InspectionAI | 머신비전, 외관검사 |
| SafetyAI | 중대재해 예방, 안전 |
| GenAI | 생성형 AI, LLM, Agent |
| InfraDS | 데이터스페이스, Catena-X |
| PdM | 예지보전, 고장예측 |

---

### 3. 수주 예측 (Win Prediction)

| 피처 | 가중치 |
|------|--------|
| fitness_score | 35% |
| priority_score | 25% |
| budget | 15% |
| dday_urgency | 10% |
| l3_flag | 10% |
| industry_score | 5% |

**ML 자동 전환**: 수주/탈락 실적 20건+ 입력 시 `LogisticRegression` → `GradientBoosting` 자동 전환

---

### 4. 정기공고 탐지

18그룹 · 120+ aliases · Priority 순 매칭

| Priority | 대표 그룹 |
|----------|----------|
| **P1** (핵심) | 스마트공장구축, AX-Sprint, 제조AI특화, 상생형스마트공장 |
| **P2** (중간) | AI바우처, 디지털트윈R&D, 데이터스페이스, 탄소중립스마트공장 |
| **P3** (참고) | 클라우드바우처, 중소기업기술개발, 스마트산업단지 |

---

### 5. Streamlit 대시보드

> **Live**: [interx-gov-intel.streamlit.app](https://interx-gov-intel.streamlit.app)

12개 페이지 구성 · 다크/라이트 모드 전환 · CSS 변수 기반 테마 시스템

| 페이지 | 기능 |
|--------|------|
| 대시보드 | KPI 6개 + D-3 긴급배너 + 등급 차트 + A등급 TOP |
| 수집 실행 | 원클릭 파이프라인 실행 + 실시간 프로그레스 |
| 공고 목록 | 필터/검색 + 상세보기(iframe 미리보기 + AI 분석) |
| 공고 비교 | 2~3건 나란히 비교 + 수주확률 차트 |
| 제안서 | A/B등급 .docx 자동 생성 다운로드 |
| 경쟁사 | TOP10 차트 + Tier1/Tier2 분류 |
| 수주 예측 | 수주확률 분포 + 유망 TOP10 |
| 마감 캘린더 | D-3/D-7/D-30 타임라인 |
| 분석 | 솔루션 레이더 + 키워드 트렌드 + 히스토리 |
| 담당자 | 담당자별 등급 분포 + 업무 배분 |
| AI 뉴스 | IT/산업 RSS 피드 + 핵심 요약 |
| AI 챗봇 | Gemini 기반 자연어 질의응답 |

---

### 6. 자동화 & 알림

| 기능 | 설명 |
|------|------|
| **GitHub Actions** | 평일 07:00 / 14:00 KST 자동 수집 |
| **Telegram Bot** | `/status` `/top` `/urgent` `/search` 양방향 명령어 |
| **Slack Webhook** | L3 강공고 즉시 알림 + 일별 요약 |
| **AI 브리핑** | Gemini 무료 API로 일일 브리핑 자동 생성 |

---

### 7. REST API

```bash
python -m interx_engine.api    # http://localhost:8000/docs (Swagger UI)
```

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/notices` | 공고 목록 (필터·정렬·페이징) |
| GET | `/api/v1/notices/{id}` | 공고 상세 |
| GET | `/api/v1/notices/urgent` | 긴급 마감 공고 |
| GET | `/api/v1/stats` | 통계 (등급별·사이트별) |
| POST | `/api/v1/pipeline/run` | 파이프라인 수동 실행 |

<br>

## 📂 Project Structure

```
interx-gov-intelligence/
├── run_engine.py                 # CLI 진입점
├── streamlit_app.py              # Streamlit 대시보드
├── configs/                      # 모든 설정 YAML (코드 하드코딩 금지)
│   ├── scoring.yaml              #   점수 가중치 · 등급 컷 · 키워드
│   ├── sites.yaml                #   수집 사이트 목록 (enabled 플래그)
│   ├── recurring.yaml            #   정기공고 패턴 (18그룹)
│   ├── manager_rules.yaml        #   담당자 배정 규칙
│   ├── sheets.yaml               #   Google Sheets 컬럼 매핑
│   ├── settings.yaml             #   타임아웃 · 워커수 · 페이지수
│   └── competitors.yaml          #   경쟁사 추적 키워드
│
└── src/interx_engine/
    ├── core/                     # 도메인 순수 로직
    │   ├── entities/             #   Notice, ScoreCard, Partner ...
    │   └── rules/                #   ScoringPolicy, L3Policy
    ├── application/              # 유스케이스 25개
    │   ├── use_cases/            #   score, dedupe, predict ...
    │   ├── ports/                #   인터페이스
    │   ├── mappers/              #   Notice → Sheets 행 변환
    │   └── orchestrators/        #   Daily/Full Pipeline
    └── infrastructure/           # 외부 시스템 구현체
        ├── collectors/sites/     #   27개 사이트 크롤러
        ├── sheets/               #   Google Sheets API
        ├── alert/                #   Telegram + Slack
        ├── clustering/           #   TF-IDF / Embedding
        ├── persistence/          #   SQLite
        └── ocr/                  #   PDF/HWP/DOCX 파싱
```

<br>

## ⚙️ Pipeline (18 Steps)

```
 [1] 수집          27개 사이트 병렬 크롤링
 [2] ID 중복제거    notice_id = site + URL MD5
 [3] 마감 필터      deadline < today → 제거
 [4] 스코어링       fitness → priority → grade
 [5] TF-IDF 중복    cosine 유사도 0.85+ 제거
 [6] 변경 감지       제목·예산·마감일 변경 추적
 [7] 담당자 배정     manager_rules.yaml 매칭
 [8] 경쟁사 추적     competitors.yaml 키워드 감지
 [9] 품질 등급       사이트별 수집 품질 A~D
[10] 행 빌드        Notice + ScoreCard → Sheets 행
[11] 부가 분석       정기공고 · 수주예측 · 제안서 · 클러스터링
[12] KPI 빌드       실행 통계 행 생성
[13] 학습 Export     JSONL 자동 저장 (ML 학습 데이터)
[14] Sheets 업로드   10개 시트 분산 저장
[15] SQLite 저장     영속화
[16] 알림 발송       L3 즉시 + 일별 요약
[17] 자동 분석       PCA · KMeans · IsolationForest 9패널 PNG
[18] AI 브리핑       Gemini 요약 자동 생성
```

<br>

## 📋 Google Sheets (10시트)

| 시트 | 용도 |
|------|------|
| `01_영업기회_정보` | 전체 공고 마스터 |
| `02_L3강공고` | L3 강공고 필터 |
| `03_파트너전달` | 파트너 후보 공고 |
| `05_긴급마감_공고` | D-7 이내 마감 |
| `20_BD리포트` | 보고용 요약 |
| `22_KPI` | 실행 성능 KPI |
| `93_통계` | 부처·솔루션·키워드 집계 |
| `94_실행로그` | 파이프라인 실행 이력 |
| `96_에러로그` | 수집 오류 |
| `97_상태변경로그` | 공고 상태 변경 이력 |

<br>

## 🔧 Configuration

모든 비즈니스 파라미터는 `configs/` YAML로 관리합니다. **코드 하드코딩 금지.**

<details>
<summary><b>scoring.yaml</b> — 점수 가중치 · 등급 컷 · 키워드</summary>

```yaml
thresholds:
  grade_a: 48        # A등급 커트라인
  grade_b: 30        # B등급
  grade_c: 18        # C등급
  l3_strong: 30      # L3 강공고 fitness 하한
  pos_multiplier: 5.0
  neg_multiplier_strong: 6.0   # 바이오/의료/건설
  neg_multiplier_medium: 4.0   # 교육/인력
  neg_multiplier_weak: 2.0     # 식품/농업

priority_formula:
  w_fitness: 0.6
  w_industry: 0.4

combo_keywords:    # 80쌍
  - ["상생형", "선도모델", 8]
  - ["ai", "제조", 5]
  ...
```

</details>

<details>
<summary><b>sites.yaml</b> — 수집 사이트</summary>

```yaml
sites:
  - code: bizinfo
    name: 기업마당
    enabled: true
    collector_type: playwright
  - code: kiat
    enabled: true
    collector_type: playwright
  ...
```

</details>

<details>
<summary><b>settings.yaml</b> — 전역 설정</summary>

```yaml
pipeline:
  max_pages_default: 5
  request_timeout: 15
  enrich_workers: 3
  collect_workers: 6
  tfidf_sim_threshold: 0.85
```

</details>

<br>

## 🧪 Testing

```bash
pytest tests/unit/ -v --tb=short              # 단위 테스트 (157건)
pytest tests/ -v                               # 전체 (unit + integration)
pytest tests/ --cov=src/interx_engine --cov-report=html  # 커버리지
```

| 테스트 | 검증 내용 |
|--------|----------|
| `test_scoring_policy.py` | 가점/감점/등급 정확도 |
| `test_l3_policy.py` | L3 키워드 매칭 |
| `test_notice_mapper.py` | Notice → Sheets 행 변환 |
| `test_budget_parser.py` | 예산 파싱 ("10억원" → 숫자) |
| `test_recurring.py` | 정기공고 패턴 매칭 |

<br>

## 🔌 Adding a New Collector

```python
# 1. infrastructure/collectors/sites/new_collector.py
class NewSiteCollector(BaseCollector):
    site_key  = "newsite"
    site_name = "새 기관명"
    list_url  = "https://newsite.go.kr/notices?page={page}"

    def _parse_page(self, page: int) -> List[Notice]:
        html = self._get(self.list_url.format(page=page))
        soup = BeautifulSoup(html, "lxml")
        ...
```

```yaml
# 2. configs/sites.yaml
- code: newsite
  name: 새 기관명
  enabled: true
  collector_type: requests
```

```python
# 3. collector_factory.py
_REGISTRY["newsite"] = NewSiteCollector
```

```bash
# 4. 테스트
python run_engine.py --sites newsite --no-sheets --dry-run
```

<br>

## 💰 Cost

| 항목 | 비용 |
|------|------|
| Streamlit Cloud 호스팅 | **무료** |
| 크롤링 (requests + BS4) | **무료** |
| 스코어링 / ML (scikit-learn) | **무료** |
| 차트 (Plotly) | **무료** |
| AI (Gemini API) | **무료** |
| Google Sheets API | **무료** |

> **전 기능 0원 운영** — 외부 유료 API 미사용

<br>

## 📝 Changelog

<details>
<summary><b>v7.0</b> — 2026-05-26 · Modern B2B SaaS 전체 리디자인</summary>

**UI 전면 개편** (Palantir / Linear / Vercel 참고)
- CSS 변수 기반 다크/라이트 테마 시스템
- KPI 카드 hover 애니메이션 + 그라데이션 accent bar
- 공고 상세: iframe 원문 미리보기 + AI 분석 + 본문 요약

**8개 신규 기능:**
| # | 기능 | 설명 |
|---|------|------|
| 1 | 접수상태 뱃지 | 접수중/접수예정/마감 자동 분류 |
| 2 | 수주확률 KPI | 대시보드 + 공고별 수주확률% |
| 3 | AI 분석 캐싱 | session_state 캐시로 중복 API 방지 |
| 4 | D-3 긴급배너 | 펄스 애니메이션, 최대 5건 |
| 5 | GitHub Actions | 평일 07:00/14:00 KST 자동 수집 |
| 6 | 공고 비교 | 2~3건 side-by-side + 차트 |
| 7 | Telegram Bot | /status /top /urgent /search |
| 8 | 다크 모드 | 사이드바 토글, 즉시 전환 |

</details>

<details>
<summary><b>v6.1</b> — 2026-05-26 · 6기능 완전 구현 + 제안서 v2</summary>

- **P1 콤보 키워드**: 80쌍 (scoring.yaml + 엔진 연동)
- **P2 정기공고 aliases**: 18그룹, 120+ aliases
- **P3 네거티브 3단계**: Strong 91개 / Medium 48개 / Weak 12개
- **P4 접수상태**: 본문 파싱 → 접수중/접수예정/마감 자동 판별
- **P5 알림**: Telegram/Slack 환경변수 자동 감지
- **P6 제안서 v2**: 솔루션 프로필 + 경쟁분석 + 8섹션 자동

</details>

<details>
<summary><b>v5.9</b> — 2026-05-22 · 프로덕션 Ready + ML v2 + AI Agent</summary>

- AI Agent 4기능 (Gemini 무료): 공고분석 + 챗봇 + 브리핑 + 제안서
- ML 수주예측 v2: 12피처, GBM/RF/앙상블 지원
- pyproject.toml + Docker + FastAPI REST API
- OCR: PDF(pdfplumber) + HWP(olefile) + DOCX
- GitHub Actions CI: 자동 lint + test
- 201건 테스트 통과

</details>

<details>
<summary><b>v5.2~5.8</b> — 이전 버전</summary>

- **v5.8**: 비제조AI 오탐 감소 — CORE_KEYWORDS 범용 단어 14개 제거
- **v5.7**: 뉴스 피드 복구 + 본문 요약 품질 대폭 개선
- **v5.6**: 수집기 버그 일괄 수정 (BTP 페이지네이션, GWTP 404, CBTP SSL)
- **v5.4**: 고장 사이트 8개 비활성화, 수주분석 강화, 원문 미리보기
- **v5.2**: 테크노파크 12개 신규 (27개 확대), 2026 키워드 30개+ 추가

</details>

<details>
<summary><b>v4.5~5.0</b> — 초기 버전</summary>

- **v5.0**: Enterprise UI v5 + 프로젝트 대규모 정리 (-12,000줄)
- **v4.5**: 프리미엄 UI + 스코어링 v3 고도화 (위치 가중치, 예산 구간, TF-IDF 유사도)

</details>

<br>

## 📌 Principles

- **도메인 로직은 `core/`에만** — infrastructure에 비즈니스 로직 금지
- **설정값은 `configs/` YAML에** — 코드 하드코딩 금지
- **의존 방향**: `infrastructure → application → core` (역방향 절대 금지)
- **수집기**: `BaseCollector` 상속 → `_parse_page()` 구현
- **보안**: `service_account.json` — Git 커밋 금지
- **품질**: 함수 50줄+ → 분리, 파일 300줄+ → 역할 분리

<br>

---

<div align="center">

Built with Python · Streamlit · scikit-learn · Playwright · Google Sheets API

</div>
