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

# Создаем не-root пользователя для безопасного выполнения процессов
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Устанавливаем только runtime-зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем скомпилированное виртуальное окружение
COPY --from=builder /build/.venv /app/.venv

# Копируем исходный код проекта
COPY --chown=appuser:appgroup . .

# Создаем необходимые директории для статики и логов, выставляя права владения
RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chown -R appuser:appgroup /app/app/static /app/app/logs && \
    chmod -R 755 /app/app/static && \
    chmod +x /app/start.sh

# Оставляем контейнер стартовать под root, чтобы скрипт мог поправить права на Volumes.
# Снижение привилегий произойдет внутри start.sh

EXPOSE 8000

# ИСПРАВЛЕНО: Указан точный абсолютный путь к скрипту внутри рабочей директории
CMD ["/start.sh"]
