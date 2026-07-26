FROM postgres:18-bookworm@sha256:1961f96e6029a02c3812d7cb329a3b03a3ac2bb067058dec17b0f5596aca9296

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="PostgreSQL"

# Compose uses a named volume whose ownership is initialized from the image.
# Running directly as postgres makes the setuid helper unnecessary and removes
# its separately compiled Go runtime from the production attack surface.
RUN rm -f /usr/local/bin/gosu
USER postgres
