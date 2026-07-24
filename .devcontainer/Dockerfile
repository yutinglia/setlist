FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# psycopg2 (non-binary) needs libpq headers at build/install time
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Keep pip current for reproducible installs of pinned requirements
RUN pip install --no-cache-dir -U pip setuptools wheel
