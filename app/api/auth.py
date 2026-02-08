import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, Request, File, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.models import User, Post
from app.database import get_session
from app.security import hash_password, get_current_user, create_session_token
from app.utils.images import process_and_save_image
from app.config import settings
from app.logger import log_action
from app.utils.flash import flash, get_flashed_messages

router = APIRouter()

# Корректная настройка шаблонов
templates = Jinja2Templates(directory=str(Path(settings.STATIC_PATH).parent / "templates"))
templates.env.globals.update(get_flashed_messages=get_flashed_messages)

def set_auth_cookie(response: RedirectResponse, user_id: int):
    token = create_session_token(user_id)
    response.set_cookie(
        key="user_session", 
        value=token, 
        httponly=True, 
        max_age=1209600,
        path="/", 
        samesite="lax",
        secure=False 
    )

# --- ВХОД (LOGIN) ---

@router.get("/login")
async def login_page(request: Request):
    """ОТОБРАЖЕНИЕ СТРАНИЦЫ ВХОДА (Исправляет 405)"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(display_name: str = Form(...), session: Session = Depends(get_session)):
    """ОБРАБОТКА ВХОДА с уведомлением"""
    name = display_name.strip()
    user = session.exec(select(User).where(User.display_name == name)).first()
    
    if not user:
        # Теперь вместо безликого ?error=1 мы шлем внятное сообщение
        res = RedirectResponse("/login", status_code=303)
        flash(res, "Семья тебя не узнала. Проверь имя или зарегистрируйся!", "error")
        return res
    
    res = RedirectResponse("/", status_code=303)
    flash(res, f"Рады видеть тебя, {user.display_name}!", "success")
    set_auth_cookie(res, int(user.id)) # type: ignore
    return res

# --- РЕГИСТРАЦИЯ (REGISTER) ---

@router.get("/register")
async def register_page(request: Request):
    """ОТОБРАЖЕНИЕ СТРАНИЦЫ РЕГИСТРАЦИИ (Исправляет 405)"""
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(display_name: str = Form(...), session: Session = Depends(get_session)):
    name = display_name.strip()
    if not name: return RedirectResponse("/register", status_code=303)

    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    
    new_user = User(
        username=unique_username,
        display_name=name,
        hashed_password=hash_password("123"),
        role="user",
        avatar_url="/static/default_avatar.png" 
    )
    
    session.add(new_user)
    session.commit() 
    session.refresh(new_user)
    
    # --- ВОТ ИСПРАВЛЕНИЕ ---
    res = RedirectResponse("/", status_code=303)
    # Выдаем куку сразу после регистрации, чтобы не логиниться второй раз
    set_auth_cookie(res, int(new_user.id)) # type: ignore
    
    flash(res, f"Добро пожаловать в семью, {name}!", "success")
    return res

# --- ВЫХОД (LOGOUT) ---

@router.get("/logout")
async def logout():
    """ПОЛНЫЙ СБРОС СЕССИИ (Лечит бесконечный редирект)"""
    res = RedirectResponse("/login", status_code=303)
    res.delete_cookie("user_session", path="/")
    return res

# --- ПРОФИЛЬ И АВАТАР ---

@router.get("/profile/{username}")
async def profile_page(request: Request, username: str, session: Session = Depends(get_session)):
    user_id = get_current_user(request)
    # Если юзер из куки не найден в базе — принудительный логаут
    if not user_id:
        res = RedirectResponse("/login", status_code=303)
        res.delete_cookie("user_session", path="/")
        return res
        
    target_user = session.exec(select(User).where(User.username == username)).first()
    if not target_user: return RedirectResponse("/", status_code=303)
    
    current_user = session.get(User, user_id)
    
    statement = select(Post).where(Post.author_id == target_user.id).options(
        selectinload(Post.author), # type: ignore
        selectinload(Post.images), # type: ignore
        selectinload(Post.comments) # type: ignore
    ).order_by(Post.created_at.desc()) # type: ignore
    
    user_posts = session.exec(statement).all()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "target_user": target_user,
        "user": current_user,
        "posts": user_posts 
    })

# ... (твои импорты без изменений)

@router.post("/update-avatar")
async def update_avatar(
    avatar: UploadFile = File(...),
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """Обновление аватарки с уведомлением об успехе"""
    user = session.get(User, user_id)
    if not user: return RedirectResponse("/logout", status_code=303)

    res = RedirectResponse(f"/profile/{user.username}", status_code=303)

    if avatar and avatar.filename:
        try:
            filename_base = uuid.uuid4().hex
            upload_path = Path(settings.AVATARS_PATH)
            upload_path.mkdir(parents=True, exist_ok=True)
            target_path = str(upload_path / f"{filename_base}.jpg")
            
            actual_saved_path = process_and_save_image(avatar.file, target_path)
            
            if actual_saved_path:
                if user.avatar_url and "default_avatar.png" not in user.avatar_url:
                    old_file_path = Path(settings.STATIC_PATH).parent / user.avatar_url.lstrip("/")
                    if old_file_path.exists():
                        os.remove(old_file_path)

                final_filename = os.path.basename(actual_saved_path)
                user.avatar_url = f"/static/uploads/avatars/{final_filename}"
                
                session.add(user)
                session.commit()
                flash(res, "Твое новое фото успешно сохранено!", "success")
                log_action(str(user_id), "AVATAR_UPDATE", f"Новый аватар: {final_filename}")
        except Exception as e:
            flash(res, "Не удалось обновить фото. Попробуй другой файл.", "error")
            print(f"❌ ОШИБКА: {e}")

    return res

@router.post("/update-name")
async def update_name(
    display_name: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user: 
        return RedirectResponse("/login", status_code=303)

    new_name = display_name.strip()
    if new_name:
        user.display_name = new_name
        session.add(user)
        session.commit()
        
        # Создаем ответ и вешаем уведомление
        res = RedirectResponse("/settings", status_code=303)
        flash(res, f"Имя успешно изменено на {new_name}!", "success")
        return res
    
    return RedirectResponse("/settings", status_code=303)