import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- 1. ГЕОГРАФИЯ ПРОЕКТА (Доступна везде) ---
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

UPLOAD_DIR = STATIC_DIR / "uploads"
AVATARS_DIR = UPLOAD_DIR / "avatars"
POSTS_DIR = UPLOAD_DIR / "posts"

# Создаем папки
for folder in [AVATARS_DIR, POSTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Определяем имя файла окружения
app_mode = os.getenv("APP_MODE", "dev")
env_file_name = f".env.{app_mode}"

# --- 2. КЛАСС НАСТРОЕК ---

class Settings(BaseSettings):
    # Окружение
    ENV: str = "development"
    
    # Основное
    PROJECT_NAME: str = "FamilyBook" 
    VERSION: str = "2.0.0"
    
    # Безопасность
    SECRET_KEY: str = "super_secret_key_change_me"
    ADMIN_PASSWORD: str = "fallback_if_env_missing"
    DEFAULT_USER_PASSWORD: str = "1234"
    REGISTRATION_TOKEN: str = "family-invite-only"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # БД
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR}/family_book.db"

    # Ограничения
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "gif", "webp"}

    # Константы путей (теперь они доступны как атрибуты класса)
    ROOT_DIR: Path = ROOT_DIR
    STATIC_PATH: str = str(STATIC_DIR)
    TEMPLATES_PATH: str = str(TEMPLATES_DIR)
    AVATARS_PATH: str = str(AVATARS_DIR)
    POSTS_PATH: str = str(POSTS_DIR)

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def get_database_url(self) -> str:
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL

    model_config = SettingsConfigDict(
        env_file=os.path.join(ROOT_DIR, env_file_name),
        env_file_encoding='utf-8',
        extra='ignore'
    )

# Создаем экземпляр
settings = Settings()