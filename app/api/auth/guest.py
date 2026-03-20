import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.models import User
from app.database import get_session
from app.security import hash_password
from app.utils.flash import flash
from app.logger import log_action
from .login import set_auth_cookies

router = APIRouter()

@router.post("/guest")
async def guest_login(display_name: str = Form(...), session: Session = Depends(get_session)):
    """Эндпоинт входа в песочницу (Sandbox)"""
    name = display_name.strip()
    res_error = RedirectResponse("/auth/login", status_code=303)

    # Базовая валидация имени гостя
    if len(name) < 2 or len(name) > 20:
        flash(res_error, "Имя должно быть от 2 до 20 символов", "error")
        return res_error

    # Генерируем уникальные технические данные для гостя
    unique_username = f"guest_{uuid.uuid4().hex[:8]}"
    dummy_pwd = hash_password(uuid.uuid4().hex) # Пароль гостю не нужен, генерируем случайный хэш
    
    # Засекаем ровно 30 минут жизни для сессии
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes=30)

    new_guest = User(
        username=unique_username,
        display_name=name,
        hashed_password=dummy_pwd,
        role="user",       # Даем права обычного пользователя для тестов
        is_guest=True,     # Ставим метку для нашей "метлы" (Garbage Collector)
        expires_at=expiration_time,
        avatar_url="/static/default_avatar.png"
    )
    
    session.add(new_guest)
    session.commit()
    session.refresh(new_guest)
    
    res = RedirectResponse("/", status_code=303)
    if new_guest.id:
        set_auth_cookies(res, int(new_guest.id))
        
    # Форматируем время окончания для красивого вывода в уведомлении
    time_str = expiration_time.astimezone().strftime("%H:%M")
    
    flash(res, f"Демо-режим активирован! {name}, у тебя есть доступ до {time_str}.", "info")
    log_action("SYSTEM", "GUEST_LOGIN", f"Зашел гость '{name}'. Удаление в {time_str}")
    
    return res