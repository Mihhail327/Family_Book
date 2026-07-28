#!/bin/bash
# Назначение: Скрипт оркестрации и запуска сервисов (web / worker)
set -e

SERVICE_TYPE="${SERVICE_TYPE:-web}"

if [ "$SERVICE_TYPE" = "web" ]; then
    echo "=== Starting WEB Service ==="
    
    echo "Running database migrations via Alembic..."
    alembic upgrade head

    echo "Starting Uvicorn Application Server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000

elif [ "$SERVICE_TYPE" = "worker" ]; then
    echo "=== Starting CELERY WORKER Service ==="
    
    exec celery -A app.core.celery_app.celery_instance worker --loglevel=info

else
    echo "ERROR: Unknown SERVICE_TYPE: $SERVICE_TYPE"
    exit 1
fi
