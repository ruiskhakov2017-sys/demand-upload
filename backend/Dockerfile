FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/deps
COPY backend/pyproject.toml /opt/deps/pyproject.toml
RUN mkdir -p app \
    && touch app/__init__.py \
    && pip install --upgrade pip \
    && pip install ".[dev]"

WORKDIR /app
COPY backend /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
