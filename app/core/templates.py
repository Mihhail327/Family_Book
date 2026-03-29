from fastapi.templating import Jinja2Templates
from app.config import settings
from app.utils.flash import get_flashed_messages

# 1. Инициализируем шаблоны
templates = Jinja2Templates(directory="app/templates")

# 2. Добавляем системные функции (range, str и т.д.) и твои настройки
# Мы используем метод update, но передаем settings через лямбду, 
# чтобы избежать той самой ошибки с dict.
templates.env.globals.update({
    "range": range,  # ВОЗВРАЩАЕМ RANGE
    "str": str,      # На всякий случай возвращаем str
    "PROJECT_NAME": str(settings.PROJECT_NAME),
    "VERSION": str(settings.VERSION),
    "get_flashed_messages": get_flashed_messages,
    "settings": lambda: settings  # Безопасная передача настроек
})