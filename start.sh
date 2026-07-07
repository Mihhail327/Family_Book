#!/bin/bash
set -e

# Docstrings in English (Google Style), Comments in Russian
# Назначение: Скрипт оркестрации прав доступа и безопасного запуска приложения

echo "==> Проверка и исправление прав доступа на примонтированные тома..."
chown -R 10001:10001 /app/app/static/uploads /app/app/logs 2>/dev/null || true

# Корректируем права на директорию SQLite, если используется именованный волюм /app/db_data
if [ -d "/app/db_data" ]; then
    chown -R 10001:10001 /app/db_data 2>/dev/null || true
fi

echo "==> Применение миграций базы данных Alembic..."
# Запускаем от имени appuser, чтобы новые файлы логов/бд не создавались под root
su appuser -c "alembic upgrade head"

echo "==> Запуск веб-сервера Uvicorn от имени appuser..."
exec su appuser -c "exec uvicorn app.main:app --host 0.0.0.0 --port 8000"
