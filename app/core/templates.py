from fastapi.templating import Jinja2Templates
from app.utils.flash import get_flashed_messages

# Просто инициализируем шаблоны
templates = Jinja2Templates(directory="app/templates")

# Очищаем глобалы от всего подозрительного
templates.env.globals.clear()

# Оставляем только то, что точно не словарь
templates.env.globals["get_flashed_messages"] = get_flashed_messages