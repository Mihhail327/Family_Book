import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.logger import log_error
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
        "token": token
    })

# --- ОБРАБОТКА РЕГИСТРАЦИИ (POST) ---
@router.post("/register/{token}")
async def register(
    token: str,
    display_name: str = Form(...),
    avatar: UploadFile = File(None),
    session: Session = Depends(get_session)
):
    # 1. Проверка безопасности
    if token != settings.REGISTRATION_TOKEN:
        raise HTTPException(status_code=403)

    name = display_name.strip()
    res_error = RedirectResponse(f"/register/{token}", status_code=303)

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
    # Username генерируем автоматически (системный ID), так как в форме только Display Name
    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    
    new_user = User(
        username=unique_username,
        display_name=name,
        hashed_password=hash_password(settings.DEFAULT_USER_PASSWORD),
        role="user",
        avatar_url=avatar_url
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    # 4. Авторизация и редирект домой
    res = RedirectResponse("/", status_code=303)
    if new_user.id is not None:
        set_auth_cookies(res, int(new_user.id))
    
    flash(res, f"Добро пожаловать домой, {name}! ✨", "success")
    return res