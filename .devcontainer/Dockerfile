FROM mcr.microsoft.com/devcontainers/python:3-3.12-bookworm

RUN pip install --no-cache-dir -U pip setuptools wheel

COPY data_updater/requirements.txt data_updater/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt \
    && rm /tmp/requirements.txt /tmp/requirements-dev.txt
