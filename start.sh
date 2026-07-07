#!/bin/bash
set -e

# Docstrings in English (Google Style), Comments in Russian
# Исправление прав перед выполнением команд

# Если папки логов или бд принадлежат root, берем права на них
if [ "$(id -u)" = '0' ]; then
    chown -R 10001:10001 /app/app/static/uploads /app/app/logs 2>/dev/null || true
fi

echo "==> Применение миграций базы данных Alembic..."
alembic upgrade head

echo "==> Запуск веб-сервера Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
