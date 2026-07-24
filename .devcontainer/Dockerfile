FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm

# Base image may ship a Yarn apt repo whose GPG key drifts (NO_PUBKEY 62D54FD4003F6525),
# which makes apt-get update fail. We don't need that repo for this project.
# https://github.com/devcontainers/images/issues/1752
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Keep pip current for reproducible installs of pinned requirements
RUN pip install --no-cache-dir -U pip setuptools wheel

# Bake API deps into the image so recreate / missing postCreate still works.
# Build context is the repo root (see docker-compose.yml).
COPY data_updater/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
