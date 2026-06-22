FROM python:3.13-slim

# 1. Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH" \
    POETRY_VERSION=2.0.1

# 2. Установка Poetry
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "poetry==$POETRY_VERSION"

RUN poetry config virtualenvs.create false

# 3. Установка зависимостей (вариант без lock-файла вообще)
COPY pyproject.toml ./
RUN poetry install --no-interaction --no-ansi --no-root --only main --no-cache

# 4. Копируем проект
COPY . .
COPY start.sh /app/start.sh

# 5. Создание директорий и права
RUN mkdir -p /app/app/static/uploads/posts \
             /app/app/static/uploads/avatars \
             /app/app/logs && \
    chmod -R 755 /app/app/static && \
    chmod +x /app/start.sh

EXPOSE 8000

# 6. ЗАПУСК через старт-скрипт оркестрации
CMD ["/app/start.sh"]