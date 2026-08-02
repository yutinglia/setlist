FROM node:26-alpine@sha256:233761595746769ebfdb6090f44fc7cdf818ae0ce62d2b37e0367723b9823e36 AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/. .
COPY VERSION /VERSION
ARG APP_VERSION=
ARG VITE_CHANNEL_REQUEST_URL=
ARG VITE_SOURCE_URL=https://github.com/yutinglia/setlist
ARG VITE_PUBLIC_SITE_URL=http://localhost:8080
ENV VITE_APP_VERSION=${APP_VERSION}
ENV VITE_CHANNEL_REQUEST_URL=${VITE_CHANNEL_REQUEST_URL}
ENV VITE_SOURCE_URL=${VITE_SOURCE_URL}
ENV VITE_PUBLIC_SITE_URL=${VITE_PUBLIC_SITE_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:59ccf0943b0b8e8d9e6ea9039a39555730f544701a655c596f7df7d096c593f5

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT"
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/LICENSE.txt
COPY THIRD_PARTY_NOTICES.md /usr/share/nginx/html/THIRD_PARTY_NOTICES.md

EXPOSE 8080
