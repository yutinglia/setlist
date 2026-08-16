FROM postgres:18-bookworm@sha256:7d2695c3aa88e792e8b3b233e7e4adb296a20412c6c0ca361e3edaaacfada108

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="PostgreSQL"

# Compose uses a named volume whose ownership is initialized from the image.
# Running directly as postgres makes the setuid helper unnecessary and removes
# its separately compiled Go runtime from the production attack surface.
RUN rm -f /usr/local/bin/gosu
USER postgres
