# =============================================================================
# InterX Government Intelligence Engine — Makefile
# 개발자 편의 명령어 모음
# =============================================================================
.PHONY: help install dev test lint run dashboard api docker-build docker-up clean

PYTHON ?= python
VENV   ?= venv

help:  ## 도움말
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## 의존성 설치 (프로덕션)
	$(PYTHON) -m pip install -r requirements.txt

dev:  ## 개발 환경 설치 (lint + test 포함)
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install pytest pytest-cov ruff
	$(PYTHON) -m pip install -e .

test:  ## 단위 테스트 실행
	$(PYTHON) -m pytest tests/unit/ -v --tb=short

test-all:  ## 전체 테스트 (unit + integration)
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:  ## 코드 린트 (ruff)
	$(PYTHON) -m ruff check src/ tests/

format:  ## 코드 포맷팅 (ruff)
	$(PYTHON) -m ruff format src/ tests/

run:  ## 파이프라인 실행 (daily)
	$(PYTHON) run_engine.py

run-dry:  ## Mock 데이터 테스트 실행
	$(PYTHON) run_engine.py --dry-run

run-full:  ## Full 파이프라인 (클러스터링·알림 포함)
	$(PYTHON) run_engine.py --full

dashboard:  ## Streamlit 대시보드 실행
	$(PYTHON) -m streamlit run streamlit_app.py

api:  ## FastAPI REST API 실행
	$(PYTHON) -m interx_engine.api

docker-build:  ## Docker 이미지 빌드
	docker build -t interx-engine .

docker-up:  ## Docker Compose 전체 기동
	docker compose --profile all up -d

clean:  ## 캐시/임시 파일 정리
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .ruff_cache
