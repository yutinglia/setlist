FROM postgres:18-bookworm@sha256:882236b897e39051d2368c5ccc6cda944904723506b2dfc97f2a8f5bc9afa382

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="PostgreSQL"

# Compose uses a named volume whose ownership is initialized from the image.
# Running directly as postgres makes the setuid helper unnecessary and removes
# its separately compiled Go runtime from the production attack surface.
RUN rm -f /usr/local/bin/gosu
USER postgres
