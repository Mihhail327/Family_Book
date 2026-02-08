import json
from fastapi import Response, Request

def flash(response: Response, message: str, category: str = "info"):
    """
    Записывает сообщение в куки. 
    Категории: 'success' (зеленый), 'error' (красный), 'info' (синий).
    """
    flash_data = json.dumps({"message": message, "category": category})
    response.set_cookie(key="flash", value=flash_data, max_age=10) # Живет 10 секунд

def get_flashed_messages(request: Request):
    """Извлекает и удаляет сообщение из куки (чтобы не висело вечно)."""
    flash_cookie = request.cookies.get("flash")
    if flash_cookie:
        try:
            return json.loads(flash_cookie)
        except:
            return None
    return None