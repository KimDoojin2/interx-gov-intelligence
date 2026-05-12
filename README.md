# InterX Government Intelligence Engine

정부지원사업 공고를 수집, 정규화, 점수화하고,
InterX BD CRM 최신 시트 구조에 맞춰 업로드하는 엔진.

## 핵심 원칙
- 클린 아키텍처 기반
- 시트명/컬럼명/점수 규칙 config 분리
- 거대한 단일 notebook/py 파일 금지
- 도메인 규칙과 외부 입출력 분리

## 실행 흐름
1. config 로드
2. 사이트별 공고 수집
3. 정규화
4. 점수 계산
5. 시트 row 매핑
6. 구글시트 업로드
7. 로그 기록
