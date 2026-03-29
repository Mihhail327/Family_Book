import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.logger import log_action, log_error
from app.models import User
from app.database import get_session
from app.security import hash_password
from app.config import settings 
from app.utils.flash import flash
from app.core.templates import templates  
from .login import set_auth_cookies
from app.utils.images import process_and_save_image

router = APIRouter()

# --- СТРАНИЦА РЕГИСТРАЦИИ (GET) ---
@router.get("/register/{token}")
async def register_page(request: Request, token: str):
    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=404)
    
    return templates.TemplateResponse("register.html", {
        "request": request, 
        "token": str(token),
        "PROJECT_NAME": str(settings.PROJECT_NAME),
        "VERSION": str(settings.VERSION)
    })

# --- ОБРАБОТКА РЕГИСТРАЦИИ (POST) ---
@router.post("/register/{token}")
async def register(
    request: Request,
    token: str,
    display_name: str = Form(...),
    confirm_email_address: str = Form(None), 
    avatar: UploadFile = File(None),
    session: Session = Depends(get_session)
):
    # 1. Защита Sentinel
    if confirm_email_address: 
        log_action(None, "SECURITY", f"Honeypot triggered from IP: {request.client.host}") # type: ignore
        return RedirectResponse("/", status_code=303) 

    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=403)

    # 2. Логика валидации имени
    name = display_name.strip()
    if len(name) < 2:
        res_error = RedirectResponse(f"/auth/register/{token}", status_code=303)
        flash(res_error, "Имя слишком короткое", "error")
        return res_error

    # 3. Обработка Аватара
    avatar_url = "/static/default_avatar.png"
    if avatar and avatar.filename:
        try:
            file_name = f"avatar_{uuid.uuid4().hex[:10]}.webp"
            file_path = Path(settings.AVATARS_PATH) / file_name
            success_path = process_and_save_image(avatar.file, str(file_path))
            if success_path:
                avatar_url = f"/static/uploads/avatars/{file_name}"
        except Exception as e:
            log_error("SYSTEM", f"Ошибка аватара: {e}")

    # --- ЛОГИКА ДЛЯ ГОСТЕЙ ---
    is_guest_mode = request.query_params.get("is_guest") == "true"
    role = "guest" if is_guest_mode else "user"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30) if is_guest_mode else None

    # 4. Создание пользователя
    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    new_user = User(
        username=unique_username,
        display_name=name,
        hashed_password=hash_password(settings.DEFAULT_USER_PASSWORD),
        role=role,
        is_guest=is_guest_mode,
        expires_at=expires_at,
        avatar_url=avatar_url
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 5. Авторизация
    res = RedirectResponse("/", status_code=303)
    if new_user.id is not None:
        set_auth_cookies(res, int(new_user.id))
    
    welcome_msg = f"Добро пожаловать в песочницу, {name}! ⏳" if is_guest_mode else f"Добро пожаловать домой, {name}! ✨"
    flash(res, welcome_msg, "success")
    
    return res