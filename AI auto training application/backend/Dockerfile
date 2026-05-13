# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# NOTE: We intentionally do NOT call `apt-get install` here.
#   - All Python deps in this image ship as prebuilt manylinux wheels
#     (asyncpg, psycopg2-binary, Pillow, etc.), so no C toolchain is needed.
#   - The healthcheck uses Python's stdlib instead of curl.
#   - libgl1 / libglib2.0-0 (needed only when the optional `ultralytics`
#     extra is installed) is documented at the bottom of this file.
#
# Skipping apt-get avoids broken-network situations on first build (HTTP
# port 80 to deb.debian.org is blocked on some corporate / VPN networks).

# ----- python deps (cached layer) -----
WORKDIR /app
COPY pyproject.toml ./
# `pip install -e .` needs a stub package layout. Install top-level deps now;
# the actual app code is copied below so editing it doesn't invalidate this
# expensive layer.
RUN mkdir -p app && touch app/__init__.py \
    && pip install --upgrade pip \
    && pip install -e .

# Uncomment to bake training deps into the image (adds ~2GB and also requires
# `apt-get install -y libgl1 libglib2.0-0` to be added above).
# RUN pip install -e ".[training]"

# ----- app code -----
COPY . .

# ----- non-root user -----
# adduser is part of base image, no apt needed
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 app \
    && mkdir -p /data && chown -R app:app /app /data
USER app

EXPOSE 8000

# Healthcheck uses Python (stdlib) so we don't depend on curl being installed.
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/healthz', timeout=2).status==200 else 1)" \
        || exit 1

# Default: migrate then serve. docker-compose dev override adds --reload.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
