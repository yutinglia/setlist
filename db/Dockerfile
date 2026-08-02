FROM flyway/flyway:13-alpine@sha256:0ac8d526acfaa11bef99926cabf9d7247d2469e488aded8e3b86ec380bb76e83

# Keep only the PostgreSQL driver and remove optional network/database clients
# that are not used by this image. Upgrade the pinned Alpine base to the latest
# security-fixed packages available for its release.
USER root
RUN apk upgrade --no-cache \
    && find /flyway/drivers -mindepth 1 -maxdepth 1 \
        ! -name 'postgresql-*.jar' \
        ! -name 'put-your-jdbc-drivers-here.txt' \
        -exec rm -rf {} + \
    && find /flyway/lib/flyway -type f \
        ! -name 'flyway-commandline-*.jar' \
        ! -name 'flyway-command-mcp-*.jar' \
        ! -name 'flyway-core-*.jar' \
        ! -name 'flyway-database-postgresql-*.jar' \
        ! -name 'flyway-verb-migrate-*.jar' \
        ! -name 'flyway-verb-validate-*.jar' \
        -delete \
    && rm -rf /flyway/lib/aad /flyway/lib/netty \
    && addgroup -g 10001 flyway \
    && adduser -D -u 10001 -G flyway flyway

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT"

COPY db/migrations /flyway/sql
USER 10001:10001
