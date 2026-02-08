import logging
import os
from datetime import datetime

# Создаем папку для логов, если её нет
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Настройка основного конфига
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        # encoding='utf-8' критически важен для записи кириллицы (имен пользователей)
        logging.FileHandler(os.path.join(LOG_DIR, "access.log"), encoding='utf-8'),
        logging.StreamHandler() # Чтобы видеть логи прямо в терминале PyCharm/VS Code
    ]
)

logger = logging.getLogger("FamilyBook")

def log_action(user: str, action: str, details: str):
    """
    Логирует действия пользователей (вход, регистрация, создание поста).
    Это поможет тебе на защите показать статистику активности.
    """
    logger.info(f"👤 USER: {user} | ⚡ ACTION: {action} | 📝 DETAILS: {details}")

def log_error(context: str, message: str):
    """
    Отдельный метод для записи ошибок сервера или базы данных.
    """
    logger.error(f"❌ ERROR in {context}: {message}")