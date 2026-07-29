import os
import logging
from logging.handlers import TimedRotatingFileHandler
from app.config import settings

# 1. Используем путь из настроек
LOG_DIR = settings.ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Единый формат для всех логов
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

def setup_logger(name: str, log_file: str, level=logging.INFO) -> logging.Logger:
    """
    Фабрика логгеров с умной ротацией.
    """
    # 🟢 ИСПРАВЛЕНО: Убрано дублирование. Выбираем только один тип хендлера.
    if os.getenv("ENVIRONMENT") == "testing":
        # Для тестов используем обычный FileHandler, чтобы Windows не блокировала файлы при ротации
        handler = logging.FileHandler(LOG_DIR / log_file, encoding='utf-8')
    else:
        # Для продакшена — TimedRotatingFileHandler с очисткой старых логов (30 дней)
        handler = TimedRotatingFileHandler(
            filename=LOG_DIR / log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )

    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Очищаем старые хендлеры, если логгер инициализируется повторно (важно для тестов)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.addHandler(handler)
    
    # Для системного логгера добавляем вывод в консоль (удобно для Docker/Render)
    if name == "System":
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
        
    return logger

# --- Инициализация независимых каналов ---
audit_logger = setup_logger("Audit", "audit.log")
system_logger = setup_logger("System", "system.log")
error_logger = setup_logger("Error", "error.log", level=logging.ERROR)

def log_action(user: str | None, action: str, details: str):
    username = user if user else "SYSTEM"
    message = f"👤 USER: {username} | ⚡ ACTION: {action} | 📝 DETAILS: {details}"
    
    if username == "SYSTEM" or "SYSTEM_" in username:
        system_logger.info(message)
    else:
        audit_logger.info(message)

def log_error(context: str, message: str):
    error_logger.error(f"❌ ERROR in {context}: {message}")

def format_exception_details(exc: Exception) -> str:
    """Форматирует стектрейс ошибки с указанием ключевых строк."""
    import traceback
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return "".join(tb_lines[-4:]).strip()

def log_exception(context: str, exc: Exception, user_info: str = "Anonymous"):
    """Подробное логирование любого исключения с трассировкой."""
    stack_info = format_exception_details(exc)
    error_logger.error(
        f"🔥 CRITICAL EXCEPTION [{context}] | User: {user_info} | Error: {type(exc).__name__}: {exc!s}\nTraceback:\n{stack_info}"
    )