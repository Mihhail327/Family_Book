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
    from app.config import settings
    
    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=404)
    
    # Мы передаем только строку PROJECT_NAME и VERSION. 
    # Объект settings НЕ передаем целиком, чтобы не триггерить ошибку.
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
    confirm_email_address: str = Form(None), # 🍯 Ловушка здесь!
    avatar: UploadFile = File(None),
    session: Session = Depends(get_session)
):
    # --- ЗАЩИТА SENTINEL ---
    # 1. Проверка Honeypot
    if confirm_email_address: 
        log_action(None, "SECURITY", f"Honeypot triggered from IP: {request.client.host}") # type: ignore
        return RedirectResponse("/", status_code=303) 

    # 2. Проверка токена
    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=403)

    # --- ЛОГИКА РЕГИСТРАЦИИ ---
    name = display_name.strip()
    res_error = RedirectResponse(f"/auth/register/{token}", status_code=303)

    if len(name) < 2:
        flash(res_error, "Имя слишком короткое", "error")
        return res_error

    # 2. Обработка Аватара
    avatar_url = "/static/default_avatar.png"
    
    if avatar and avatar.filename:
        try:
            # 1. Генерируем имя файла сразу с расширением .webp
            file_name = f"avatar_{uuid.uuid4().hex[:10]}.webp"
            file_path = Path(settings.AVATARS_PATH) / file_name

            # 2. Используем магическую функцию обработки
            # Она принимает file.file (BinaryID) и путь назначения
            success_path = process_and_save_image(avatar.file, str(file_path))

            if success_path:
                avatar_url = f"/static/uploads/avatars/{file_name}"
            else:
                # Если обработка не удалась (например, файл - не картинка)
                log_error("SYSTEM","REGISTER_IMG_FAIL")
                

        except Exception as e:
            log_error("SYSTEM", f"Критическая ошибка загрузки аватара: {e}")
            avatar_url = "/static/default_avatar.png" 

    # 3. Создание пользователя
    # Проверяем, есть ли в URL параметр ?is_guest=true
    is_guest_mode = request.query_params.get("is_guest") == "true"
    
    role = "user"
    expires_at = None
    
    if is_guest_mode:
        role = "guest"
        # Настраиваем время смерти: +30 минут от текущего момента
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)


    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    
    new_user = User(
        username=unique_username,
        display_name=name,
        hashed_password=hash_password(settings.DEFAULT_USER_PASSWORD),
        role=role,
        is_guest=is_guest_mode,  # Проставляем флаг
        expires_at=expires_at,   # Ставим таймер удаления
        avatar_url=avatar_url
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 4. Авторизация и редирект домой
    res = RedirectResponse("/", status_code=303)
    if new_user.id is not None:
        set_auth_cookies(res, int(new_user.id))
    
    # Красивое приветствие в зависимости от роли
    welcome_msg = f"Добро пожаловать в песочницу, {name}! ⏳" if is_guest_mode else f"Добро пожаловать домой, {name}! ✨"
    flash(res, welcome_msg, "success")
    
    return res