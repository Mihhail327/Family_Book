import json
from fastapi import Response, Request

def flash(response: Response, message: str, category: str = "info"):
    """
    Записывает сообщение в куку. 
    Категории: 'success', 'error', 'info'.
    """
    # Сериализуем данные в JSON
    flash_data = json.dumps({"message": message, "category": category})
    # Устанавливаем куку. httponly=True для безопасности. max_age=10 удалит её через 10 сек.
    response.set_cookie(key="flash", value=flash_data, max_age=10, httponly=True)

def get_flashed_messages(request: Request):
    """
    Извлекает сообщение из куки для отображения во фронтенде.
    """
    flash_cookie = request.cookies.get("flash")
    if not flash_cookie:
        return []

    try:
        data = json.loads(flash_cookie)
        # ИСПРАВЛЕНО: Возвращаем список словарей, чтобы Jinja2 мог читать msg.message
        return [data]
    except (json.JSONDecodeError, TypeError):
        return []