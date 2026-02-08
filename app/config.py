import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Сначала определяем имя файла (ДО класса)
app_mode = os.getenv("APP_MODE", "dev") # берем из системы или ставим 'dev'
env_file_name = f".env.{app_mode}"

# --- 1. СТРОГАЯ ГЕОГРАФИЯ ПРОЕКТА ---

# Путь к папке app/ (где лежит этот файл)
APP_DIR = Path(__file__).resolve().parent

# Путь к корню проекта (на уровень выше app/)
ROOT_DIR = APP_DIR.parent

# Папка со статикой (всегда внутри app/static)
STATIC_DIR = APP_DIR / "static"

# Папка для загрузок
UPLOAD_DIR = STATIC_DIR / "uploads"
AVATARS_DIR = UPLOAD_DIR / "avatars"
POSTS_DIR = UPLOAD_DIR / "posts"

# Автоматическое создание всех нужных папок при импорте конфига
for folder in [AVATARS_DIR, POSTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# --- 2. КЛАСС НАСТРОЕК (Pydantic) ---

class Settings(BaseSettings):
    # Основное
    PROJECT_NAME: str = "FamilyBook"
    VERSION: str = "1.3.1"
    ENVIRONMENT: str = "development"
    
    # Безопасность
    SECRET_KEY: str = "super_secret_key_change_me"
    
    # База данных (кладем файл в корень проекта)
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR}/family_book.db"
    
    # Пути для использования в коде (строки)
    # Мы отдаем абсолютные пути, чтобы Python никогда не терял файлы
    STATIC_PATH: str = str(STATIC_DIR)
    UPLOAD_PATH: str = str(UPLOAD_DIR)
    AVATARS_PATH: str = str(AVATARS_DIR)
    POSTS_PATH: str = str(POSTS_DIR)
    
    # Ограничения
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20 MB
    ALLOWED_EXTENSIONS: set = {"png", "jpg", "jpeg", "gif", "webp"}

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    model_config = SettingsConfigDict(
        env_file=env_file_name, 
        env_file_encoding='utf-8',
        extra='ignore'
    )

# Создаем экземпляр для импорта в другие модули
settings = Settings()