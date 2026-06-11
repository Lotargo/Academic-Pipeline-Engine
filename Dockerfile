# Build stage for backend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
ENV POETRY_VERSION=1.8.2
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Copy package definition
COPY pyproject.toml poetry.lock* /app/

# Configure poetry to not create a virtual environment inside container
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --no-directory

# Copy code and configuration files
COPY academic_pe /app/academic_pe
COPY config /app/config
COPY scripts /app/scripts

# Create output folder if it doesn't exist
RUN mkdir -p /app/output

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "academic_pe.server:app", "--host", "0.0.0.0", "--port", "8000"]
