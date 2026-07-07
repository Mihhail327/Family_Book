#!/bin/bash
set -e

# Docstrings in English (Google Style), Comments in Russian
# Назначение: Скрипт инициализации и запуска веб-слоя приложения

echo "==> Применение миграций базы данных Alembic..."
alembic upgrade head

echo "==> Запуск веб-сервера Uvicorn..."
# Использование exec заменяет текущий процесс bash процессом сервера,
# позволяя Docker корректно пробрасывать системные сигналы (SIGTERM) для graceful shutdown.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
