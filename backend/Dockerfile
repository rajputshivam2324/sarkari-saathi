# Sarkari Saathi backend for Google Cloud Run.
# Build context is the backend/ folder:  docker build -t sarkari-api backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Do not run as root.
RUN useradd --create-home --uid 10001 app && chown -R app:app /srv
USER app

# Cloud Run sets PORT (8080). Settings come from environment variables, not from a .env file.
ENV PORT=8080
EXPOSE 8080

# --proxy-headers: Cloud Run terminates TLS, so trust X-Forwarded-* for the real client address and scheme.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'
