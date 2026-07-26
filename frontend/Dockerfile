FROM node:26-alpine@sha256:e88a35be04478413b7c71c455cd9865de9b9360e1f43456be5951032d7ac1a66 AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/. .
COPY VERSION /VERSION
ARG APP_VERSION=
ARG VITE_SOURCE_URL=https://github.com/yutinglia/setlist
ARG VITE_PUBLIC_SITE_URL=http://localhost:8080
ENV VITE_APP_VERSION=${APP_VERSION}
ENV VITE_SOURCE_URL=${VITE_SOURCE_URL}
ENV VITE_PUBLIC_SITE_URL=${VITE_PUBLIC_SITE_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:18d67281256ded39ff65e010ae4f831be18f19356f83c60bc546492c7eb6dd23

ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.source="https://github.com/yutinglia/setlist" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT"
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/LICENSE.txt
COPY THIRD_PARTY_NOTICES.md /usr/share/nginx/html/THIRD_PARTY_NOTICES.md

EXPOSE 8080
