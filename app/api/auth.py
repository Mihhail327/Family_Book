import os
import uuid
from pathlib import Path
from typing import Optional

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

templates = Jinja2Templates(directory=str(Path(settings.STATIC_PATH).parent / "templates"))
templates.env.globals.update(get_flashed_messages=get_flashed_messages)

def set_auth_cookie(response: RedirectResponse, user_id: int):
    token = create_session_token(user_id)
    # Автоматически определяем, нужен ли Secure (для Render = True)
    is_production = settings.ENVIRONMENT == "production"
    
    response.set_cookie(
        key="user_session", 
        value=token, 
        httponly=True, 
        max_age=1209600, # 14 дней
        path="/", 
        samesite="lax",
        secure=is_production 
    )

# --- ВХОД ---

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(display_name: str = Form(...), session: Session = Depends(get_session)):
    name = display_name.strip()
    # Ищем пользователя по имени
    user = session.exec(select(User).where(User.display_name == name)).first()
    
    if not user:
        res = RedirectResponse("/login", status_code=303)
        flash(res, "Семья тебя не узнала. Проверь имя или зарегистрируйся!", "error")
        return res
    
    res = RedirectResponse("/", status_code=303)
    flash(res, f"Рады видеть тебя, {user.display_name}!", "success")
    
    # Pylance может ругаться на int(None), но мы знаем, что id есть
    if user.id:
        set_auth_cookie(res, int(user.id)) 
        
    return res

# --- РЕГИСТРАЦИЯ ---

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(display_name: str = Form(...), session: Session = Depends(get_session)):
    name = display_name.strip()
    res_error = RedirectResponse("/register", status_code=303)

    # 1. Валидация длины
    if len(name) < 2:
        flash(res_error, "Имя слишком короткое (минимум 2 буквы)", "error")
        return res_error
    if len(name) > 20:
        flash(res_error, "Имя слишком длинное (максимум 20 букв)", "error")
        return res_error

    # 2. Проверка уникальности
    existing_user = session.exec(select(User).where(User.display_name == name)).first()
    if existing_user:
        flash(res_error, f"Имя '{name}' уже занято. Добавь первую букву фамилии!", "error")
        return res_error

    # Создание пользователя
    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    
    # Пароль берем из настроек или ставим "123"
    default_pwd = getattr(settings, "DEFAULT_USER_PASSWORD", "123")
    
    new_user = User(
        username=unique_username,
        display_name=name,
        hashed_password=hash_password(default_pwd),
        role="user",
        avatar_url="/static/default_avatar.png" 
    )
    
    session.add(new_user)
    session.commit() 
    session.refresh(new_user)
    
    res = RedirectResponse("/", status_code=303)
    if new_user.id:
        set_auth_cookie(res, int(new_user.id))
    
    flash(res, f"Добро пожаловать в семью, {name}!", "success")
    return res

# --- ВЫХОД ---

@router.get("/logout")
async def logout():
    res = RedirectResponse("/login", status_code=303)
    res.delete_cookie("user_session", path="/")
    return res

# --- ПРОФИЛЬ ---

@router.get("/profile/{username}")
async def profile_page(request: Request, username: str, session: Session = Depends(get_session)):
    user_id = get_current_user(request)
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

# --- ОБНОВЛЕНИЕ АВАТАРА ---

@router.post("/update-avatar")
async def update_avatar(
    avatar: UploadFile = File(...),
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user: return RedirectResponse("/logout", status_code=303)

    res = RedirectResponse(f"/profile/{user.username}", status_code=303)

    if avatar and avatar.filename:
        try:
            filename_base = uuid.uuid4().hex
            upload_path = Path(settings.AVATARS_PATH)
            upload_path.mkdir(parents=True, exist_ok=True)
            
            target_path = str(upload_path / f"{filename_base}.webp")
            
            actual_saved_path = process_and_save_image(avatar.file, target_path)
            
            if actual_saved_path:
                if user.avatar_url and "default_avatar.png" not in user.avatar_url:
                    old_filename = os.path.basename(user.avatar_url)
                    old_file_path = upload_path / old_filename
                    if old_file_path.exists():
                        os.remove(old_file_path)

                final_filename = os.path.basename(actual_saved_path)
                user.avatar_url = f"/static/uploads/avatars/{final_filename}"
                
                session.add(user)
                session.commit()
                flash(res, "Твое новое фото успешно сохранено!", "success")
                log_action(str(user_id), "AVATAR_UPDATE", f"Новый аватар: {final_filename}")
            else:
                flash(res, "Ошибка обработки изображения. Попробуй другой файл.", "error")
                
        except Exception as e:
            flash(res, "Не удалось обновить фото.", "error")
            print(f"❌ ОШИБКА АВАТАРА: {e}")

    return res

# --- ОБНОВЛЕНИЕ ИМЕНИ ---

@router.post("/update-name")
async def update_name(
    display_name: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    
    # 1. СНАЧАЛА проверяем существование пользователя
    if not user: 
        return RedirectResponse("/login", status_code=303)

    # 2. И только потом обращаемся к его полям
    redirect_url = f"/profile/{user.username}"
    
    new_name = display_name.strip()
    res = RedirectResponse(redirect_url, status_code=303)

    # Валидация
    if len(new_name) < 2 or len(new_name) > 20:
        flash(res, "Некорректная длина имени", "error")
        return res

    # Проверка на занятость
    existing = session.exec(select(User).where(User.display_name == new_name)).first()
    if existing and existing.id != user.id:
        flash(res, "Это имя уже занято другим членом семьи", "error")
        return res

    if new_name:
        user.display_name = new_name
        session.add(user)
        session.commit()
        flash(res, f"Имя успешно изменено на {new_name}!", "success")
    
    return res