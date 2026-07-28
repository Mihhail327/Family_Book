import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.models import User
from app.database import get_session
from app.security import hash_password
from app.utils.flash import flash
from app.logger import log_action, log_error
from app.config import settings
from app.core.templates import templates
from .login import set_auth_cookies

router = APIRouter()

@router.get("/guest/{token}")
async def guest_welcome_page(request: Request, token: str):
    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="welcome.html",
        context={
            "request": request,
            "is_guest_invite": True,
            "token": str(token),
            "PROJECT_NAME": str(settings.PROJECT_NAME),
            "VERSION": str(settings.VERSION)
        }
    )

@router.get("/guest")
async def guest_no_token_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="welcome.html",
        context={
            "request": request,
            "is_guest_invite": False,
            "token": None,  # nosec B105
            "PROJECT_NAME": str(settings.PROJECT_NAME),
            "VERSION": str(settings.VERSION)
        }
    )

@router.post("/guest/{token}")
@router.post("/guest")
async def guest_login(request: Request, token: str | None = None, display_name: str = Form(...), session: Session = Depends(get_session)):
    """Эндпоинт входа в песочницу (Sandbox)"""
    if not token or token != settings.REGISTRATION_TOKEN:
        res_token_err = RedirectResponse("/", status_code=303)
        flash(res_token_err, "Вход в песочницу доступен только по персональной инвайт-ссылке!", "error")
        return res_token_err

    name = display_name.strip()
    res_error = RedirectResponse(f"/auth/guest/{token}", status_code=303)

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
        role="guest",       # Метка роли гостя
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
        from app.models import AuditLog
        from app.services.notifier import bot_alert
        client_ip = request.client.host if request.client else "127.0.0.1"
        audit = AuditLog(
            user_id=new_guest.id,
            action="GUEST_LOGIN",
            details=f"Вход гостя в песочницу: '{name}' (ID: {new_guest.id})",
            ip_address=client_ip
        )
        session.add(audit)
        session.commit()

        if settings.ENV != "testing":
            try:
                import asyncio
                asyncio.create_task(bot_alert.send_alert(
                    f"⌛ **GUEST SANDBOX LOGIN**\n👤 {name} (`{unique_username}`)\n🌐 IP: `{client_ip}`",
                    level="INFO"
                ))
            except Exception as e:
                log_error("GUEST_LOGIN_BOT_ALERT", str(e))
        
    # Форматируем время окончания для красивого вывода в уведомлении
    time_str = expiration_time.astimezone().strftime("%H:%M")
    
    flash(res, f"Демо-режим активирован! {name}, у тебя есть доступ до {time_str}.", "info")
    log_action("SYSTEM", "GUEST_LOGIN", f"Зашел гость '{name}'. Удаление в {time_str}")
    
    return res