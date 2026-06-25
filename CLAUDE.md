# InterX Government Intelligence Engine

## 프로젝트 개요
정부지원사업 공고를 자동 수집·점수화·분류해 Google Sheets CRM에 업로드하는 파이프라인.
Clean Architecture 3레이어 (core → application → infrastructure) 구조.

## 아키텍처
```
core/           → 순수 도메인 (외부 의존성 없음)
  entities/     → Notice, ScoreCard, PredictionResult, Cluster, Partner ...
  rules/        → PriorityScoringPolicy, L3StrongPolicy, RecommendationRules

application/    → 유스케이스 & 오케스트레이터
  use_cases/    → 20개 (score, deduplicate, detect_recurring, win_prediction, validate_parsing ...)
  ports/        → 인터페이스 (collector, sheet, alert, partner)
  mappers/      → Notice→Sheets행 변환
  orchestrators/→ DailyPipeline, FullPipeline

infrastructure/ → 외부 구현체
  collectors/   → 20개 사이트 크롤러 (requests / Playwright)
  sheets/       → Google Sheets API
  alert/        → Slack / Telegram
  clustering/   → TF-IDF / Embedding
  persistence/  → SQLite
  analysis/     → pandas / sklearn
```

## 실행
```bash
venv/Scripts/python run_engine.py              # 기본
venv/Scripts/python run_engine.py --full       # 클러스터링·파트너·알림 포함
venv/Scripts/python run_engine.py --dry-run    # Mock 데이터 테스트
venv/Scripts/python run_engine.py --no-sheets  # Sheets 업로드 생략
venv/Scripts/python run_engine.py --no-detail  # 상세 페이지 생략 (빠른 실행)
venv/Scripts/python run_engine.py --sites bizinfo,kiat  # 특정 사이트만
venv/Scripts/python -m pytest tests/unit/ -v --tb=short  # 단위 테스트
```

## 설정 파일 (configs/) — 코드에 하드코딩 금지
| 파일 | 역할 | 핵심 파라미터 |
|---|---|---|
| `scoring.yaml` | 점수 가중치·등급 컷·키워드 | grade_a=48, grade_b=30, grade_c=18 |
| `sites.yaml` | 수집 사이트 목록 (enabled 플래그) | 16개 enabled |
| `recurring.yaml` | 정기공고 패턴 (name + aliases) | 125줄 |
| `manager_rules.yaml` | 담당자 배정 규칙 | 키워드+부처 매칭 |
| `sheets.yaml` | Sheets 9시트 컬럼 매핑 | 01~96 시트 |
| `settings.yaml` | 타임아웃·페이지수·워커수 | max_pages=5 |

## 스코어링 알고리즘 핵심 (priority_scoring_policy.py)
```
scored_text = 제목 + 요약 + 사업목적 + 지원내용 (body_text 제외 — 오염 방지)
full_text   = scored_text + body_text (코어 키워드 체크에만 사용)

1. 코어 키워드 체크 → 하나도 없으면 fitness=0 → D등급
2. 가점: POSITIVE_KEYWORDS × 5.0 + 구조화섹션 ×1.5 + 예산보너스 3.0
3. 감점: NEGATIVE_KEYWORDS × 6.0
4. fitness = pos - neg (0~100 클램핑)
5. 솔루션별 점수 8개 (ManufacturingDT/RecipeAI/QualityAI/InspectionAI/SafetyAI/GenAI/InfraDS/PdM)
6. industry_score = 비0점 솔루션 평균
7. priority = fitness × 0.6 + industry × 0.4
8. 등급: A(≥48) / B(≥30) / C(≥18) / D(<18) ← scoring.yaml에서 로드
9. L3 강공고: fitness ≥ 30 AND L3 키워드 존재 → l3_strong="Y"
```

## Win Prediction 가중치 (win_prediction.py)
```
fitness_score  × 0.35   # 키워드 매칭 적합도
priority_score × 0.25   # 우선순위
budget_억      × 0.15   # 지원금액
dday_urgency   × 0.10   # 마감 긴급도
l3_flag        × 0.10   # L3 강공고 여부
industry_score × 0.05   # 솔루션 적합도
→ 0~100% (A≥75 / B≥55 / C≥35 / D<35)
ML 모드: data/models/win_pred_lr.pkl 존재 시 자동 전환
```

