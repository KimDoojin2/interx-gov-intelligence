# InterX Government Intelligence Engine v3.0
## 아키텍처 요약 / 진단 / 확장 가이드

---

## 1. 전체 아키텍처

```
main()
  └─ DailyPipelineOrchestrator.run(execution_id)
       ├─ [병렬] BaseCollector.collect() × N사이트   → List[Notice]
       │    ├─ fetch_html_smart()  (requests → Playwright fallback)
       │    ├─ parse_list_page()
       │    ├─ parse_detail_page()
       │    │    ├─ extract_dates()
       │    │    ├─ extract_budget()
       │    │    ├─ parse_attachments()
       │    │    └─ extract_structured_sections()
       │    └─ ErrorRecord 수집
       ├─ SQLiteGateway.existing_keys()              → 중복 제거
       ├─ ScoreEngine.score_all()                    → List[ScoreCard]
       │    ├─ positive/negative keyword 매칭
       │    ├─ solution별 점수 계산
       │    └─ l3_strong / partner_candidate 판정
       ├─ [병렬] AttachmentDownloader.process_all()  → 다운로드 결과
       │    └─ classify_download_error()             → 실패 사유 분류
       ├─ parse_attachments_in_notices()             → PDF/HWPX/DOCX 파싱
       ├─ Row 조립 (notice_to_master_row 등)
       ├─ GoogleSheetGateway.append_rows_batch()     → 배치 업로드
       └─ SQLiteGateway.upsert_notices/attachments() → 로컬 저장
```

---

## 2. 기존 코드 문제점 진단 및 개선 내역

| 문제 | 기존 | v3.0 개선 |
|------|------|-----------|
| 하드코딩 | 경로/시트명 곳곳에 산재 | 환경변수 + 상수 TOP에 집중 |
| Sheets 성능 | 행 단위 append 반복 | BATCH_SIZE=500 일괄 append_rows |
| 중복 수집 | 없음 | SQLite notice_key(md5) 기반 dedup |
| 에러 처리 | 단계별 try/catch 부재 | 모든 단계 ErrorRecord 수집 + 에러 로그 시트 |
| 다운로드 실패 분류 | 3종류 | 12종류 세분류 (ssl/403/404/timeout 등) |
| 병렬 처리 | 순차 | ThreadPoolExecutor (수집/다운로드) |
| Playwright 충돌 | asyncio 직접 사용 | sync_playwright + nest_asyncio |
| 상태 관리 | 없음 | NEW/UPDATED/DEADLINE_SOON/CLOSED |
| 구조화 파싱 | 없음 | 10개 섹션 자동 추출 |
| 사이트 확장성 | BizinfoCollector 고정 | COLLECTOR_REGISTRY 딕셔너리 |
| 점수 단순 | 키워드 카운트만 | 솔루션별 점수 + 산업점수 + 가중합 |
| D-day | 없음 | calc_dday() → D-day + 상태 동시 계산 |
| 하이퍼링크 | 없음 | HYPERLINK 수식으로 공고명 컬럼 생성 |

---

## 3. 새 사이트 수집기 추가 방법

```python
class MyNewSiteCollector(BaseCollector):
    site_key  = "mysite"
    base_url  = "https://www.mysite.go.kr"
    ssl_verify = True   # SSL 문제 사이트는 False

    def get_list_url(self, page: int) -> str:
        return f"{self.base_url}/list.do?page={page}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        for a in soup.select(".bbs-list a.title"):
            href = urljoin(self.base_url, a["href"])
            items.append({"title": safe_text(a.get_text()), "detail_url": href})
        return items

    def parse_detail_page(self, html: str, detail_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        body = safe_text(soup.get_text(" "))
        dates = extract_dates(body)
        return {
            "title":         parse_title(soup),
            "body_text":     body,
            "posted_date":   dates.get("posted_date", ""),
            "deadline_date": dates.get("deadline_date", ""),
            "budget":        extract_budget(body),
            "ministry":      extract_ministry(body),
            "agency":        "내 기관명",
            "business_type": "",
            "summary":       body[:300],
            "attachments":   parse_attachments(soup, detail_url),
        }

# 레지스트리에 등록
COLLECTOR_REGISTRY["mysite"] = MyNewSiteCollector
```

---

## 4. 환경변수 전체 목록

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| INTERX_SHEET_NAME | InterX_BD_CRM_v10_fresh_template | Google Sheets 이름 |
| INTERX_SA_JSON | ./service_account.json | 서비스 계정 JSON 경로 |
| INTERX_DB_PATH | ./data/interx_engine.db | SQLite DB 경로 |
| INTERX_ATT_DIR | ./data/attachments | 첨부파일 저장 디렉토리 |
| INTERX_LOG_DIR | ./logs | 로그 파일 디렉토리 |
| INTERX_WORKERS | 4 | 병렬 스레드 수 |
| INTERX_MAX_PAGES | 3 | 사이트당 최대 수집 페이지 |
| INTERX_TIMEOUT | 45 | HTTP 요청 타임아웃(초) |
| PLAYWRIGHT_SITES | (빈값) | 강제 Playwright 사이트 키 (comma-separated) |

---

## 5. 주의할 병목 포인트

1. **Google Sheets API 한도**: 100req/100sec 제한 → BATCH_SIZE=500, sleep(0.5) 조정
2. **Playwright 메모리**: headless chromium 프로세스가 Colab RAM 초과할 수 있음 → 꼭 필요한 사이트만 PLAYWRIGHT_SITES에 등록
3. **ThreadPoolExecutor + Playwright**: Playwright는 스레드 안전하지 않음 → Playwright 사이트는 단일 스레드로 처리하거나 별도 프로세스 사용 권장
4. **HWP 파싱**: python-hwp 라이브러리가 Colab에서 불안정 → hwpx(압축 xml)만 지원, hwp는 "skipped" 처리
5. **대용량 첨부파일**: 다운로드 타임아웃 30초 → 큰 파일은 AttachmentDownloader(timeout=120) 조정

---

## 6. 추후 확장 포인트

- [ ] `SmbaCollector` (중소벤처기업부 공식 사이트)
- [ ] `InnopolisCollector` (연구개발특구진흥재단)
- [ ] `KiatCollector` (한국산업기술진흥원)
- [ ] `NtisCollector` (국가과학기술정보서비스)
- [ ] LLM 기반 사업요약 자동 생성 (Claude API 연동)
- [ ] 첨부파일 텍스트 기반 재점수화 (구조화 파싱 → 재스코어링)
- [ ] Slack/이메일 알림 (L3 강공고 발생 시)
- [ ] Streamlit 대시보드 연동
- [ ] 스케줄러 (APScheduler / GitHub Actions cron)
