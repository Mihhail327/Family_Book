from fastapi.templating import Jinja2Templates
from app.config import settings
from app.utils.flash import get_flashed_messages

# 1. Инициализируем шаблоны
templates = Jinja2Templates(directory="app/templates")

# 2. Добавляем функции и константы в глобальную область видимости
# Мы передаем PROJECT_NAME и VERSION как строки (они хешируются без проблем)
templates.env.globals.update(
    PROJECT_NAME=str(settings.PROJECT_NAME),
    VERSION=str(settings.VERSION),
    get_flashed_messages=get_flashed_messages,
    # Самое важное: передаем settings как ЛЯМБДУ (функцию)
    # Это обходит ошибку "unhashable type: 'dict'", так как функция хешируема
    settings=lambda: settings
)