FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm@sha256:b1c8e01d2dcb17a102fdd0abd2d2f4737f2b1be0373944314ef22c39f3c4b931

RUN pip install --no-cache-dir \
        pip==26.1.2 \
        setuptools==83.0.0 \
        wheel==0.47.0

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
