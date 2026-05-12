# Migration Notes

## 목적
기존 엔진 자산을 삭제하지 않고 archive로 이동한 뒤,
필요한 기능만 새 Clean Architecture 구조로 재이식한다.

## 우선 이식 대상
1. 사이트별 collector
2. 첨부파일 다운로드 로직
3. PDF/HWP/HWPX 파서
4. 점수 계산 로직
5. 로그 기록 로직

## 보류 대상
- giant notebook 통합 실행본
- 중복 백업본
- 임시 export 파일

## 원칙
- 기존 코드는 archive에서 참고만 한다.
- 새 기능 구현은 반드시 src/interx_engine 아래에 한다.
- notebook은 실행/검증 용도로만 사용한다.
