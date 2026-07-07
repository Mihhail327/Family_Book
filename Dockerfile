# ==========================================
# Этап 1: Экспорт зависимостей (Builder)
# ==========================================
FROM python:3.13-slim AS builder

WORKDIR /build

ENV POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install --no-cache-dir -U pip "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./

# Генерируем чистый requirements.txt без использования капризных локальных .venv слоев
RUN $POETRY_HOME/bin/poetry export --without-hashes --format=requirements.txt > requirements.txt

# ==========================================
# Этап 2: Финальный продакшен-образ (Runner)
# ==========================================
FROM python:3.13-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем только сгенерированный файл зависимостей
COPY --from=builder /build/requirements.txt .

# Устанавливаем пакеты напрямую в глобальный контекст python внутри runner
# (Для изолированного Docker-контейнера внутренний venv избыточен и только путает пути)
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код проекта
COPY . .

RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chmod -R 755 /app/app/static

EXPOSE 8000

# Теперь все бинарники гарантированно сидят в стандартном глобальном PATH системы!
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
