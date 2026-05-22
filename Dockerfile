# =============================================================================
# InterX Government Intelligence Engine — Docker
# Multi-stage build for minimal production image
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps (for lxml, scikit-learn)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Dependencies ─────────────────────────────────────────────────────────────
FROM base AS deps

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM deps AS runtime

COPY src/ ./src/
COPY configs/ ./configs/
COPY run_engine.py ./
COPY .streamlit/ ./.streamlit/
COPY streamlit_app.py ./

# Non-root user
RUN useradd -m -r interx && \
    mkdir -p /app/data /app/logs /app/output && \
    chown -R interx:interx /app
USER interx

# ── Entrypoints ──────────────────────────────────────────────────────────────
# Pipeline (default)
CMD ["python", "run_engine.py"]

# Dashboard: docker run -p 8501:8501 interx-engine streamlit run streamlit_app.py
# API:       docker run -p 8000:8000 interx-engine python -m interx_engine.api
EXPOSE 8501 8000
