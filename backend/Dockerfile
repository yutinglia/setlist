# Production-oriented image for the backend FastAPI service.
# Build from repo root:
#   docker compose up --build backend
# Or:
#   docker build -f backend/Dockerfile -t vks-backend .

FROM python:3.14-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install --no-cache-dir \
        pip==26.1.2 \
        setuptools==83.0.0 \
        wheel==0.47.0 \
    && pip install --no-cache-dir -r requirements.txt

ENV APP_ENV=prod
EXPOSE 8000

FROM base AS test
COPY backend/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/. .
ENV APP_ENV=test
CMD ["python", "-m", "pytest"]

FROM base AS runtime
ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 10001 appuser
COPY LICENSE /usr/share/licenses/vtuber-karaoke-search/LICENSE
COPY backend/main.py backend/config.py backend/container.py backend/deps.py \
     backend/run_updater_once.py backend/reanalyze_stored_data.py ./
COPY backend/db ./db
COPY backend/models ./models
COPY backend/repositories ./repositories
COPY backend/routers ./routers
COPY backend/services ./services
COPY backend/utils ./utils
USER appuser

# cwd = /app (backend/); imports assume this layout
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
