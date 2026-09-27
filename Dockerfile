FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOOKS_HOST=0.0.0.0 \
    BOOKS_PORT=8501 \
    BOOKS_DB_PATH=/data/books.sqlite3

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && chmod +x /app/scripts/docker-entrypoint.sh \
    && mkdir -p /data

VOLUME ["/data"]
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -m books.health

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
