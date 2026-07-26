FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm@sha256:6ef67a2f0d2f054ad60990679e15208367ff10110a0c0be7f18dbaa7b7319d1d

RUN pip install --no-cache-dir \
        pip==26.1.2 \
        setuptools==83.0.0 \
        wheel==0.47.0

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