## BD 마일스톤 자동 배정
- M01: L3강공고=Y (기본)
- M05: L3강공고=Y + D-day ≤ 14 (A/B) 또는 D-day ≤ 7 (전등급)
- P01: 파트너후보=Y (A/B/C)
- 복합: M01|P01, M05|P01

## Google Sheets 9시트
01_영업기회_정보 / 02_L3강공고 / 03_파트너전달 / 05_긴급마감_공고
20_BD리포트 / 22_KPI / 93_통계 / 94_실행로그 / 96_에러로그

## 수집기 구조
- `BaseCollector` (requests) / `PlaywrightBaseCollector` 상속
- `_parse_page()` 구현 필수
- 2단계: 목록 순회 → 상세 페이지 보강 (_enrich_notices)
- notice_id = site_code + URL MD5(8자리)
- Playwright 사이트: bizinfo, kiat, dicia, smart_factory, iitp, ketep

## 알려진 이슈
- ✅ (해결) 테스트 18건 실패 → v5.9에서 전체 164건 통과
- ✅ (해결) 스마트공장 중복 → nttId 기반 notice_id로 수정 완료
- ✅ (해결) pypdf, olefile, python-docx → 설치 완료, 제안서 v2 생성 정상 동작
- ✅ (해결) ML 모델 미학습 → GradientBoosting 학습 완료 (223건, accuracy=0.985, ROC-AUC=0.998)
- ✅ (해결) 수집기 타임아웃 → timeout 20→30초, retry 2→3회, backoff 0.5→1.0 강화
- ✅ (해결) gwtp 404 스팸 → fetch_detail=False 설정
- ✅ (해결) use_container_width deprecation → width="stretch" 전체 교체

## ML 엔진 v2 (win_prediction.py)
```
피처 12개 (v2):
  fitness_score, priority_score, budget_score, dday_urgency,
  l3_flag, industry_score,
  tfidf_similarity, keyword_density, type_multiplier,
  combo_count, budget_grade, urgency_boost
모델: auto → 50건+ GradientBoosting, <50건 LogisticRegression
      ensemble → VotingClassifier(LR+GBM+RF)
      학습 데이터: data/exports/training/*.jsonl (파이프라인 자동)
      모델 파일: data/models/win_pred_model.pkl
```

---

## 다른 분 코드 (bizinfo_datalist.py) 비교 분석

### 그 코드의 강점 (우리 엔진에 취합해야 할 것)
1. **콤보 키워드 38쌍** — 두 키워드 동시 출현 시 보너스 (상생형AX+선도모델 → +8)
   → configs/scoring.yaml에 combo_keywords 섹션 추가
   → priority_scoring_policy.py에 콤보 계산 로직 추가

2. **정기공고 aliases 더 많음** — group_id + priority 구조, 변형명까지 포착
   → configs/recurring.yaml aliases 보강

3. **네거티브 감점 3단계** — 바이오(-20) / 교육(-15) / 식품(-5) 세분화
   → scoring.yaml negative_keywords를 strong/medium/weak 3단계로 분리

4. **접수상태 자동 분류** — 신청기간 파싱 → 접수중/접수예정/마감
   → base_collector.py _enrich에 classify_apply_status() 추가

5. **스마트공장 공고번호 중복키** — URL 대신 nttId로 중복 판별
   → smart_factory_collector.py notice_id 로직 수정

6. **상태변경로그** — 공고 상태 변경 시 사유/처리자/일시 기록
   → sheets.yaml에 상태변경로그 시트 추가

### 우리 엔진만 있는 것 (그 코드에 없음)
- 수집 사이트 20개+ (그쪽은 3개)
- win_probability ML 기반 수주 예측
- Playwright (JS/SPA 처리)
- body_text 8000자 수집
- 담당자 자동 배정
- 파트너 매칭
- TF-IDF 클러스터링
- 9패널 자동 분석 대시보드
- Slack/Telegram 알림
- 파싱 품질 자동 검증

### 취합 우선순위
1순위(즉시): 콤보 키워드 38쌍 → scoring.yaml (0.5일)
2순위(즉시): 정기공고 aliases 보강 → recurring.yaml (0.5일)
3순위(즉시): 스마트공장 nttId 중복키 → smart_factory_collector.py (1일)
4순위(1주): 접수상태 분류 → base_collector.py (1일)
5순위(1주): 상태변경로그 → sheets.yaml + 플랫폼 (1~2일)
6순위(2주): 네거티브 3단계 → scoring.yaml (0.5일)

