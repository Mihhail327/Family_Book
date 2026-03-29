from fastapi.templating import Jinja2Templates
from app.config import settings
from app.utils.flash import get_flashed_messages

# Инициализируем один раз
templates = Jinja2Templates(directory="app/templates")

# Добавляем глобальные переменные ПРАВИЛЬНО
templates.env.globals.update(
    PROJECT_NAME=settings.PROJECT_NAME,
    VERSION=settings.VERSION,
    get_flashed_messages=get_flashed_messages,
    # Мы передаем функцию, которая возвращает настройки. 
    # Теперь в HTML ты по-прежнему пишешь {{ settings.PROJECT_NAME }}, 
    # но Jinja вызывает функцию и не пытается хешировать сам объект.
    settings=lambda: settings 
)