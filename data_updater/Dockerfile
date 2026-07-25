# Production-oriented image for the data_updater FastAPI service.
# Build from repo root:
#   docker compose up --build data_updater
# Or:
#   docker build -t vks-data-updater ./data_updater

FROM python:3.12-slim-bookworm AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

ENV APP_ENV=prod
EXPOSE 8000

FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
ENV APP_ENV=test
CMD ["python", "-m", "pytest"]

FROM base AS runtime
RUN useradd --create-home --uid 10001 appuser
COPY main.py config.py deps.py ./
COPY db ./db
COPY models ./models
COPY repositories ./repositories
COPY routers ./routers
COPY services ./services
COPY utils ./utils
USER appuser

# cwd = /app (data_updater/); imports assume this layout
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
