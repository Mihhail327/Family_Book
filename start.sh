#!/bin/bash
set -e

# Накатываем миграции Alembic
poetry run alembic upgrade head

# Фоновый запуск воркера Celery
poetry run celery -A app.core.celery_app.celery_instance worker --loglevel=info &

# Запуск веб-сервера через exec
exec poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
