# Production-oriented image for the data_updater FastAPI service.
# Build from repo root:
#   docker compose up --build data_updater
# Or:
#   docker build -f data_updater/Dockerfile -t vks-data-updater .

FROM python:3.12-slim-bookworm AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY data_updater/requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

ENV APP_ENV=prod
EXPOSE 8000

FROM base AS test
COPY data_updater/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY data_updater/. .
ENV APP_ENV=test
CMD ["python", "-m", "pytest"]

FROM base AS runtime
LABEL org.opencontainers.image.source="https://github.com/yutinglia/vtuber-karaoke-search" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 10001 appuser
COPY LICENSE /usr/share/licenses/vtuber-karaoke-search/LICENSE
COPY data_updater/main.py data_updater/config.py data_updater/deps.py ./
COPY data_updater/db ./db
COPY data_updater/models ./models
COPY data_updater/repositories ./repositories
COPY data_updater/routers ./routers
COPY data_updater/services ./services
COPY data_updater/utils ./utils
USER appuser

# cwd = /app (data_updater/); imports assume this layout
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
