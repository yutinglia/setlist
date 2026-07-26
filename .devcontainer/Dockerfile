FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm

RUN pip install --no-cache-dir -U pip setuptools wheel

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
