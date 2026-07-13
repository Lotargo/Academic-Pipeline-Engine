# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=1.8.2
ENV PORT=8000

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root --no-directory

COPY alembic.ini ./
COPY migrations ./migrations
COPY academic_pe ./academic_pe
COPY config ./config
COPY scripts ./scripts

RUN useradd --system --create-home --uid 1001 --shell /usr/sbin/nologin ape \
    && mkdir --parents /app/exports \
    && chown --recursive ape:ape /app

USER ape

EXPOSE 8000

CMD ["sh", "-c", "uvicorn academic_pe.server:app --host 0.0.0.0 --port ${PORT}"]
