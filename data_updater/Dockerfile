# Production-oriented image for the data_updater FastAPI service.
# Build from repo root:
#   docker compose up --build data_updater
# Or:
#   docker build -t vks-data-updater ./data_updater

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ENV APP_ENV=prod
EXPOSE 8000

# cwd = /app (data_updater/); imports assume this layout
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
