FROM python:3.13-slim

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка Poetry
RUN pip install poetry && poetry config virtualenvs.create false

# Копируем зависимости
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --no-dev

# Копируем код
COPY . .

# Создаем папки для статики и логов, если их нет
RUN mkdir -p /app/app/static/uploads/posts /app/app/static/uploads/avatars /app/app/logs

EXPOSE 8000

# Запуск через gunicorn с uvicorn-воркерами
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000"]