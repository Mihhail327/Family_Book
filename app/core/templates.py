from fastapi.templating import Jinja2Templates
from app.config import settings
from app.utils.flash import get_flashed_messages

# Инициализируем один раз здесь
templates = Jinja2Templates(directory="app/templates")

# Добавляем глобальные переменные
templates.env.globals.update(
    settings=settings,
    get_flashed_messages=get_flashed_messages
)