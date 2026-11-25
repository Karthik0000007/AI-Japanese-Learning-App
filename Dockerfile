# Offline AI Japanese Trainer — app image.
# Speech extras (Whisper, TTS) are not installed here to keep the image small;
# the app runs without them and those endpoints answer 503.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as an unprivileged user
RUN useradd --create-home --uid 1000 app
COPY --chown=app:app . .
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=8)"

# 1. migrate  2. load the N5 sample (idempotent: inserts nothing after the first run)  3. serve
CMD ["sh", "-c", "python -m alembic upgrade head && python -m tools.seed --sample && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
