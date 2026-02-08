FROM python:3.13-slim

# Установка системных зависимостей (нужны для сборки bcrypt и pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/root/.local/bin:$PATH"

# Обновляем pip и ставим Poetry
RUN pip install --upgrade pip && \
    pip install "poetry>=2.0.0"

# В Poetry 2.0 конфиг для venv остается прежним
RUN poetry config virtualenvs.create false

# Копируем только файлы зависимостей
COPY pyproject.toml poetry.lock* ./

# ВАЖНО: Poetry 2.0 иногда требует, чтобы проект был инициализирован
# Используем --no-root, чтобы не пытаться ставить сам пакет family-book
RUN poetry install --no-interaction --no-ansi --no-root

# Теперь копируем всё остальное
COPY . .

# Создаем директории для работы
RUN mkdir -p /app/app/static/uploads/posts /app/app/static/uploads/avatars /app/app/logs

EXPOSE 8000

# Запуск через gunicorn с увеличенным тайм-аутом до 120 секунд
CMD ["python", "-m", "gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--timeout", "120"]