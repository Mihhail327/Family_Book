import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- 1. ГЕОГРАФИЯ ПРОЕКТА ---
APP_DIR = Path(__file__).resolve().parent 
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"

UPLOAD_DIR = STATIC_DIR / "uploads"
AVATARS_DIR = UPLOAD_DIR / "avatars"
POSTS_DIR = UPLOAD_DIR / "posts"

# Создаем папки при импорте конфига
for folder in [AVATARS_DIR, POSTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Определяем имя файла окружения
app_mode = os.getenv("APP_MODE", "dev")
env_file_name = f".env.{app_mode}"

# --- 2. КЛАСС НАСТРОЕК ---

class Settings(BaseSettings):
    # Окружение (development, production, testing)
    ENV: str = "development"
    
    # Основное
    PROJECT_NAME: str = "FamilyBook" 
    VERSION: str = "3.0.0"  
    
    # Безопасность
    SECRET_KEY: str = "super_secret_key_change_me"
    ADMIN_PASSWORD: str = "fallback_if_env_missing"
    DEFAULT_USER_PASSWORD: str = "1234"
    REGISTRATION_TOKEN: str = "family-invite-only"

    # 🤖 Sentinel Bot Settings
    BOT_TOKEN: str = "666666:your_token_here" 
    ADMIN_CHAT_ID: str = "12345678"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # БД
    DATABASE_URL: str = "sqlite:///./family_book.db"

    # Ограничения
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "gif", "webp"}

    # Константы путей
    STATIC_PATH: str = str(STATIC_DIR)
    TEMPLATES_PATH: str = str(TEMPLATES_DIR)
    AVATARS_PATH: str = str(AVATARS_DIR)
    POSTS_PATH: str = str(POSTS_DIR)

    # Единый конфиг для Pydantic
    model_config = SettingsConfigDict(
        # Используй глобальный ROOT_DIR через имя модуля или просто путь
        env_file=os.path.join(os.getcwd(), env_file_name), 
        env_file_encoding='utf-8',
        extra='ignore'
    )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def get_database_url(self) -> str:
        # Фикс для Render/Heroku, которые шлют postgres:// вместо postgresql://
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL

# Создаем единственный экземпляр
settings = Settings()