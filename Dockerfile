# syntax=docker/dockerfile:1
FROM python:3.12-slim AS dependency-builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.2
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV" \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root --no-directory

FROM python:3.12-slim AS backend-base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --from=dependency-builder /opt/venv /opt/venv

COPY alembic.ini ./
COPY migrations ./migrations
COPY academic_pe ./academic_pe
COPY config ./config
COPY scripts ./scripts

RUN useradd --system --create-home --uid 1001 --shell /usr/sbin/nologin ape \
    && mkdir --parents /app/exports \
    && chown --recursive ape:ape /app

USER ape

FROM backend-base AS api

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/readyz', timeout=3)"]

CMD ["sh", "-c", "uvicorn academic_pe.server:app --host 0.0.0.0 --port ${PORT}"]

FROM backend-base AS export

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libreoffice-core libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*
USER ape

# Compose supplies the queue-specific Celery command.  Keeping the default as
# an executable converter probe makes accidental direct runs fail fast instead
# of starting an API image with LibreOffice installed.
CMD ["soffice", "--headless", "--version"]
