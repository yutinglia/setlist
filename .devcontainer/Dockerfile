FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:0fdcf958b64fd9ffe19972b4afb1337d1c57596442fb2424130bae8e093b9fcc

RUN pip install --no-cache-dir \
        pip==26.1.2 \
        setuptools==83.0.0 \
        wheel==0.47.0

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
