# ==========================================
# Этап 1: Экспорт зависимостей (Builder)
# ==========================================
FROM python:3.13-slim AS builder

WORKDIR /build

ENV POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \# ==========================================
# Этап 1: Сборка зависимостей (Builder)
# ==========================================
FROM python:3.13-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.0.1 \
    POETRY_HOME="/opt/poetry"

# Системные зависимости для сборки C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN python -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install --no-cache-dir -U pip "poetry==$POETRY_VERSION"

ENV PATH="$POETRY_HOME/bin:$PATH"

COPY pyproject.toml poetry.lock* ./

# КРИТИЧЕСКИЙ ШАГ: Ставим пакеты в локальную директорию /build/dist-packages
# чтобы изолировать их и легко скопировать на следующий этап.
RUN if [ -f poetry.lock ]; then rm -f poetry.lock; fi && \
    poetry config virtualenvs.create false && \
    poetry run pip install --no-cache-dir -U pip && \
    poetry install --no-interaction --no-ansi --no-root --only main

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

# Копируем установленные пакеты напрямую из глобального python-окружения билдера
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код проекта
COPY . .

RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chmod -R 755 /app/app/static

EXPOSE 8000

# Теперь alembic и uvicorn гарантированно лежат в /usr/local/bin и доступны глобально!
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
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
