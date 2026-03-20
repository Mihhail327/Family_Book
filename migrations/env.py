import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. ИМПОРТИРУЕМ SQLModel И ТВОИ МОДЕЛИ
from sqlmodel import SQLModel
from app.config import settings
# Импортируем модели, чтобы Alembic их "увидел"
from app.models import User, Post, PostImage, Comment, Notification, PostLike

# Это объект конфигурации Alembic
config = context.config

# Настройка логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. УКАЗЫВАЕМ МЕТАДАННЫЕ
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' моде (генерирует SQL скрипт)."""
    # Берем URL из настроек нашего приложения (settings.DATABASE_URL)
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True, # Позволяет видеть изменения типов колонок
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Запуск миграций в 'online' моде (реальное подключение к БД)."""
    
    # 3. ДИНАМИЧЕСКИ ПОДМЕНЯЕМ URL ИЗ SETTINGS
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()