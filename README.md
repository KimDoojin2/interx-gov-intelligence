# InterX Government Intelligence Engine

정부지원사업 공고를 **자동 수집 → 필터링 → 점수화 → 등급 분류 → Google Sheets 업로드** 하는 풀파이프라인 엔진.

---

## 목차
0. [최근 업데이트](#-최근-업데이트)
1. [한눈에 보기](#1-한눈에-보기)
2. [빠른 실행](#2-빠른-실행)
3. [아키텍처 — 3레이어 클린 구조](#3-아키텍처--3레이어-클린-구조)
4. [디렉토리 구조](#4-디렉토리-구조)
5. [파이프라인 17단계 상세](#5-파이프라인-17단계-상세)
6. [수집 (Collector)](#6-수집-collector)
7. [스코어링 알고리즘](#7-스코어링-알고리즘)
8. [정기공고 탐지](#8-정기공고-탐지)
9. [L3 강공고 정책](#9-l3-강공고-정책)
10. [수주 예측 (Win Prediction)](#10-수주-예측-win-prediction)
11. [담당자 자동 배정 & BD 마일스톤](#11-담당자-자동-배정--bd-마일스톤)
12. [설정 파일 (configs/)](#12-설정-파일-configs)
13. [Google Sheets 10시트 구조](#13-google-sheets-10시트-구조)
14. [새 컬렉터 추가 방법](#14-새-컬렉터-추가-방법)
15. [테스트](#15-테스트)
16. [핵심 원칙](#16-핵심-원칙)
17. [BD Intelligence 웹 플랫폼](#17-bd-intelligence-웹-플랫폼)
18. [경쟁사 분석 리포트](#18-경쟁사-분석-리포트)
19. [제안서 자동 생성 v2](#19-제안서-자동-생성-v2)
20. [ML 수주예측 학습 파이프라인](#20-ml-수주예측-학습-파이프라인)
21. [Streamlit 팀 배포 앱](#21-streamlit-팀-배포-앱)

---

## 📋 최근 업데이트

### v7.3 — 2026-05-28

**사업계획서 생성기 v4 — 부처별 실제 양식 기반 자동 매칭**

| 항목 | 내용 |
|------|------|
| **템플릿 레지스트리** | `configs/business_plan_templates.yaml` — 산자부(KEIT), 중기부(TIPA), AX Sprint 3개 부처별 실제 양식 구조 등록 |
| **자동 매칭** | 공고의 부처/기관/사업명 키워드 → 해당 양식 자동 선택 (4단계 폴백) |
| **양식 기반 생성** | 실제 정부 양식(HWPX/HWP에서 추출)의 섹션 구조 + guidance를 Gemini 프롬프트에 주입 |
| **매칭 결과** | 산자부→7섹션(필요성~TRL), TIPA→4섹션(목표~확산), AX Sprint→6섹션(개요~KPI), 범용→6섹션 |
| **skip_ai_content** | 인적사항, 예산 등 수기 작성 섹션은 AI 생성 건너뜀 |

**4단계 폴백:** 업로드 양식 → 레지스트리 매칭 → AI 공고 분석 → 기본 템플릿
**전 기능 0원 운영**

---

### v7.2 — 2026-05-28

**🔧 엔진 점검 + 5대 신규 기능 + 차트 수정 + 테스트 강화**

**엔진 점검 4개 이슈 전체 수정:**

| 이슈 | 수정 내용 |
|------|----------|
| **App→Infra 역방향 의존** | 29개 직접 import → 포트/어댑터 패턴 리팩토링 (settings_port, budget_utils_port, gemini_port) |
| **Use Case 테스트 부재** | 8개 핵심 UC 대상 36개 단위 테스트 신규 작성 |
| **본문 파싱 짧은 단어 필터** | 문장 단위 분리 후 필터 적용으로 변경 (의미 있는 문장 유실 방지) |
| **NTIS 수집기 스캐폴드** | 빈 `[]` 반환 → BaseCollector 완전 구현 (_parse_page, _parse_table_rows, _resolve_url) |

**5대 신규 기능:**

| # | 기능 | 설명 | 파일 |
|---|------|------|------|
| 1 | **스마트 알림 자동화** | A등급 신규, D-3 마감 긴급, 변경 감지 알림 (enabled=False 기본) | `send_smart_alerts.py` |
| 2 | **수집기 가동률 점검** | 26개 사이트 1페이지 수집 시도 → 성공/빈결과/실패 리포트 (81% 가동) | `check_collectors.py` |
| 3 | **변경감지 v2** | 필드별 스냅샷(해시, 마감일, 예산, 접수상태, 첨부수) + 구체적 변경사유 추적 | `detect_changes.py` |
| 4 | **유사공고 추천** | TF-IDF char_wb(2,4) cosine similarity 기반, 공유 키워드 표시 | `find_similar_notices.py` |
| 5 | **공고 상세 페이지 강화** | 유사 공고 TOP5 추천 + 변경 이력 섹션 추가 | `streamlit_app.py` |

**차트 한글 겹침 수정:**
- Y축 한글 제목 세로 겹침 해결 (`_yaxis()` 헬퍼 + standoff=8 + margin 조정)
- 범례-제목 겹침 해결 (솔루션 트렌드 차트 height 450, legend y=1.18)
- 수평 바 차트 좌측 여백 확대 (l=120)

**NTIS 수집기 상태:**
- 기존 URL 404 → 신규 URL 확인 → 봇 접근 차단 확인 → `enabled: false` (Playwright 전환 필요)

**테스트:** 324건 전체 통과 (기존 157 + UC 36 + 파싱 정확도 107 + 기타 24)
**가동률:** 25개 사이트 대상, 21개 정상 수집 (84%)
**전 기능 0원 운영**

---

### v7.1 — 2026-05-26

**🚀 엔진 100% 완성 — ML 학습 + 제안서 활성화 + 수집기 안정화**

| 항목 | 내용 | 비용 |
|------|------|------|
| **ML 수주예측 모델 학습** | GradientBoosting 223건 학습 완료 (accuracy=98.5%, ROC-AUC=0.998). 다음 파이프라인부터 ML 모드 자동 전환 | 무료 (scikit-learn) |
| **제안서 v2 생성 활성화** | pypdf/olefile/python-docx 설치 확인, A등급 공고 .docx 자동 생성 정상 동작 | 무료 (오픈소스) |
| **수집기 타임아웃 안정화** | timeout 20→30초, retry 2→3회, backoff 0.5→1.0 (느린 사이트 대응) | 무료 (설정값) |
| **gwtp 404 스팸 차단** | 강원TP 상세페이지 전부 404 → fetch_detail=False, ~390건 불필요 요청 제거 | — |
| **Streamlit deprecation 해소** | `use_container_width=True` → `width="stretch"` 전체 21건 교체 | — |

**테스트:** 157건 전체 통과
**전 기능 0원 운영** — 외부 유료 API 미사용

---

### v7.0 — 2026-05-26

**🎨 Modern B2B SaaS 전체 리디자인 + 8개 신규 기능**

**UI 전면 개편 (Palantir / Linear / Vercel 참고):**
- CSS 변수 기반 테마 시스템 (다크/라이트 즉시 전환)
- 새 KPI 카드 디자인 (hover 시 그라데이션 accent bar + translateY 애니메이션)
- 클린 타이포그래피, 통일된 색상 토큰, 여백 개선
- Enterprise급 데이터 테이블 가독성 향상
- 공고 상세 보기: 원문 미리보기(iframe) + AI 분석 + 본문 요약 통합 패널

**8개 신규 기능:**

| # | 기능 | 설명 |
|---|------|------|
| 1 | 접수상태 뱃지 | 접수중(초록)/접수예정(파랑)/마감(회색) 뱃지 — 대시보드+공고목록+캘린더 |
| 2 | 수주확률 KPI | 대시보드 6번째 KPI 카드 + 공고별 수주확률% 표시 |
| 3 | AI 분석 캐싱 | session_state에 공고별 Gemini 분석 결과 저장, 중복 API 호출 방지 |
| 4 | D-3 긴급배너 | 대시보드 최상단, 펄스 애니메이션 + 최대 5건 표시 |
| 5 | GitHub Actions | `.github/workflows/auto_collect.yml` — 평일 07:00/14:00 KST 자동 수집 |
| 6 | 공고 비교 | 새 페이지 "공고 비교" — 2~3건 나란히 비교 테이블 + 수주확률 차트 |
| 7 | 양방향 텔레그램 | `telegram_bot.py` — /status /top /urgent /search 명령어 지원 |
| 8 | 다크 모드 | 사이드바 토글 버튼, 전체 UI 즉시 전환 |

**테스트:** 157 unit tests + P1-P6 통합 테스트 전체 통과
**백업:** `v6.1-stable` 태그로 롤백 가능

---

### v6.1 — 2026-05-26

**🔧 6기능 완전 구현 + 제안서 v2 전환 + UI 안정화**

**P1~P6 기능 구현 완료:**
- **P1 콤보 키워드**: 80쌍 (scoring.yaml + priority_scoring_policy.py 연동 완료)
- **P2 정기공고 aliases**: 18그룹, 120+ aliases, priority 순 정렬 매칭
- **P3 네거티브 3단계**: Strong(91개/×6.0) + Medium(48개/×4.0) + Weak(12개/×2.0)
- **P4 접수상태 자동 분류**: `classify_apply_status()` → Notice.apply_status 정식 필드화
  - 본문에서 접수기간 파싱 → 접수중/접수예정/마감 자동 판별
  - Sheets 매퍼 28컬럼으로 확장 (접수상태 컬럼 추가)
- **P5 Telegram/Slack 알림**: 환경변수 자동감지, L3 강공고 즉시알림 + 일별요약
- **P6 제안서 v2 고도화**: 솔루션별 역량 프로필, 경쟁분석, 정기공고 이력, 8섹션 자동생성
  - 파이프라인 기본 제안서 v1 → v2 전환 완료

**엔진 안정화:**
- Python 3.14 호환성 검증 완료
- Gemini API 키 보안: URL 파라미터 → `x-goog-api-key` 헤더 방식 전환
- 스코어링 fallback 값 scoring.yaml 실제값과 동기화 (grade_a=48/b=30/c=18)
- bare `except:` → `except Exception:` 전환 (코드 품질)
- 157 unit tests + P1-P6 통합 테스트 전체 통과

**UI 수정:**
- 사이드바 네비게이션: 하얀 배경 + 오렌지 액센트
- 사이드바 접기/펼치기: `<<` 클릭 후에도 `>` 버튼 항상 표시 (header 투명화)
- 솔루션+키워드+히스토리 3탭 → "📈 분석" 단일 페이지로 병합
- 하단 배너 제거 (불필요 UI 정리)

### v6.0 — 2026-05-22

**🎨 사이드바 네비게이션 전면 리팩토링**
- 13개 수평 탭 → 좌측 사이드바 네비게이션
- 사이드바: INTERX 브랜딩 + 시스템 상태 (LIVE/v5.9/25Sites/ML v2)
- 히어로 배너 제거 → 컴팩트 탑바만 유지 (화면 공간 최적화)
- `st.tabs()` → `st.sidebar.radio()` + `if/elif` 페이지 라우팅

### v5.9 — 2026-05-22

**🏗️ 프로덕션 Ready + ML 엔진 v2 + OCR 완료**

**AI Agent 4기능 (Gemini 무료 API):**
- 공고 분석 에이전트: "이 공고가 InterX에 왜 맞는지" 1문장 + 제안 전략 자동 생성
- 질의응답 챗봇: "A등급 스마트공장 관련은?" 자연어 질문 → 수집 데이터 기반 RAG 답변
- 일일 브리핑 자동 생성: 등급별/긴급/L3/정기공고 요약 → Slack/Telegram 전달
- 제안서 초안 LLM 강화: 공고 요구사항 → InterX 솔루션 매핑 → 전략 자동 작성
- Streamlit 대시보드: 공고 상세에 💡 AI 분석 버튼 + 💬 AI 챗봇 탭 (13번째)
- API 키 없어도 규칙 기반 fallback 동작 (무료 발급: aistudio.google.com/apikey)
- 파이프라인 Step 18: 실행 완료 시 AI 브리핑 자동 생성

**엔진 최적화 — 개발팀 즉시 연동 가능:**
- `pyproject.toml`: 표준 Python 패키지 (`pip install -e ".[dev]"`)
- `Dockerfile` + `docker-compose.yml`: 원커맨드 빌드/실행
- FastAPI REST API (`/api/v1/`): 공고 CRUD + 통계 + 파이프라인 실행
- GitHub Actions CI: push/PR 자동 lint(ruff) + 테스트
- `Makefile`: `make test`, `make run`, `make api`, `make docker-build`
- `conftest.py`: 테스트 환경 표준화 (sys.path 해킹 제거)
- `.env.example` 보강, `.dockerignore` 추가

**ML 수주예측 엔진 v2:**
- 피처 12개로 확장: fitness, priority, budget_score, dday_urgency, l3_flag, industry_score, tfidf_similarity, keyword_density, type_multiplier, combo_count, budget_grade, urgency_boost
- GradientBoosting / RandomForest / VotingClassifier 앙상블 지원 (50건+ 자동 GBM 전환)
- 파이프라인 실행마다 JSONL 학습 데이터 자동 내보내기 (`data/exports/training/`)
- Streamlit 대시보드에 ML 모델 정보 배너 + 학습 버튼 + 피처 중요도 차트
- 수주 예측 탭 전면 개선: v2 피처별 기여도 시각화, InterX 유사도/콤보 키워드 표시

**버그 수정:**
- 부산테크노파크(BTP) 수집기: 페이지네이션("443 페이지") 공고 혼입, 제목 중복, 상세 URL 메인페이지 연결 문제 수정
- 통합 테스트 4건 실패 수정 (설정값 변경 반영: l3=30, partner=18, 등급=A/B/C/D)
- 전체 201건 테스트 통과 (unit 143 + integration 58)
- 스마트공장 nttId 중복 방지 정상 작동 확인
- 모든 25개 수집기 등록 및 설정 정상 확인

**OCR 문서 파싱 구현 (Phase 1~3):**
- Phase 1: pdfplumber 텍스트 기반 PDF + 테이블 추출 (Streamlit Cloud 호환) + pypdf fallback
- Phase 2: pytesseract + pdf2image 스캔 PDF OCR (로컬/Tesseract 설치 필요)
- Phase 3: HWP 바이너리 파싱 (olefile + zlib Section 스트림) + DOCX (python-docx)
- `base_collector` 자동 연동: body_text < 200자 + 첨부파일 있으면 OCR 보강
- 통합 dispatcher: 확장자별 자동 분기 (`.pdf` → `.docx` → `.hwp`)
- 실전 추출 테스트 37건 (한글 PDF/DOCX/HWP 실제 파일 생성 → 추출 검증)

**아키텍처 개선:**
- 콤보 키워드 80쌍 → `scoring.yaml` 외부화 (코드 하드코딩 제거, 핵심 원칙 준수)
- 상태변경로그: `log_status_change.py` → 검토상태/BD마일스톤 변경 이력 자동 기록 → `97_상태변경로그` 시트
- Streamlit OCR 표시: 첨부파일 OCR 보강 시 📎 OCR 캡션
- 수집기 전체 점검: 테크노파크 12개 + 기타 7개 모두 bad=0 확인

### v5.8 — 2026-05-21

**🎯 스코어링 정밀화 — 비제조AI 공고 오탐 대폭 감소**

- **CORE_KEYWORDS 범용 단어 14개 제거**: `ai`, `인공지능`, `품질`, `안전`, `공정`, `데이터`, `로봇`, `클라우드`, `플랫폼`, `poc`, `agent`, `에이전트`, `스케줄링`, `실증`
  - 이들은 POSITIVE_KEYWORDS에서 가점만 부여 (코어 게이트 통과 X)
  - "디지털 품질 컨설팅", "AI 교육", "데이터분석 교육" 등 오탐 방지
- **제조 맥락 복합어 추가**: `공정최적화`, `품질검사`, `품질ai`, `안전ai`, `로봇자동화`, `산업로봇`, `협동로봇`
- **NEGATIVE_KEYWORDS 20개+ 신규**: 해양/수산, 탄소중립/RE100, 농촌, 우주/항공, 리빙랩, 평가위원/심사위원, SW품질/테스팅, 해외마케팅, 판로개척, 지식산업센터, 상장/IPO, 화장품, 치유산업, 인력양성, 위탁운영
- **핵심 내용 잡음 필터 강화**: "작성일", "조회수", "다운로드", "첨부파일", "담당자 연락처" 등 메타데이터 패턴 제거
- **대시보드 iframe 복원**: A등급 공고에서 원문 사이트 미리보기 iframe 다시 표시 + 차단 안내 메시지

### v5.7 — 2026-05-21

**📰 뉴스 피드 복구 + 핵심 요약 + 본문 품질 대폭 개선**

**뉴스 피드 수정**
- IT·산업 동향 카테고리 깨진 RSS 3개 전량 교체
  - ZDNet Korea(404) → 전자신문 IT, 디지털타임스(404) → 디지털데일리, IT조선(접속불가) → 테크M
- 뉴스 핵심 요약: RSS `content:encoded` 파싱 + 본문에서 핵심 문장 3개 자동 추출
- **원문 상세 요약**: 기사 페이지 직접 방문 → `<p>` 태그 본문에서 5문장 핵심 추출 (1시간 캐시)

**본문 요약 품질 개선 (수집기)**
- `_parse_detail_page` 전면 개편: 25개 본문 컨테이너 선택자 우선 탐색 (`board_view`, `view_content`, `bbs_view` 등)
- 잡음 자동 필터링: 메뉴/네비/푸터 텍스트 패턴 제거 (`_JUNK_RE` — 로그인, 회원가입, 주메뉴바로가기, MAIN TOPIC 등)
- `_extract_smart_summary()`: 구조화 섹션(사업목적/지원내용) → 핵심 키워드 문장 → 첫 유의미 문장 순서로 요약 생성
- 본문 영역 못 찾을 시 가장 긴 텍스트 블록 div 자동 선택

**대시보드 표시 개선**
- 대시보드 공고 요약: 구조화 섹션 우선 → summary 필드 → 키워드 매칭 문장 3개 추출 (기존 `body[:300]` 무조건 자르기 폐지)
- 공고 목록 탭: "공고 핵심 내용" expander — 사업목적/지원내용/지원대상/지원금액/신청방법/추진일정 6개 구조화 섹션 + 전체 본문
- `{{...}}` Vue/React 템플릿 변수 자동 제거

**수집기 버그 수정**
- GJTP 원문 바로가기 메인페이지 이동 버그: `BASE` URL에 `/home/business.cs` 경로 누락 → 수정
- 제주TP Vue SPA 템플릿 노출: `fetch_detail=False` 설정 (상세 HTML에 `{{...}}`만 있음)
- iframe X-Frame-Options 차단 대응: "원문 바로가기(새 탭)" 링크를 상단 배치 + 차단 안내 메시지
- `st.iframe()` scrolling 파라미터 미지원 에러 수정

### v5.6 — 2026-05-21

**🐛 수집기 버그 일괄 수정 + iframe 안정화**
- **BTP 페이지네이션 파싱 버그 수정**: "443 페이지", "처음 페이지" 등 페이지 네비게이션 텍스트가 공고 제목으로 수집되던 버그 → `_PAGINATION_TITLE_RE` 정규식 필터 추가
- **GWTP detail URL 404 수정**: Base64 `bbs_data` 파라미터의 `||` 접미사가 URL 인코딩 시 `%7C%7C`로 변환되어 404 → `_parse_page` 오버라이드에서 `||` 제거
- **CBTP SSL 우회**: HTTP→HTTPS 강제 리다이렉트 + DH_KEY_TOO_SMALL → `ssl_verify=False` 설정
- **SJTP/UTP LINK_PATTERN 수정**: `bo_table=` → `wr_id=` (개별 게시글만 매칭, 페이지네이션 링크 제외)
- **SeoulTP/PTP detail enrichment 비활성화**: javascript: 링크 기반 (POST 폼 제출) → 정적 URL 추출 불가, `fetch_detail=False`
- **`_parse_table` javascript: 필터**: base_collector의 테이블 파싱에서 javascript: href 스킵 추가
- **`st.components.v1.iframe` → `st.iframe`**: deprecated API 제거 (2026-06-01 deadline 대응)

### v5.4 — 2026-05-21

**🔧 안정화 + 수주분석 강화 + 원문 미리보기**
- **탭 리셋 문제 해결**: `st.form()`으로 수집 설정 래핑 → selectbox 변경 시 대시보드로 넘어가는 버그 수정
- **고장 사이트 8개 비활성화** (27개 → 19개 활성)
  - 404: 경기TP, 강원TP, 경남TP, 포항TP
  - SSL/타임아웃: 충북TP(DH_KEY_TOO_SMALL), 인천TP(ConnectTimeout)
  - 기타: 세종TP(0건), 울산TP(비공고 페이지 수집)
- **수주예측 TOP10 분석 근거**: 각 공고 클릭 시 가중치별 기여도 바 차트 + 핵심 근거 표시
  - 키워드 적합도(35%), 우선순위(25%), 예산(15%), 긴급도(10%), L3(10%), 솔루션(5%) 분해
- **원문 사이트 미리보기**: 대시보드 A등급 공고 + 공고 상세에서 iframe으로 원문 페이지 직접 표시
- **Arrow 직렬화 에러 수정**: D-day 컬럼 int+string 혼합 → string 통일
- **Playwright 미설치 정리**: Streamlit Cloud에서는 설치 불가 → kiat/iitp/smart_factory/ketep/bizinfo는 로컬 전용

### v5.2 — 2026-05-21

**🏗️ 테크노파크 12개 신규 + 2026 프로젝트 키워드 대량 추가**
- **수집 사이트 27개로 확대** (기존 16개 → 27개)
  - 신규 테크노파크 12개: 서울TP, 경기TP, 경기대진TP, 인천TP, 강원TP, 세종TP, 충북TP, 충남TP, 부산TP, 울산TP, 경남TP, 포항TP
  - `_TechnoBaseCollector` 공통 베이스 클래스 (4단계 파싱: 링크패턴 → 테이블 → li → fallback)
  - `technopark_collectors.py` 단일 파일 통합 (12개 클래스)
- **dicia(의료기기산업협회) 비활성화** — 제조AI 범위 외
- **2026 신규 과제 키워드 30개+** 대량 추가
  - CORE: 에이전틱AI, 자율공정, DTaaS, 테스트베드, 소부장, 혁신바우처, 피지컬AI, 물류자동화, AI선박, AI반도체
  - POSITIVE: 에이전틱AI(6), 피지컬AI(5), 제조DTaaS(6), AI+X(5), 자율공정(5), Multi AI Agent(6) 등 40항목
  - COMBO: (에이전틱,ai,6), (피지컬,ai,6), (dtaas,제조,6), (multi,agent,6) 등 15쌍 신규
  - L3 강공고 키워드: 에이전틱AI, 피지컬AI, 제조DTaaS, 자율공정, 제조DX멘토 추가
- **솔루션맵 업데이트**: GenAI(에이전틱AI/피지컬AI), ManufacturingDT(자율공정/DTaaS), InfraDS(AI반도체) 확장

### v5.1 — 2026-05-21

- **키워드 차트 필터 강화**
  - "2026" 등 순수 숫자(연도/금액) 제목 빈출 단어에서 제외
  - 불용어 30개+ 추가 (프로그램, 센터, 재공고, 산업, 기업, 육성 등)
  - 의미 있는 키워드만 표시 (AI, 제조, 스마트공장, 디지털트윈 등)

### v5.0 — 2026-05-20

**🏢 Enterprise UI v5 + 프로젝트 대규모 정리**
- **interxlab.com 공식 디자인 시스템 적용**
  - `--accent-color: #FF8000` (공식 오렌지)
  - `--accent2-color: #3A7BEE` (공식 블루)
  - `--primary-color: #000` (블랙 네비게이션, 버튼)
  - 버튼: 블랙 → 호버 시 오렌지 전환 / 카드: 오렌지 글로우 호버
  - 인트로: 블랙 배경 + 화이트 INTER + 오렌지 X
- **Enterprise 컴포넌트 시스템**: Metric Card, Notice Row, Status Pill, Section Header, Empty State
- **프로젝트 정리 (-12,000줄)**: archive/ 전체 삭제, 레거시 루트 파일 제거
- **코드 48% 압축**: 1,076줄 → 563줄 (기능 100% 유지)

### v4.5

**🎨 프리미엄 UI 리디자인**
- InterX 브랜드 테마 적용: 화이트 배경 + 오렌지(`#F5921B`) + 다크그레이(`#3C3C3C`)
- Google Inter 폰트, 로고 인트로 애니메이션 (INTER**X** fadeIn/fadeOut)
- KPI 카드 호버 효과, 공고 카드 왼쪽 보더 애니메이션, 오렌지 그라디언트 버튼
- 프리미엄 SaaS 수준 디자인 퀄리티

**🧠 스코어링 v3 전면 고도화 (6가지 개선)**
1. **위치 가중치**: 제목(×3.0) > 요약(×1.5) > 핵심텍스트(×1.2) > 본문(×0.5)
2. **예산 구간 점수**: 한글 예산 파싱 → 0~10점 (1억 이하 3점 ~ 50억 이상 10점)
3. **공고 유형 분류**: 실증(×1.25) / R&D(×1.15) / 구축(×1.10) / 바우처(×1.0) / 인력(×0.5)
4. **TF-IDF 프로필 매칭**: InterX 수행사업 프로필과 코사인 유사도 → 최대 +15점
5. **키워드 밀도**: 전체 단어 대비 적합 키워드 비율 → 최대 +8점
6. **긴급도 부스트**: 등급×마감일 교차 부스트 (A등급+D-3일 → +22.5점)

**📊 신규 기능 3가지**
- **공고 상세 보기**: 점수 상세, 키워드 태그, 솔루션 점수, 본문 미리보기
- **Excel 다운로드 강화**: 전체 필드 포함 .xlsx 다운로드
- **수집 히스토리 탭 (11번째 탭)**: 실행 이력, 등급 비교 트렌드, 사이트별 변화 추적

**🔧 실제 사업 데이터 기반 키워드 70건+ 추가**
- InterX 실제 수행 과제명(AI 용접, 자율 운영, 예지보전, AI Agent 등)에서 추출
- 콤보 키워드 25쌍 추가 (자율운영+제조, agent+제조, 암묵지+ai 등)
- 테스트 15/15건 PASS (실제 InterX 과제 제목 → A/B 등급 정확 분류)

---

## 1. 한눈에 보기

```
20개+ 정부사이트
  └─ 병렬 크롤링 (requests / Playwright)
      └─ 3겹 필터 (기본 → L3 → 키워드)
          └─ 스코어링 (fitness → priority → grade A/B/C/D)
              └─ 부가 분석 (정기공고 탐지 / win_probability / 클러스터링)
                  └─ Google Sheets 9시트 자동 업로드
                      └─ Slack/Telegram 알림
```

| 항목 | 수치 |
|------|------|
| 수집 사이트 | 25개 활성 (requests 20개, Playwright 5개) |
| 파이프라인 단계 | 18단계 (AI 브리핑 포함) |
| 유즈케이스 | 27개 (스코어링, 중복제거, 경쟁사, 제안서, ML예측, 유사공고, 스마트알림 등) |
| 정기공고 패턴 | 18그룹, 120+ aliases (priority 1/2/3 등급) |
| 콤보 키워드 | 80쌍 (두 키워드 동시 출현 시 가점) |
| 감점 분류 | 3단계 — Strong 91개(×6.0) / Medium 48개(×4.0) / Weak 12개(×2.0) |
| 등급 | A / B / C / D |
| 경쟁사 추적 | Tier1(6사) + Tier2(10사) + 파트너(7곳) |
| 솔루션 프로필 | 8개 (ManufacturingDT ~ PdM) |
| 수주 예측 | Rule 가중합 + ML(LogisticRegression) 자동 전환 |
| Sheets 시트 수 | 10개 (97_상태변경로그 포함) |
| 웹 플랫폼 | FastAPI + Tailwind (4페이지 + 6 API) |
| REST API | FastAPI 7 엔드포인트 (Swagger UI 자동 생성) |
| 팀 배포 앱 | Streamlit Cloud (11개 탭, 무료 호스팅) |
| AI Agent | Gemini 무료 (공고분석 + 챗봇 + 브리핑 + 제안서) |
| 단위 테스트 | 324건 전체 통과 (UC 36 + 파싱 정확도 107 포함) |
| CI/CD | GitHub Actions (자동 lint + test on push) |
| 패키징 | pyproject.toml + Docker + docker-compose |
| 실행 주기 | 1일 2회 (07:00 / 14:00, Colab 또는 로컬) |

---

## 2. 빠른 실행

### 2-A. 개발 환경 셋업 (신규 팀원 온보딩)

```bash
# 1) 클론
git clone https://github.com/KimDoojin2/interx-gov-intelligence.git
cd interx-gov-intelligence

# 2) 가상환경 + 의존성
python -m venv venv
venv/Scripts/activate          # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"        # 패키지 + pytest + ruff

# 3) 환경변수
cp .env.example .env           # 실제 값으로 수정

# 4) 테스트 실행 (201건 통과 확인)
pytest tests/unit/ -v --tb=short

# 5) Dry-run 파이프라인 테스트 (실제 수집 없이)
python run_engine.py --dry-run
```

### 2-B. 실행 옵션

```bash
# 기본 실행 (수집 → 스코어링 → Sheets 업로드)
python run_engine.py

# 전체 실행 (클러스터링·파트너매칭·알림 포함)
python run_engine.py --full

# 개발/테스트용
python run_engine.py --dry-run        # Mock 데이터로 실행
python run_engine.py --no-sheets      # Sheets 업로드 생략
python run_engine.py --no-alert       # 알림 생략
python run_engine.py --no-detail      # 상세 페이지 방문 생략 (빠름)
python run_engine.py --sites bizinfo,kiat,nipa  # 특정 사이트만

# 테스트
pytest tests/unit/ -v --tb=short      # 단위 테스트
pytest tests/ -v                      # 전체 (unit + integration)

# 대시보드 UI
streamlit run streamlit_app.py

# REST API (프론트엔드 연동)
python -m interx_engine.api           # http://localhost:8000/docs
```

### 2-C. Docker (원커맨드 실행)

```bash
# 빌드
docker build -t interx-engine .

# 파이프라인 1회 실행
docker compose --profile engine up

# 대시보드 (http://localhost:8501)
docker compose --profile dashboard up

# REST API (http://localhost:8000/docs)
docker compose --profile api up

# 전체
docker compose --profile all up -d
```

### 2-D. Playwright 사이트 (bizinfo, kiat, ketep, smart_factory, iitp)
```bash
python -m playwright install chromium
```

### 2-E. REST API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| GET | `/api/v1/notices` | 공고 목록 (필터·정렬·페이징) |
| GET | `/api/v1/notices/{id}` | 공고 상세 |
| GET | `/api/v1/notices/urgent` | 긴급 마감 공고 |
| GET | `/api/v1/stats` | 통계 (등급별·사이트별) |
| GET | `/api/v1/pipeline/status` | 마지막 실행 상태 |
| POST | `/api/v1/pipeline/run` | 파이프라인 수동 실행 |

Swagger UI: `http://localhost:8000/docs`

---

## 3. 아키텍처 — 3레이어 클린 구조

```
┌──────────────────────────────────────────┐
│  core/                                    │  ← 도메인 순수 로직, 외부 의존성 없음
│    entities/  notice, score_card, ...     │
│    rules/     scoring_policy, l3_policy   │
└───────────────┬──────────────────────────┘
                │ 의존 방향 (단방향)
┌───────────────▼──────────────────────────┐
│  application/                             │  ← 유스케이스 & 오케스트레이터
│    use_cases/ score, dedupe, cluster ...  │
│    ports/     (인터페이스 정의)            │
│    mappers/   notice_mapper, kpi_mapper   │
│    orchestrators/ daily_pipeline          │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  infrastructure/                          │  ← 실제 외부 구현체
│    collectors/   requests / Playwright    │
│    sheets/        Google Sheets API       │
│    alert/         Slack / Telegram        │
│    clustering/    TF-IDF / Embedding      │
│    persistence/   SQLite                  │
└──────────────────────────────────────────┘
```

**규칙**: 의존 방향은 항상 `infrastructure → application → core`. 역방향 금지.

---

## 4. 디렉토리 구조

```
interx_gov_intelligence/
├── run_engine.py                          # 단일 진입점 (CLI 파싱 → 오케스트레이터 호출)
├── streamlit_app.py                       # Streamlit Cloud 대시보드 (Enterprise v5)
├── assets/
│   └── hero_earth.png                     # 히어로 배너 이미지 (지구 일출)
├── configs/                               # 모든 설정값 YAML (코드에 하드코딩 금지)
│   ├── scoring.yaml                       # 점수 가중치, 등급 컷, 키워드 전체
│   ├── sites.yaml                         # 수집 사이트 목록 (enabled 플래그)
│   ├── recurring.yaml                     # 정기공고 패턴 (name + aliases)
│   ├── manager_rules.yaml                 # 담당자 자동 배정 규칙
│   ├── sheets.yaml                        # Google Sheets 시트명·컬럼 매핑
│   ├── settings.yaml                      # 타임아웃·페이지수 등 전역 설정
│   └── competitors.yaml                   # 경쟁사 추적 키워드
│
└── src/interx_engine/
    ├── core/                              # ← 외부 의존성 없는 순수 도메인
    │   ├── entities/
    │   │   ├── notice.py                  # 공고 엔티티 (데이터 컨테이너)
    │   │   ├── score_card.py              # 채점 결과 (fitness, grade, solutions)
    │   │   ├── prediction_result.py       # 수주 예측 결과
    │   │   ├── cluster.py                 # 공고 클러스터 그룹
    │   │   ├── partner.py                 # 파트너사
    │   │   ├── recommendation.py          # BD 추천 액션
    │   │   ├── analysis_report.py         # 포트폴리오 분석 리포트
    │   │   └── attachment.py              # 첨부파일 메타
    │   └── rules/
    │       ├── priority_scoring_policy.py # ★ 핵심 스코어링 로직 전체
    │       ├── l3_strong_policy.py        # L3 강공고 키워드 사전 필터
    │       └── recommendation_rules.py    # BD 액션 추천 규칙
    │
    ├── application/                       # ← 유스케이스 (비즈니스 흐름)
    │   ├── ports/                         # 인터페이스(추상) 정의
    │   │   ├── notice_collector_port.py
    │   │   ├── sheet_gateway_port.py
    │   │   ├── alert_gateway_port.py
    │   │   └── partner_repository_port.py
    │   ├── use_cases/                     # 단일 책임 유스케이스
    │   │   ├── score_notices.py           # 스코어링 실행
    │   │   ├── deduplicate_notices.py     # TF-IDF 유사도 중복 제거
    │   │   ├── detect_recurring.py        # 정기공고 패턴 매칭
    │   │   ├── detect_changes.py          # 공고 변경 감지 (제목/예산/마감일)
    │   │   ├── assign_manager.py          # 담당자 자동 배정
    │   │   ├── assign_milestone.py        # BD 마일스톤 배정 (M01/M05/P01)
    │   │   ├── track_competitors.py       # 경쟁사 공고 감지
    │   │   ├── match_partners.py          # 파트너사 공고 매칭
    │   │   ├── recommend_notices.py       # BD 추천 액션 생성
    │   │   ├── cluster_notices.py         # 공고 클러스터링
    │   │   ├── alert_notices.py           # 알림 발송 (Slack/Telegram)
    │   │   ├── site_quality_grader.py     # 사이트 수집 품질 A~D 등급
    │   │   ├── deep_parsing.py            # 첨부파일(PDF/HWP) 정밀 파싱
    │   │   ├── portfolio_analysis.py      # pandas 기반 포트폴리오 분석
    │   │   ├── win_prediction.py          # ★ 수주 가능성 예측 (룰/ML)
    │   │   ├── generate_proposal.py       # 제안서 초안 Word .docx 자동 생성
    │   │   ├── export_training_data.py    # ML 학습데이터 JSONL 저장
    │   │   ├── summarize_l3.py            # L3 공고 Claude API 요약
    │   │   ├── auto_analysis.py           # 비지도학습 자동 분석 (9패널 PNG)
    │   │   ├── download_attachments.py    # 첨부파일 다운로드
    │   │   └── log_pipeline_run.py        # 파이프라인 실행 로그
    │   ├── mappers/
    │   │   ├── notice_mapper.py           # Notice+ScoreCard → Sheets 행 딕셔너리
    │   │   ├── kpi_mapper.py              # 실행 통계 행 빌더
    │   │   └── attachment_mapper.py       # 첨부파일 행 변환
    │   └── orchestrators/
    │       ├── daily_pipeline.py          # ★ 수집→스코어링→업로드 전체 흐름
    │       └── full_pipeline.py           # daily + 클러스터링·파트너매칭·알림
    │
    ├── infrastructure/                    # ← 외부 시스템 구현체
    │   ├── collectors/
    │   │   ├── collector_factory.py       # 사이트코드 → 콜렉터 인스턴스 팩토리
    │   │   ├── html_utils.py              # HTML 파싱 공통 유틸
    │   │   └── sites/
    │   │       ├── base_collector.py      # BaseCollector / PlaywrightBaseCollector 추상
    │   │       ├── bizinfo_collector.py   # 기업마당 (Playwright)
    │   │       ├── kiat_collector.py      # 한국산업기술진흥원 (Playwright)
    │   │       ├── nipa_collector.py      # 정보통신산업진흥원
    │   │       ├── innopolis_collector.py # 연구개발특구진흥재단
    │   │       ├── smart_factory_collector.py # 스마트제조혁신추진단 (Playwright)
    │   │       ├── bipa_collector.py      # 부산정보산업진흥원
    │   │       ├── uipa_collector.py      # 울산정보산업진흥원
    │   │       ├── gicon_collector.py     # 광주전남연구원
    │   │       ├── ttp_collector.py       # 대전테크노파크
    │   │       ├── dicia_collector.py     # 의료기기산업협회 (Playwright)
    │   │       ├── gjtp_collector.py      # 광주테크노파크
    │   │       ├── new_collectors.py      # KISED·KETEP·KOIIA·JEJUTP (멀티)
    │   │       ├── technopark_collectors.py # 테크노파크 12개 통합 (v5.2)
    │   │       └── mock_notice_collector.py # 테스트용 Mock
    │   ├── sheets/
    │   │   ├── google_sheet_gateway.py    # 실제 Google Sheets API 연동
    │   │   └── console_sheet_gateway.py   # 로컬 개발용 콘솔 Fallback
    │   ├── alert/
    │   │   ├── slack_gateway.py           # Slack Webhook 알림
    │   │   └── telegram_gateway.py        # Telegram Bot 알림
    │   ├── clustering/
    │   │   ├── tfidf_clusterer.py         # TF-IDF + cosine 클러스터링 (기본)
    │   │   └── embedding_clusterer.py     # Sentence-Transformers 임베딩 (선택)
    │   ├── persistence/
    │   │   └── sqlite_writer.py           # SQLite 영속성 (data/interx.db)
    │   ├── analysis/
    │   │   ├── pandas_analyzer.py         # pandas 통계 분석
    │   │   └── sklearn_clusterer.py       # sklearn PCA·KMeans·IsoForest
    │   ├── storage/
    │   │   ├── csv_writer.py              # CSV Fallback 저장
    │   │   └── file_downloader.py         # 첨부파일 다운로더
    │   ├── matching/
    │   │   └── csv_partner_repository.py  # CSV 기반 파트너 저장소
    │   ├── config/
    │   │   ├── settings_loader.py         # 설정 싱글턴 (settings.yaml)
    │   │   └── yaml_loader.py             # YAML 로딩 유틸
    │   └── utils/
    │       ├── budget_parser.py           # 예산 문자열 정규화 ("2억원" → 200000000)
    │       └── morpheme_scorer.py         # 형태소 기반 점수 계산
    │
    └── interfaces/
        └── dashboard/
            └── app.py                     # Streamlit 대시보드 UI
```

---

## 5. 파이프라인 17단계 상세

`run_engine.py` → `DailyPipelineOrchestrator.run()` 순으로 아래 17단계 실행.

```
[1]  수집 (Collect)
     └─ sites.yaml의 enabled: true 사이트를 ThreadPoolExecutor로 병렬 크롤링
        각 콜렉터: 목록 페이지 순회 → 상세 페이지 방문 → Notice 객체 생성

[2]  notice_id 중복 제거
     └─ notice_id = site_code + URL MD5(8자리)
        동일 notice_id는 수집 즉시 제거 (같은 실행 내 중복)

[2B] SQLite 기존 공고 필터
     └─ data/interx.db 에 30일 내 동일 notice_id 존재 시 is_new=False 마킹
        (완전 제거 아님 — 변경 감지를 위해 유지)

[3]  마감 지난 공고 제거
     └─ deadline_date < 오늘 → 자동 제거

[4]  스코어링 (Scoring)
     └─ PriorityScoringPolicy.calculate(notice) → ScoreCard
        코어 키워드 체크 → 가점/감점 계산 → 솔루션별 점수 → grade A/B/C/D

[5]  TF-IDF 중복 제거
     └─ 공고 제목 TF-IDF 벡터화 → cosine 유사도 0.85 이상 쌍 감지
        점수 낮은 쪽 제거 (TfidfClusterer)

[6]  변경 감지 (Change Detection)
     └─ 이전 실행 대비 제목·예산·마감일 변경 시 notice.is_changed = True

[7]  담당자 자동 배정
     └─ manager_rules.yaml 키워드 + ministry 매칭 → notice.manager 배정
        매칭 실패 시 "미배정"

[7B] BD 마일스톤 자동 배정
     └─ L3강공고=Y + D-day 기준으로 M01/M05/P01 자동 배정

[8]  경쟁사 트래킹
     └─ competitors.yaml 키워드 포함 공고 → notice.competitor_flag = True

[9]  사이트별 품질 등급
     └─ 수집 성공률·A/B 비율로 사이트별 데이터 품질 A~D 등급 산출

[10] 행 빌드 (Row Build)
     └─ NoticeMapper: Notice + ScoreCard → Google Sheets 업로드용 딕셔너리
        KpiMapper: 실행 통계 행 생성

[11] 부가 분석 (병렬 처리)
     ├─ 정기공고 탐지:    recurring.yaml 패턴 매칭 → recurring_flag/group 설정
     ├─ DeepParsing:      첨부파일(PDF/HWP) 본문 추가 파싱 → 예산·KPI 보강
     ├─ L3 AI 요약:       Claude API로 L3 강공고 자동 요약 (ANTHROPIC_API_KEY 필요)
     ├─ 포트폴리오 분석:   pandas 기반 등급 분포·키워드 트렌드 리포트
     ├─ 수주 예측:         rule_v1 가중합 or sklearn ML 모델 자동 선택
     └─ 제안서 생성:       A/B등급 공고 Word .docx 초안 자동 생성

[12] KPI / 실행 로그 빌드
     └─ 수집수·등급분포·소요시간 등 통계 행 생성

[13] 학습 데이터 자동 Export
     └─ 전체 공고(C/D 포함)를 JSONL로 data/exports/training/ 저장
        → 향후 Win Prediction ML 학습 데이터 누적

[14] Google Sheets 업로드
     └─ 9개 시트에 분산 저장 (상세는 섹션 13 참조)

[15] SQLite 저장
     └─ data/interx.db 에 실행 결과 영속화

[16] 알림 발송 (--full 옵션 시)
     └─ L3 강공고 즉시 알림 + 일별 요약 (Slack 또는 Telegram)

[17] 자동 비지도학습 분석 + PNG 생성
     └─ PCA·KMeans·IsolationForest → 9패널 차트 PNG 자동 저장
        data/analysis/dashboard_EXEC-YYYYMMDD-HHMMSS.png
```

---

## 6. 수집 (Collector)

### 6-1. 사이트별 수집 방식

| 사이트 코드 | 기관명 | 수집 방식 | 비고 |
|------------|--------|----------|------|
| `bizinfo` | 기업마당 | Playwright | JS 렌더링 필수 |
| `kiat` | 한국산업기술진흥원 | Playwright | Vue.js SPA |
| `nipa` | 정보통신산업진흥원 | requests | |
| `innopolis` | 연구개발특구진흥재단 | requests | |
| `smart_factory` | 스마트제조혁신추진단 | Playwright | React SPA, nttId 기반 중복키 (URL MD5 → nttId) |
| `bipa` | 부산정보산업진흥원 | requests | |
| `uipa` | 울산정보산업진흥원 | requests | |
| `gicon` | 광주전남연구원 | requests | |
| `ttp` | 대전테크노파크 | requests | |
| `gjtp` | 광주테크노파크 | requests | |
| `kised` | 창업진흥원 | requests | new_collectors.py |
| `ketep` | 에너지기술평가원 | Playwright | 2025~ /businessAcment URL |
| `koiia` | 산업지능화협회 | requests | new_collectors.py |
| `jejutp` | 제주테크노파크 | requests | |
| `iitp` | 정보통신기획평가원 | Playwright | Vue.js SPA |
| `seoultp` | 서울테크노파크 | requests | v5.2 신규 |
| `gtp` | 경기테크노파크 | requests | v5.2 신규 |
| `gdtp` | 경기대진테크노파크 | requests | v5.2 신규 |
| `itp` | 인천테크노파크 | requests | v5.2 신규 |
| `gwtp` | 강원테크노파크 | requests | v5.2 신규 |
| `sjtp` | 세종테크노파크 | requests | v5.2 신규 |
| `cbtp` | 충북테크노파크 | requests | v5.2 신규 |
| `ctp` | 충남테크노파크 | requests | v5.2 신규 |
| `btp` | 부산테크노파크 | requests | v5.2 신규 |
| `utp` | 울산테크노파크 | requests | v5.2 신규 |
| `gntp` | 경남테크노파크 | requests | v5.2 신규 |
| `ptp` | 포항테크노파크 | requests | v5.2 신규 |
| | | | |
| *비활성* | | | |
| `dicia` | 의료기기산업협회 | Playwright | 제조AI 범위 외 → 비활성 |
| `iris` | IRIS | requests | 로그인 필수로 비활성 |
| `smba` | 중소벤처기업부 | requests | 서버 차단으로 비활성 |
| `gbtp` | 경북테크노파크 | — | IP 차단으로 비활성 |
| `nrf` | 한국연구재단 | requests | 500 서버에러 → 비활성 |

### 6-2. 2단계 수집 흐름

```
1단계 — 목록 페이지 (_parse_page)
  목록 URL 순회 (pageIndex=1, 2, 3 ...)
    └─ requests: GET → BeautifulSoup lxml 파싱
    └─ Playwright: headless Chromium 렌더링 후 innerHTML 파싱

  각 행(tr/li)에서 추출:
    - 공고명 + 상세 URL (<a href>)
    - 날짜 (정규식: \d{4}[-./]\d{1,2}[-./]\d{1,2})
    - notice_id = site_code + URL MD5(8자리)
      (스마트공장: nttId 파라미터 기반 ID — URL 변형으로 인한 중복 방지)

  종료 조건: 공고 0건 페이지 감지 시 순회 중단
  딜레이: random.uniform(0.5, 1.2)초

2단계 — 상세 페이지 보강 (_enrich_notices)
  ThreadPoolExecutor (최대 3 워커) 병렬 방문

  각 상세 URL에서 추출:
    ① 본문 (body_text)
       BeautifulSoup → script/style/nav/header/footer 제거
       GNB/LNB/SNB div 메뉴 텍스트 오염 방지
       get_text(" ") → 연속 공백 제거 → 최대 8,000자

    ② 예산 (budget) — 우선순위 정규식:
       1. "지원금액 : N억원"
       2. "총 사업비 : N백만원"
       3. "과제당 : N억원"
       4. "최대 N억원"
       5. "N억원 이내/내외/규모"

    ③ 구조화 섹션 (structured)
       사업목적 / 지원내용 / 지원대상 / 지원금액 / 신청방법 / 추진일정
       섹션 헤더 키워드 탐지 → 다음 섹션까지 최대 300자

    ④ 첨부파일 (attachments)
       .pdf/.hwp/.hwpx/.docx/.xlsx 확장자 URL
       download/fileDown/atchFile 패턴 URL
       → {name, url} 목록

    ⑤ 접수상태 자동 분류 (classify_apply_status)
       본문에서 "접수기간: YYYY-MM-DD ~ YYYY-MM-DD" 패턴 파싱
       → 오늘 < 시작일: "접수예정"
       → 시작일 ≤ 오늘 ≤ 종료일: "접수중"
       → 오늘 > 종료일: "마감"
       패턴 미발견 시 deadline 기반 추정

  딜레이: random.uniform(0.3, 0.8)초
```

### 6-3. BaseCollector 핵심 속성

```python
class BaseCollector(ABC):
    site_key: str          # 사이트 코드 (예: "bizinfo")
    site_name: str         # 기관명 (예: "기업마당")
    list_url: str          # 목록 페이지 URL 템플릿
    max_pages: int         # 최대 수집 페이지 수 (settings.yaml)
    execution_id: str      # 파이프라인 실행 ID (EXEC-YYYYMMDD-HHMMSS)

    @abstractmethod
    def _parse_page(self, page: int) -> List[Notice]: ...

    def collect(self) -> List[Notice]:
        # 목록 수집 → 상세 보강 → 반환
```

---

## 7. 스코어링 알고리즘

`PriorityScoringPolicy.calculate(notice)` → `ScoreCard` 반환

### 7-1. 스코어링 대상 텍스트

```python
scored_text = 제목 + 요약 + 사업목적 + 지원내용   # 가점/감점 계산에 사용
full_text   = scored_text + body_text              # 코어 키워드 체크에만 사용
```

> **body_text를 scored_text에 포함하지 않는 이유**: 공고 본문에는 관련 없는 법령·안내문이 섞여 오염을 유발하기 때문.

### 7-2. 점수 계산 단계

```
Step 1. 코어 키워드 존재 확인 (full_text 기준)
        CORE_KEYWORDS = {제조, 스마트공장, AI, 데이터, 공정, 설비, 자동화, ...}
        → 최소 1개 이상 없으면 fitness = 0 → 즉시 D등급

Step 2. 가점 계산 (scored_text 기준)
        POSITIVE_KEYWORDS 딕셔너리 순회
        구조화 섹션(사업목적/지원내용) 히트 시 ×1.5 보너스
        예산 정보 존재 시 +3.0 보너스
        pos_score = Σ(키워드 가중치) × struct_bonus

Step 2B. 콤보 키워드 보너스 (80쌍)
         두 키워드가 scored_text에 동시 존재 시 추가 가점
         예: ("상생형", "선도모델") → +8, ("ai", "제조") → +5
         combo_bonus = Σ(매칭된 콤보 보너스)

Step 3. 감점 계산 — 3단계 차등 (scored_text 기준)
        STRONG (×6.0): 바이오/의료/건설/엔터/고용 — 완전 범위 외
        MEDIUM (×4.0): 교육/창업/전시회/금융 — 일부 관련 가능
        WEAK   (×2.0): 농업/식품/일반 콘텐츠 — 간접 관련 가능
        neg_score = Σ(strong×1.0 + medium×0.67 + weak×0.33) 비율 적용

Step 4. 적합도 계산
        fitness = pos_score × 5.0 - neg_score × 6.0 + struct_bonus + combo_bonus
        범위: 0.0 ~ 100.0 (min(100, max(0, ...)) 클램핑)

Step 5. 솔루션별 점수 (8개 솔루션)
        SOLUTION_MAP 각 항목의 키워드 합산 × scale(15)
        → 0~100점, 총 8개 값

Step 6. 산업 점수
        industry_score = 비0점 솔루션들의 평균

Step 7. 우선순위 계산
        priority = fitness × 0.6 + industry_score × 0.4
        (fitness = 0이면 priority 강제 0)

Step 8. 등급 분류
        A: priority ≥ 48   (최우선 영업 대상)
        B: priority ≥ 30   (검토 대상)
        C: priority ≥ 18   (모니터링)
        D: priority <  18  (해당 없음)

Step 9. 제목 블랙리스트 강제 D
        "수요기업" / "육성과정" / "시찰단" 포함 시
        → fitness=0, priority=0, grade=D 강제

Step 10. L3 강공고 확정
         fitness ≥ 30 AND 제목에 L3 키워드 존재
         → notice.l3_strong = "Y" (즉시 알림 대상)
```

### 7-2B. v3 고도화 — 6가지 추가 분석 (ScoreCard 확장 필드)

```
Step A. 위치 가중치 (Position Weighting)
        제목(×3.0) > 요약(×1.5) > 핵심텍스트(×1.2) > 본문(×0.5)
        → 제목에 핵심 키워드가 있을수록 높은 점수

Step B. 예산 구간 점수 (Budget Scoring)
        한글 예산 파싱: "10억원" → 10, "5천만원" → 0.5
        1억 이하: 3점 / 1~5억: 5점 / 5~10억: 7점 / 10~50억: 9점 / 50억+: 10점

Step C. 공고 유형 분류 (Type Classification)
        실증(×1.25) / R&D(×1.15) / 구축(×1.10) / 바우처(×1.0) / 인력(×0.5)
        → 유형별 보정 배율 적용

Step D. TF-IDF 프로필 유사도
        InterX 실제 수행 사업 프로필과 char_wb ngram(2,4) TF-IDF 코사인 유사도
        → 최대 +15점 보너스

Step E. 키워드 밀도 (Keyword Density)
        적합 키워드 히트 수 / 전체 단어 수 비율
        → 최대 +8점 보너스

Step F. 긴급도 부스트 (Urgency × Grade)
        A등급 + D-3일 → +22.5점 / A등급 + D-7일 → +15점
        B등급 + D-3일 → +12점
```

### 7-3. 솔루션별 키워드 맵 (SOLUTION_MAP 요약)

| 솔루션 | 대표 키워드 | 설명 |
|--------|------------|------|
| `ManufacturingDT` | 디지털트윈, 스마트공장, 자율형공장, AI팩토리 | 제조 디지털트윈 |
| `RecipeAI` | 레시피, 배합, 품질예측, 공정최적화 | 제조 레시피 AI |
| `QualityAI` | 품질관리, 불량검출, 이상탐지 | 품질 AI |
| `InspectionAI` | 머신비전, 비전검사, 외관검사 | 비전 검사 AI |
| `SafetyAI` | 중대재해, 안전관리, 작업자안전 | 안전 AI |
| `GenAI` | 생성형AI, GPT, LLM, AI에이전트 | 제조 GenAI |
| `InfraDS` | 데이터스페이스, AAS, Catena-X, 클라우드 | 데이터 인프라 |
| `PdM` | 예지보전, 설비관리, 고장예측, PHM | 예지보전 |

### 7-4. 콤보 키워드 (80쌍)

두 키워드가 동시에 scored_text에 존재할 때 추가 가점. 핵심 공고 탐지력 향상.

| 조합 예시 | 보너스 | 설명 |
|----------|--------|------|
| 상생형 + 선도모델 | +8 | 정부 핵심 정책 (최고 보너스) |
| 상생형 + 스마트공장 | +6 | 대중소 상생형 공장 구축 |
| ai + 제조 | +5 | 제조AI 핵심 |
| ax + 실증 | +5 | AX 실증 공고 |
| 탄소중립 + 스마트공장 | +5 | ESG 연계 제조 |
| dx + 제조 | +5 | 제조DX |
| 공급망 + ai | +4 | Catena-X / 공급망 디지털화 |
| 로봇 + ai | +4 | 지능형 로봇 제조 |

### 7-5. 가점/감점 키워드 예시

```yaml
# 가점 키워드 (점수 높을수록 인터엑스 적합)
스마트공장: 5, 스마트팩토리: 5
제조ai: 5,   제조AI: 5
디지털트윈: 4, 예지보전: 4, 자율형공장: 4
ai: 3,       머신비전: 3, 비전검사: 3
데이터: 2,   자동화: 2

# 감점 키워드 — 3단계 차등 감점
# STRONG (×6.0): 완전 범위 외
수요기업: 12, 일자리: 7, 세미나: 7
바이오: 5, 신약: 6, 건설공사: 5

# MEDIUM (×4.0): 일부 관련 가능
소상공인: 6, 교육생모집: 6, 전시회: 4

# WEAK (×2.0): 간접 관련 가능
농업: 4, 식품기업: 4, 문화: 2
```

---

## 8. 정기공고 탐지

`detect_recurring.py` — `configs/recurring.yaml` 패턴과 공고 제목을 매칭.

### 8-1. 동작 방식

```python
title = "2025년 스마트공장 구축지원 사업 통합 공고"

# recurring.yaml 패턴 순회 (priority 순 정렬 — 핵심공고 먼저 매칭)
for (group_name, aliases, priority) in _PATTERNS:
    for alias in aliases:
        if alias.lower() in title.lower():
            notice.recurring_flag     = "Y"
            notice.recurring_group    = group_name
            notice.recurring_priority = priority  # 1=핵심, 2=중간, 3=참고
            break
```

### 8-2. recurring.yaml 주요 패턴 (18그룹, 120+ aliases)

| Priority | 그룹명 | aliases 수 | 대표 aliases |
|----------|--------|-----------|-------------|
| **P1** | `스마트공장구축` | 13 | 스마트공장 구축, 스마트팩토리 구축, 보급확산, AI스마트공장 |
| **P1** | `제조혁신스마트공장` | 7 | 스마트제조혁신, 제조혁신사업, 스마트공장 확산 |
| **P1** | `AX-Sprint` | 9 | AX-Sprint, AX실증, 자율제조 AX, 자율형공장 AX |
| **P1** | `제조AI특화사업` | 12 | 제조AI특화, 산업AI솔루션, AI응용제품, 신속상용화 |
| **P1** | `상생형스마트공장` | 6 | 상생형 스마트공장, 상생형 선도모델, 대중소 상생형 |
| **P2** | `AI바우처` | 7 | AI바우처사업, 인공지능 바우처, AI바우처 지원사업 |
| **P2** | `데이터바우처` | 7 | 데이터바우처사업, 빅데이터 바우처 |
| **P2** | `디지털트윈R&D` | 7 | 디지털트윈 기술개발, 디지털트윈 실증, DT 실증 |
| **P2** | `신속실증특례` | 8 | 신속실증, PoC실증, 신속상용화, 실증사업 |
| **P2** | `글로벌스마트공장` | 8 | 글로벌 스마트공장, K-스마트공장, 해외스마트공장 |
| **P2** | `탄소중립스마트공장` | 9 | 탄소중립 스마트공장, 그린스마트공장, 넷제로스마트 |
| **P2** | `데이터스페이스` | 6 | 데이터스페이스, Catena-X, 제조데이터 공유 |
| **P2** | `공정최적화AI` | 5 | 공정최적화, AI 공정최적화, 공정혁신 |
| **P3** | `클라우드바우처` | 4 | 클라우드바우처사업, 클라우드 서비스 바우처 |
| **P3** | `중소기업기술개발` | 9 | 중소기업 기술개발, R&D 지원, 기술혁신개발사업 |
| **P3** | `규제샌드박스` | 6 | 규제샌드박스, 산업융합샌드박스, ICT규제샌드박스 |
| **P3** | `스마트공장전문인력` | 8 | 스마트공장 전문인력, 제조AI인력, 스마트제조인력양성 |
| **P3** | `스마트산업단지` | 8 | 스마트산업단지, 스마트산단, 디지털클러스터 |

> `recurring_flag = "Y"` 인 공고는 Google Sheets `01_영업기회_정보` 시트에 정기공고여부/정기공고그룹 컬럼에 자동 기재됩니다.
> priority 필드로 핵심(P1) 정기공고를 우선 매칭하여, 여러 패턴에 해당될 때 가장 중요한 그룹이 배정됩니다.

---

## 9. L3 강공고 정책

L3 = **직접 제안 대상** — 인터엑스가 직접 영업해야 하는 핵심 공고.

### 9-1. 판정 2단계

```
[사전 필터] L3StrongPolicy.is_l3_strong(notice)
  대상 텍스트: 제목 + 요약 + 사업유형 (소문자 변환)
  scoring.yaml의 l3_keywords 목록 중 1개 이상 포함 시 후보 마킹

[최종 확정] PriorityScoringPolicy.calculate()
  fitness ≥ 30 AND 사전 필터 통과 → notice.l3_strong = "Y"
```

### 9-2. L3 키워드 목록 (주요)

```
스마트공장 / 스마트팩토리 / 자율제조 / 자율공장 / 자율형공장
제조ai / 산업ai / 제조인공지능
디지털트윈 / 디지털 트윈
머신비전 / 비전검사 / 이상탐지
중대재해 / 제조안전
manufacturing-x / 공정최적화 / 예지보전
ai팩토리 / ai공장
산업ai에이전트 / ai에이전트 / ai응용제품 / 신속상용화
제조dx / 데이터스페이스 / catena-x / aas
```

### 9-3. L3 처리 흐름

```
L3강공고 = "Y"
    ├─ Sheets 02_L3강공고 시트에 별도 저장
    ├─ BD 마일스톤 M01 (공고 발굴) 또는 M05 (즉시 컨셉 제안) 자동 배정
    ├─ Telegram/Slack 즉시 알림 발송
    └─ Claude API 요약 (--full + ANTHROPIC_API_KEY 설정 시)
```

---

## 10. 수주 예측 (Win Prediction)

`win_prediction.py` — 공고별 수주 가능성 0~100% 예측.

### 10-1. 피처 가중치

| 피처 | 가중치 | 설명 |
|------|--------|------|
| `fitness_score` | **35%** | 키워드 매칭 적합도 (0~100 정규화) |
| `priority_score` | **25%** | 우선순위 점수 (0~100 정규화) |
| `budget_억` | **15%** | 지원금액 규모 (10억 기준 정규화, 초과 시 감소) |
| `dday_urgency` | **10%** | 마감 긴급도 (D-7이내 최고, 너무 여유있으면 낮음) |
| `l3_flag` | **10%** | L3 강공고 여부 (Y=1.0, N=0.0) |
| `industry_score` | **5%** | 솔루션 산업 적합도 점수 |

### 10-2. 등급 기준

| 등급 | win_probability | 의미 |
|------|-----------------|------|
| A | ≥ 75% | 즉시 투자 — 제안서 착수 |
| B | ≥ 55% | 검토 — 세부 검토 후 결정 |
| C | ≥ 35% | 관망 — 기회 모니터링 |
| D | < 35% | 제외 |

### 10-3. ML 모드 자동 전환

```
파이프라인 실행마다 data/exports/training/*.jsonl 누적
    ↓
영업팀 수주/탈락 결과 입력 (data/crm_memos.json)
    ↓
WinPredictionTrainer().train() 실행
→ LogisticRegression 학습 → data/models/win_pred_lr.pkl 저장
    ↓
이후 파이프라인: pkl 감지 → ML 모드 자동 전환 (rule_v1 대체)
```

> 최소 20건 이상 수주/탈락 실적 필요. 데이터 부족 시 rule_v1 가중합으로 동작.

---

## 11. 담당자 자동 배정 & BD 마일스톤

### 11-1. 담당자 자동 배정 (assign_manager.py)

`manager_rules.yaml` 에 정의된 규칙을 위에서부터 순서대로 매칭, 첫 번째 매칭 적용.

```yaml
rules:
  - name: "제조AI 전문"
    manager: "김BD"
    conditions:
      keywords: ["스마트팩토리", "제조ai", "디지털트윈", "예지보전", "머신비전"]

  - name: "R&D 사업"
    manager: "이연구"
    conditions:
      keywords: ["r&d", "연구개발", "기술개발"]
      ministry: ["과학기술정보통신부", "산업통상자원부"]

  - name: "중기부 바우처"
    manager: "박바우처"
    conditions:
      keywords: ["바우처", "중소기업", "창업"]
      ministry: ["중소벤처기업부"]
  ...
```

### 11-2. BD 마일스톤 자동 배정 (assign_milestone.py)

| 코드 | 의미 | 배정 조건 |
|------|------|----------|
| `M01` | 공고 발굴·등록 | L3강공고=Y (기본) |
| `M05` | 즉시 컨셉 제안 | L3강공고=Y + D-day ≤ 14 (A/B등급) 또는 D-day ≤ 7 (전등급) |
| `P01` | 파트너 후보 발굴 | 파트너후보=Y (A/B/C등급) |
| `M01\|P01` | BD + 파트너 동시 | 두 조건 모두 해당 |

---

## 12. 설정 파일 (configs/)

모든 비즈니스 파라미터는 YAML 파일로 관리. **코드에 하드코딩 금지.**

### scoring.yaml

```yaml
thresholds:
  l3_strong:         30   # fitness ≥ 30 → L3 강공고
  partner_candidate: 18   # priority ≥ 18 → 파트너 후보
  grade_a:           48   # priority ≥ 48 → A등급
  grade_b:           30   # priority ≥ 30 → B등급
  grade_c:           18   # priority ≥ 18 → C등급
  neg_multiplier:          6.0  # 감점 기본 배율 (하위 호환)
  neg_multiplier_strong:   6.0  # 바이오/의료/건설 — 완전 범위 외
  neg_multiplier_medium:   4.0  # 교육/인력 — 일부 관련 가능
  neg_multiplier_weak:     2.0  # 식품/농업 — 간접 관련 가능
  pos_multiplier:     5.0 # 가점 배율
  struct_bonus_factor:1.5 # 구조화 섹션 보너스 배율
  budget_bonus:       3.0 # 예산 존재 시 보너스

solutions:
  scale_factor: 15.0
  names: [ManufacturingDT, RecipeAI, QualityAI, InspectionAI, SafetyAI, GenAI, InfraDS, PdM]

priority_formula:
  w_fitness:  0.6
  w_industry: 0.4

l3_keywords:         # L3 강공고 키워드 목록
  min_hits: 1
  keywords: [스마트공장, 제조ai, 디지털트윈, ...]

positive_keywords:   # 가점 키워드 딕셔너리
  스마트공장: 5
  제조ai: 5
  ...

negative_keywords:   # 감점 키워드 딕셔너리
  수요기업: 12
  일자리: 7
  ...

solution_keywords:   # 솔루션별 키워드 맵
  ManufacturingDT:
    디지털트윈: 4
    스마트공장: 3
    ...
```

### sites.yaml

```yaml
sites:
  - code: bizinfo
    name: 기업마당
    enabled: true
    collector_type: playwright   # requests or playwright
  - code: kiat
    enabled: true
    collector_type: playwright
  - code: smba
    enabled: false   # 서버 차단
  ...
```

### recurring.yaml

```yaml
patterns:
  - name: 스마트공장구축
    priority: 1              # 1=핵심, 2=중간, 3=참고
    aliases:
      - 스마트공장 구축
      - 스마트팩토리 구축
      - 스마트공장 보급
      - 스마트공장 보급확산
      - 스마트공장 고도화
      - 자율형스마트공장
      - AI스마트공장
      - 스마트공장구축사업
      ...  # 그룹당 6~13개 aliases

  - name: 상생형스마트공장    # 신규 추가
    priority: 1
    aliases:
      - 상생형 스마트공장
      - 상생형 선도모델
      - 대중소 상생형
  ...
# 총 18그룹, 120+ aliases, priority 순 정렬 매칭
```

### manager_rules.yaml → [섹션 11-1 참조]

### sheets.yaml → [섹션 13 참조]

### settings.yaml

```yaml
pipeline:
  max_pages_default: 5       # 사이트별 기본 최대 페이지 수
  request_timeout: 15        # HTTP 타임아웃 (초)
  enrich_workers: 3          # 상세 페이지 병렬 워커 수
  collect_workers: 6         # 사이트 병렬 수집 워커 수
  tfidf_sim_threshold: 0.85  # TF-IDF 중복 판단 유사도 임계값
```

---

## 13. Google Sheets 10시트 구조

파이프라인 실행 후 자동 업로드. Sheets를 백엔드 DB로 사용해 별도 DB 없이 플랫폼 연결 가능.

| 시트명 | 용도 | 주요 컬럼 |
|--------|------|----------|
| `01_영업기회_정보` | 전체 수집 공고 마스터 | 공고명·마감일·D-day·등급·win_probability·추천솔루션·담당자·정기공고여부 |
| `02_L3강공고` | L3강공고=Y 필터 | 01과 동일 구조 |
| `03_파트너전달` | 파트너 후보 공고 | 01과 동일 구조 |
| `05_긴급마감_공고` | D-7 이내 마감 | 공고명·마감일·D-day·기관·등급 |
| `20_BD리포트` | 보고용 요약 | 실행일·총수집·등급별 건수·사이트별 현황 |
| `22_KPI` | 실행별 성능 KPI | 실행ID·소요시간·수집수·A등급수·L3수 |
| `93_통계` | 부처·솔루션·키워드 집계 | (시장 분석 참고용) |
| `94_실행로그` | 파이프라인 실행 이력 | 실행ID·시작/종료시각·상태 |
| `96_에러로그` | 수집 오류 사이트 | 사이트코드·오류메시지·발생시각 |
| `97_상태변경로그` | 공고 상태 변경 이력 | 변경일시·공고ID·변경필드·이전값·변경값·변경사유·처리자 |

---

## 14. 새 컬렉터 추가 방법

1. `infrastructure/collectors/sites/` 에 `{site}_collector.py` 생성

```python
from interx_engine.infrastructure.collectors.sites.base_collector import BaseCollector
from interx_engine.core.entities.notice import Notice

class NewSiteCollector(BaseCollector):
    site_key  = "newsite"
    site_name = "새 기관명"
    list_url  = "https://newsite.go.kr/notices?page={page}"

    def _parse_page(self, page: int) -> List[Notice]:
        html = self._get(self.list_url.format(page=page))
        soup = BeautifulSoup(html, "lxml")
        notices = []
        for tr in soup.select("table.board-list tr[data-id]"):
            title = tr.select_one("td.title a").text.strip()
            href  = tr.select_one("td.title a")["href"]
            url   = urljoin("https://newsite.go.kr", href)
            notices.append(Notice(
                notice_id    = _notice_id("newsite", url),
                title        = title,
                site         = "newsite",
                detail_url   = url,
                execution_id = self.execution_id,
            ))
        return notices
```

2. `configs/sites.yaml` 에 추가

```yaml
- code: newsite
  name: 새 기관명
  enabled: true
  collector_type: requests   # or playwright
```

3. `collector_factory.py` 에 매핑 추가

```python
from .sites.new_collector import NewSiteCollector
_REGISTRY["newsite"] = NewSiteCollector
```

4. 테스트 실행

```bash
venv/Scripts/python run_engine.py --sites newsite --no-sheets --dry-run
```

---

## 15. 테스트

```bash
# 단위 테스트 (엔티티·매퍼·스코어링 정책)
venv/Scripts/python -m pytest tests/unit/ -v --tb=short

# 통합 테스트 (파이프라인 dry-run, settings 검증)
venv/Scripts/python -m pytest tests/ -v

# 커버리지 측정
venv/Scripts/python -m pytest tests/ --cov=src/interx_engine --cov-report=html
```

**단위 테스트 주요 항목**

| 테스트 파일 | 검증 내용 |
|------------|----------|
| `test_scoring_policy.py` | 가점/감점/등급 계산 정확도 |
| `test_l3_policy.py` | L3 키워드 매칭 |
| `test_notice_mapper.py` | Notice → Sheets 행 변환 |
| `test_budget_parser.py` | 예산 문자열 → 숫자 정규화 |
| `test_recurring.py` | 정기공고 패턴 매칭 |

---

## 16. 핵심 원칙

- **도메인 로직은 `core/`에만** — infrastructure에 비즈니스 로직 절대 금지
- **설정값은 `configs/` YAML에** — 코드에 숫자/키워드 하드코딩 금지
- **각 크롤러는 `BaseCollector` 상속** — `_parse_page()` 메서드만 구현
- **`service_account.json`** — Git에 올리면 안 됨 (Google 인증키, .gitignore에 포함)
- **Playwright 필요 사이트**: `bizinfo`, `kiat`, `ketep`, `smart_factory`, `iitp`
  → 초기 실행 전 `playwright install chromium` 필수
- **의존 방향**: infrastructure → application → core (역방향 절대 금지)
- **중복 방지**: notice_id = site_code + URL MD5 / 스마트공장은 nttId 기반 키 (`smart_factory-ntt{nttId}`)
- **접수상태 자동 분류**: 상세 페이지 본문에서 접수기간 파싱 → 접수중/접수예정/마감 자동 판별

---

## 자동 생성 대시보드 차트 (9패널)

파이프라인 실행마다 `data/analysis/dashboard_{execution_id}.png` 자동 저장.

```
┌──────────────┬──────────────┬──────────────┐
│ ① 등급 분포   │ ② PCA 산점도  │ ③ 적합도 히스 │
├──────────────┼──────────────┼──────────────┤
│ ④ 사이트 현황 │ ⑤ 솔루션 수요 │ ⑥ 키워드 빈도 │
├──────────────┼──────────────┼──────────────┤
│ ⑦ 클러스터   │ ⑧ D-day 분포 │ ⑨ 이상치 탐지 │
└──────────────┴──────────────┴──────────────┘
```

| 차트 | 의미 | BD 활용 |
|------|------|---------|
| ① 등급 분포 (도넛) | A/B/C/D 비율 | 파이프라인 등급 필터 기준 |
| ② PCA 2D 산점도 | 6개 피처 2차원 압축, 색깔=클러스터, 빨간테두리=이상치 | 유사 공고 그룹 탭 설계 |
| ③ 적합도 히스토그램 | C/B/A 컷라인 수직선 표시 | 적합도 슬라이더 필터 구간 |
| ④ 사이트별 수집 현황 | 전체(파랑)·A/B등급(노랑)·L3(빨강) 막대 | 채널 효율 KPI |
| ⑤ 솔루션 수요 분포 | 8개 솔루션별 공고 수 | 제품별 파이프라인 규모 |
| ⑥ 키워드 빈도 Top-12 | 공고 본문 키워드 빈도 | 시장 키워드 트렌딩 |
| ⑦ 클러스터별 적합도 | KMeans 그룹별 평균 적합도 | 집중 공략 세그먼트 |
| ⑧ D-day 긴급도 분포 | 마감 구간별 공고 수 | 긴급 알림 배지 기준 |
| ⑨ Isolation Forest 이상치 | 비정형 공고 상위 5% 탐지 | ⚠️ 검토 요망 자동 플래그 |

---

## 17. BD Intelligence 웹 플랫폼

엔진 파이프라인 결과를 실시간으로 확인·관리하는 웹 대시보드.
**FastAPI + Jinja2 + Tailwind CSS + Chart.js** 기반, 다크 네이비 테마.

### 17-1. 실행 방법

```bash
# 플랫폼 서버 시작
cd platform && python start_server.py    # http://localhost:8001

# 엔진 DB → 플랫폼 수동 싱크
python platform/colab_sync.py --url http://localhost:8001
```

### 17-2. 플랫폼 구조

```
platform/
├── app.py               # FastAPI 앱 (4 페이지 + 6 API 엔드포인트)
├── database.py           # SQLite ORM (notices, pipeline_results, status_changes, user_memos)
├── colab_sync.py         # Colab → 플랫폼 자동 싱크 모듈
├── start_server.py       # 서버 실행 스크립트
├── static/css/style.css  # 커스텀 스타일 (대부분 Tailwind)
└── templates/
    ├── base.html          # 레이아웃 (사이드바 + 다크 테마)
    ├── dashboard.html     # 대시보드 (KPI 6개 + 차트 3개 + TOP5)
    ├── notices.html       # 공고 목록 (필터·정렬·페이지네이션)
    ├── notice_detail.html # 공고 상세 (스코어링 분석 + BD 상태 편집)
    └── pipeline.html      # 파이프라인 실행 이력
```

### 17-3. 페이지 & API 엔드포인트

| 타입 | 경로 | 설명 |
|------|------|------|
| 페이지 | `/` | 대시보드 — KPI 카드 6개, 등급 도넛/사이트 바/솔루션 레이더 차트, 우선순위 TOP5 |
| 페이지 | `/notices` | 공고 목록 — 등급·사이트·L3·긴급 필터, 검색, 정렬, 페이지네이션 |
| 페이지 | `/notice/{id}` | 공고 상세 — 스코어링 분석(fitness/priority/win%), 본문, BD 상태 편집 |
| 페이지 | `/pipeline` | 파이프라인 — 실행 이력 테이블, Colab 연동 코드 안내 |
| API | `GET /api/stats` | 대시보드 KPI 데이터 (JSON) |
| API | `GET /api/notices` | 공고 목록 (필터·페이지네이션 파라미터) |
| API | `GET /api/notice/{id}` | 공고 상세 (JSON) |
| API | `POST /api/notice/{id}/update` | BD 상태 변경 (status/manager/milestone/memo) |
| API | `POST /api/pipeline/sync` | Colab 파이프라인 결과 수신 |
| API | `GET /api/health` | 헬스 체크 |

### 17-4. Colab 자동 싱크 연동

파이프라인 실행 후 결과를 플랫폼에 자동 전송. Colab 노트북 끝에 아래 코드 추가:

```python
from platform.colab_sync import sync_pipeline_result

# 파이프라인 실행 후:
sync_pipeline_result(
    result=final_result,          # 파이프라인 결과 딕셔너리
    notices=scored_notices,       # Notice 객체 리스트
    score_cards=score_card_dict,  # {notice_id: ScoreCard} 딕셔너리
    platform_url="http://YOUR_SERVER:8001",
)
```

또는 엔진 SQLite DB에서 직접 싱크:

```bash
python platform/colab_sync.py --url http://YOUR_SERVER:8001
```

### 17-5. UI 테마

- **배경**: navy `#0A1628`
- **강조**: cyan `#00CFFF`, gold `#FFD700`
- **카드**: glass-morphism (반투명 블러 + 글로우 테두리)
- **등급 배지**: A=초록, B=시안, C=골드, D=빨강, L3=핑크

---

## 18. 경쟁사 분석 리포트

`competitor_report.py` — 경쟁사 공고 참여 현황을 자동 분석하여 4패널 차트 PNG + CSV 생성.

### 18-1. 분석 대상

| 구분 | 기업 수 | 주요 기업 |
|------|---------|----------|
| **Tier1 (직접 경쟁)** | 6개 | 삼성SDS, LG CNS, SK C&C, 포스코DX, 현대오토에버, 롯데정보통신 |
| **Tier2 (간접 경쟁)** | 10개 | 한국IBM, 오라클, SAP, 다쏘시스템, 지멘스, 씨메스, 수아랩 등 |
| **Partners** | 7개 | 성균관대, KAIST, 한국생산기술연구원, ETRI 등 |

### 18-2. 생성 출력물

```
data/analysis/
├── competitor_chart_{execution_id}.png   # 4패널 차트
└── competitor_report_{execution_id}.csv  # 상세 데이터
```

### 18-3. 4패널 차트 구성

```
┌────────────────────┬────────────────────┐
│ ① TOP10 경쟁사     │ ② Tier 분포 도넛   │
│   (가로 막대)       │   (Tier1/Tier2/파트너) │
├────────────────────┼────────────────────┤
│ ③ 경쟁사×등급 분포  │ ④ 월별 활동 트렌드  │
│   (스택 바)         │   (라인 차트)       │
└────────────────────┴────────────────────┘
```

| 차트 | 설명 | BD 활용 |
|------|------|---------|
| ① TOP10 경쟁사 | 공고 출현 빈도 상위 10개 | 주요 경쟁사 식별 |
| ② Tier 분포 | 직접/간접/파트너 비율 | 경쟁 강도 파악 |
| ③ 경쟁사×등급 | 경쟁사별 A/B/C/D 분포 | 고등급 공고 경쟁 현황 |
| ④ 월별 트렌드 | 최근 6개월 경쟁사 활동량 | 시장 경쟁 추이 |

### 18-4. 사용 방법

```python
from interx_engine.application.use_cases.competitor_report import generate_competitor_report

result = generate_competitor_report(notices, score_cards, execution_id="EXEC-001")
# result["summary"]           → 통계 요약
# result["chart_path"]        → PNG 경로
# result["csv_path"]          → CSV 경로
# result["competitor_notices"] → 경쟁사 관련 공고 목록
```

---

## 19. 제안서 자동 생성 v2

`generate_proposal_v2.py` — A/B 등급 공고에 대해 **솔루션 맞춤형** Word 제안서 초안 자동 생성.

### 19-1. v1 대비 개선점

| 항목 | v1 | v2 |
|------|----|----|
| 솔루션 상세 | 이름만 표시 | **8개 솔루션별 역량 프로필 자동 반영** |
| 점수 분석 | 등급만 | **솔루션 점수 테이블** (솔루션명/점수/적합도) |
| 경쟁 분석 | 없음 | **경쟁사 감지 시 경쟁 환경 섹션 추가** |
| 공고 플래그 | 없음 | **L3 강공고 / 정기공고 / D-day 표시** |
| 공고 본문 | 없음 | **요약 또는 본문 2000자 자동 포함** |

### 19-2. 8개 솔루션 역량 프로필

제안서에 자동 삽입되는 InterX 솔루션별 상세 내용:

| 솔루션 | 설명 | 기술 스택 |
|--------|------|----------|
| **ManufacturingDT** | 실시간 공정 시뮬레이션 디지털트윈 | Unity 3D / OPC-UA / Azure IoT |
| **RecipeAI** | 공정 조건 최적화 AI | XGBoost / LSTM / Bayesian Opt |
| **QualityAI** | 불량 검출 및 품질 예측 | CNN / YOLO / Anomaly Detection |
| **InspectionAI** | 머신비전 자동 외관 검사 | YOLO v8 / Detectron2 / OpenCV |
| **SafetyAI** | 중대재해 예방 안전 AI | Pose Estimation / IoT Gateway |
| **GenAI** | 제조 생성형 AI | GPT-4 / Claude / LangChain / RAG |
| **InfraDS** | 데이터 스페이스 인프라 | Catena-X / K8s / Kafka / MinIO |
| **PdM** | 설비 고장 예측 예지보전 | LSTM / Transformer / Edge Computing |

### 19-3. 생성 문서 구조

```
[제안서 초안] {공고명}
├── 핵심 지표 카드 (등급/적합도/우선순위/D-day)
├── 1. 사업 개요 (공고 기본 정보)
├── 2. InterX 적합도 분석 (점수 + 솔루션 테이블)
├── 3. 추천 솔루션 및 역량 (상위 3개 솔루션 상세)
├── 4. 제안 전략 ([작성 필요] 차별화 포인트)
├── 5. 경쟁 환경 분석 (경쟁사 감지 시)
├── 6. 추진 일정 (D-day 기반 타임라인)
├── 7. 공고 원문 링크
└── 8. 공고 본문 요약
```

### 19-4. 사용 방법

```python
from interx_engine.application.use_cases.generate_proposal_v2 import generate_proposals_v2

paths = generate_proposals_v2(notices, score_cards, output_dir="output/proposals")
# ["output/proposals/A_bizinfo_스마트공장AI구축.docx", ...]
```

---

## 20. ML 수주예측 학습 파이프라인

기존 rule_v1 가중합 → **sklearn LogisticRegression ML 모델**로 자동 전환.

### 20-1. 학습 데이터 소스 (우선순위)

| 순위 | 소스 | 라벨 기준 | 설명 |
|------|------|----------|------|
| 1 | `data/crm_memos.json` | "수주"=1, "탈락"=0 | 영업팀 실적 입력 (최우선) |
| 2 | `data/exports/training/*.jsonl` | grade A/B=1, C/D=0 | 파이프라인 자동 Export |
| 3 | `data/interx_engine.db` | grade A/B=1, C/D=0 | SQLite 누적 데이터 |

### 20-2. 학습 흐름

```
데이터 로드 (최소 20건 필요)
  ↓
피처 추출 (fitness, priority, budget, dday, l3, industry)
  ↓
StandardScaler 정규화
  ↓
LogisticRegression 학습
  ↓
5-fold Cross Validation (n≥30 시 train/test 70/30 split)
  ↓
data/models/win_pred_lr.pkl 저장
  ↓
다음 파이프라인 실행 → pkl 감지 → ML 모드 자동 전환
```

### 20-3. 실행 방법

```bash
# 학습 실행
venv/Scripts/python scripts/train_win_model.py

# CRM 데이터 형식 (data/crm_memos.json)
[
  {"notice_id": "bizinfo-a1b2c3d4", "result": "수주"},
  {"notice_id": "kiat-e5f6g7h8",   "result": "탈락"}
]
```

### 20-4. 모드 자동 전환

```
파이프라인 실행 시:
  data/models/win_pred_lr.pkl 존재?
    ├── YES → ML 모드 (LogisticRegression 예측)
    └── NO  → Rule 모드 (기존 6가지 가중합)
```

> 영업팀이 수주/탈락 결과를 20건 이상 입력하면 ML 모드가 활성화되어 예측 정확도가 향상됩니다.

---

## 21. Streamlit 팀 배포 앱

팀원에게 **링크 하나**로 공유하는 원클릭 파이프라인 실행 웹앱.
Streamlit Cloud 무료 호스팅, 별도 서버 비용 없음.

### 21-1. 접속 URL

```
https://interx-gov-intel.streamlit.app
```

### 21-2. 11개 탭 구성

| 탭 | 기능 | 주요 내용 |
|----|------|----------|
| **대시보드** | 종합 현황 | KPI 6개 + 등급 도넛 차트 + A등급 TOP10 + 사이트별 바 차트 |
| **수집 실행** | 파이프라인 실행 | 버튼 하나로 16개 사이트 수집 → 실시간 프로그레스 |
| **공고 목록** | 전체 공고 조회 | 등급/사이트/키워드 필터 + 공고 상세 보기 + CSV/Excel 다운로드 |
| **제안서** | 자동 제안서 | A/B 등급 공고 .docx 다운로드 |
| **경쟁사 분석** | 경쟁사 추적 | TOP10 바 차트 + 경쟁사 관련 공고 테이블 |
| **수주 예측** | 수주 확률 | 공고별 수주 확률 분포 히스토그램 + 유망 TOP10 |
| **마감 캘린더** | 마감 관리 | D-3/D-7/D-30 KPI + 타임라인 차트 + 긴급 리스트 |
| **솔루션 매칭** | 솔루션 분석 | 8개 솔루션 레이더 차트 + 점수/공고수 비교 |
| **키워드 트렌드** | 시장 동향 | 매칭 키워드 TOP20 + 제목 빈출 단어 TOP20 |
| **담당자 현황** | 업무 배분 | 담당자별 등급 분포 스택 차트 + 상세 테이블 |
| **수집 히스토리** | 실행 이력 추적 | 수집 트렌드 차트 + 등급 비교 + 사이트별 변화 + 히스토리 Excel 다운로드 |

### 21-3. UI 디자인 — interxlab.com 공식 팔레트

```
InterX Enterprise Dashboard v5 — 공식 사이트 동일 디자인 시스템
├── --accent-color: #FF8000 (공식 오렌지)
├── --accent2-color: #3A7BEE (공식 블루)
├── --primary-color: #000 (블랙)
├── 네비게이션: 블랙 풀너비 바 (공식 사이트 헤더 동일)
├── 인트로: 블랙 배경 + INTER(화이트) + X(오렌지) 2.6초 애니메이션
├── Metric Card: 오렌지 글로우 호버 (2px 2px 20px rgba(255,128,0,.15))
├── Notice Row: 배지 + 제목 + 메타 + Status Pill 컴포넌트
├── 버튼: 블랙 기본 → 호버 시 오렌지 전환
├── Status Pill: 시맨틱 색상 (A=초록, L3=핑크, 긴급=빨강)
└── Empty State: 아이콘 + 제목 + 설명 + 액션 가이드
```

### 21-4. 기술 스택

```
Streamlit 1.57 + Plotly + Pandas
├── streamlit_app.py          # Enterprise Dashboard (11탭, ~560줄)
├── .streamlit/config.toml     # 테마 설정 (primaryColor: #FF8000)
└── Streamlit Cloud            # 무료 호스팅 (GitHub 연동 자동 배포)
```

### 21-4. 배포 방법

1. [share.streamlit.io](https://share.streamlit.io) → GitHub 로그인
2. Repository: `KimDoojin2/interx-gov-intelligence`, Branch: `master`, Main file: `streamlit_app.py`
3. Deploy 클릭 → 2~3분 후 고정 URL 생성

### 21-5. 비용

| 항목 | 비용 |
|------|------|
| Streamlit Cloud 호스팅 | **무료** (Community Plan) |
| 수집 실행 (크롤링) | **무료** (requests + BeautifulSoup) |
| 스코어링/분석 | **무료** (Python + scikit-learn) |
| 차트/시각화 | **무료** (Plotly) |
| Google Sheets 연동 | **무료** (API 일일 한도 내) |

> 외부 유료 API(GPT, Claude 등) 미사용. 전 기능 0원 운영.
