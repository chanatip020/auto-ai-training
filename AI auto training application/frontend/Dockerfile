# syntax=docker/dockerfile:1.6
# Multi-stage: build static bundle with Node, serve with nginx.
#
# Using node:20-bookworm-slim (Debian-based) instead of node:20-alpine
# because some Alpine variants ship without npm in $PATH inside BuildKit
# contexts, which produced "npm: not found" on first build.
FROM node:20-bookworm-slim AS build
WORKDIR /app

# Cache layer for deps. Use npm ci when package-lock.json exists.
COPY package.json ./
COPY package-lock.json* ./
RUN if [ -f package-lock.json ]; then \
        npm ci --no-audit --no-fund ; \
    else \
        npm install --no-audit --no-fund ; \
    fi

# Build
COPY . .
# In Docker, the bundle calls /api on the same origin (nginx proxies to api).
ENV VITE_API_BASE=""
RUN npm run build

# ----- runtime stage -----
FROM nginx:1.27-alpine AS runtime

# Replace the default site config with one that proxies /api -> api:8000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Drop in the built bundle
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
