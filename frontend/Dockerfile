FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/. .
ARG VITE_SOURCE_URL=https://github.com/yutinglia/vtuber-karaoke-search
ARG VITE_PUBLIC_SITE_URL=http://localhost:8080
ENV VITE_SOURCE_URL=${VITE_SOURCE_URL}
ENV VITE_PUBLIC_SITE_URL=${VITE_PUBLIC_SITE_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine

LABEL org.opencontainers.image.source="https://github.com/yutinglia/vtuber-karaoke-search" \
      org.opencontainers.image.licenses="MIT"
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/LICENSE.txt

EXPOSE 8080
