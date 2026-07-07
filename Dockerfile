# ==========================================
# Этап 1: Сборка зависимостей (Builder)
# ==========================================
FROM python:3.13-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# Устанавливаем системные зависимости, необходимые только для компиляции
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry в изолированную директорию
RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install --no-cache-dir --upgrade pip && \
    $POETRY_HOME/bin/pip install --no-cache-dir "poetry==$POETRY_VERSION"

ENV PATH="$POETRY_HOME/bin:$PATH"

COPY pyproject.toml poetry.lock* ./

# Корректная сборка зависимостей без конфликтов хэшей локального lock-файла
RUN if [ -f poetry.lock ]; then \
        rm -f poetry.lock && \
        poetry install --no-interaction --no-ansi --no-root --only main; \
    else \
        poetry install --no-interaction --no-ansi --no-root --only main; \
    fi

# ==========================================
# Этап 2: Финальный продакшен-образ (Runner)
# ==========================================
FROM python:3.13-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Устанавливаем только runtime-зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем скомпилированное виртуальное окружение
COPY --from=builder /build/.venv /app/.venv

# Копируем исходный код проекта
COPY . .

# Создаем необходимые директории для статики и логов
RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chmod -R 755 /app/app/static

EXPOSE 8000

# Запуск с явным указанием пути к бинарникам внутри .venv
CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"]
