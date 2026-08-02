FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:29f5e05ad69bdec17b27b353b034000a7b9fecf7bd29b759e16954ab059ee46d

RUN pip install --no-cache-dir \
        pip==26.1.2 \
        setuptools==83.0.0 \
        wheel==0.47.0

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
