# ==========================================
# Этап 1: Сборка зависимостей (Builder)
# ==========================================
FROM python:3.12.3-slim-bookworm AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install --no-cache-dir -U pip "poetry==$POETRY_VERSION"

ENV PATH="$POETRY_HOME/bin:$PATH"

COPY pyproject.toml poetry.lock ./

# Контракт: Детальное логирование (-vvv) и установка без создания virtualenv
RUN poetry config virtualenvs.create false && \
    poetry install -vvv --no-interaction --no-ansi --no-root --only main

# ==========================================
# Этап 2: Финальный продакшен-образ (Runner)
# ==========================================
FROM python:3.12.3-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Контракт: Пути жестко привязаны к версии Python 3.12 (Исправлено)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

COPY . .

RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chown -R appuser:appgroup /app/app/static /app/app/logs /app/db_data && \
    chmod -R 755 /app/app/static

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