---

## BD 플랫폼 기능 로드맵

### Phase 1 — 필수 (이것 없으면 Sheets와 다를 게 없음)
1. **홈 대시보드** — 숫자 카드(A등급/D-7 마감/정기공고 탐지) + 차트 3개 + 긴급 TOP5
   데이터: 01_영업기회_정보 시트 쿼리
2. **공고 상세 화면** — 기본정보 + 적합도(등급/win%/키워드/콤보/정기) + 본문 + 상태변경
   데이터: body_text, matched_keywords, win_probability, attachment_items
3. **파이프라인 칸반** — 신규→검토→제안서→제출→수주/탈락, 드래그 상태변경 + 로그
   데이터: status, manager, grade

### Phase 2 — 경쟁력 차별화
4. **정기공고 트래커** — 패턴별 올해 탐지 + 작년 수주 이력 연결
5. **제안서 후보 목록** — A등급+win≥60%+마감30일 자동 필터 + 담당자별 현황
6. **win_probability 파이프라인** — 예상 수주액 = Σ(예산 × win%) → 매니저 보고용

### Phase 3 — 확장
7. **시장 인텔리전스** — 월별 키워드 트렌드 + 솔루션별 공고 수 + 사이트별 활동량
8. **알림 센터** — Slack 연동 + 플랫폼 내 알림 (A등급 신규/D-3 마감/정기공고 탐지)
9. **파싱 검증 대시보드** — 사이트별 필드 완성도 + 등급 정확도 의심 자동 탐지

### 플랫폼 데이터 소스
Sheets API로 01시트 읽기 or SQLite(data/interx_engine.db) 직접 연결.
핵심 컬럼: notice_name, deadline, grade, win_probability, score, l3_strong,
         recurring_flag, recurring_group, manager, status, body_text, matched_keywords

### 공고 1건 전체 필드 (DB 설계 기준)
기본: notice_name, org, department, notice_date, deadline, apply_period, budget, link, site
수집: body_text(8000자), attachment_items, structured(사업목적/지원내용/지원대상/신청방법)
분석: grade, score, win_probability, matched_keywords, combo_keywords, l3_strong
정기: recurring_flag, recurring_group
감점: penalty_reasons, apply_status(접수중/접수예정)
운영: status, manager, memo, bd_milestone, collected_at

---

## PPT/PDF 생성 도구

### PPT (pptxgenjs)
- 경로: C:\Users\DJKIM\Desktop\ppt_gen\gen.js
- 실행: cd ppt_gen && node gen.js
- 테마: navy(#0A1628) + cyan(#00CFFF) 다크 테마
- 주의: hex 색상에 "#" 금지 / shadow 객체는 factory 함수로 매번 새로 생성
  / ROUNDED_RECTANGLE + accent border 함께 쓰지 말 것 (모서리 안 맞음)
- QA: comtypes로 PowerPoint COM → JPG export → 시각 검증
- 한글 텍스트 배치: x,y,w,h 좌표 정밀 계산 필수 (배열 깨짐 주의)

### PDF (reportlab)
- 경로: C:\Users\DJKIM\Desktop\ppt_gen\make_pdf.py
- 한글 폰트: Malgun Gothic (C:/Windows/Fonts/malgun.ttf, malgunbd.ttf)
- 출력: C:\Users\DJKIM\Desktop\우리엔진_플랫폼_적용가이드.pdf
- 이모지 주의: print문에 이모지 쓰면 cp949 인코딩 오류
- PDF 열려있으면 PermissionError — 닫고 재실행

---

## 핵심 원칙
- 도메인 규칙은 core/에만 — infrastructure에 비즈니스 로직 금지
- 설정값은 configs/ YAML에 — 코드 하드코딩 금지
- 크롤러는 BaseCollector 상속 — _parse_page() 구현
- service_account.json.json — Git 올리면 안 됨
- venv/Scripts/python 사용
- 의존 방향: infrastructure → application → core (역방향 절대 금지)
- 함수 50줄 이상 → 분리 검토, 파일 300줄 이상 → 역할 분리 검토
- 같은 로직 2회 반복 → 리팩토링 트리거
