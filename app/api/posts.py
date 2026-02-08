import os
import uuid
from pathlib import Path
from typing import List, Any, cast, Optional

from fastapi import APIRouter, Request, Depends, Form, status, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Post, User, PostImage, Comment, PostLike
from app.security import get_current_user 
from app.logger import log_action, log_error
from app.utils.images import process_and_save_image
from app.config import settings
from app.utils.flash import flash, get_flashed_messages

router = APIRouter()

# Корректная настройка шаблонов (используем settings)
templates = Jinja2Templates(directory=str(Path(settings.STATIC_PATH).parent / "templates"))
templates.env.globals.update(get_flashed_messages=get_flashed_messages)

@router.get("/")
async def index(request: Request, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id: return RedirectResponse(url="/login", status_code=303)
    user = session.get(User, user_id)
    
    statement = (
        select(Post)
        .options(
            selectinload(Post.author), # type: ignore
            selectinload(Post.images), # type: ignore
            selectinload(Post.likers), # type: ignore
            selectinload(Post.comments).selectinload(Comment.author) # type: ignore
        )
        .order_by(col(Post.created_at).desc()) 
    )
    posts = session.exec(statement).all()
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "posts": posts})

@router.post("/posts/create")
async def create_post(
    content: Optional[str] = Form(None),
    is_gift: bool = Form(False),
    files: List[UploadFile] = File(default=[]), 
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Создание поста с уведомлением об успехе"""
    if not user_id: return RedirectResponse("/login", status_code=303)
    
    response = RedirectResponse(url="/", status_code=303)

    try:
        new_post = Post(
            content=content.strip() if content else None,
            author_id=user_id,
            is_gift=is_gift,
            is_opened=not is_gift 
        )
        session.add(new_post)
        session.commit()
        session.refresh(new_post)

        if new_post.id:
            upload_path = Path(settings.POSTS_PATH).resolve()
            upload_path.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                if not file.filename: continue
                filename = f"{uuid.uuid4().hex}.webp"
                target_path = upload_path / filename
                
                if process_and_save_image(cast(Any, file.file), str(target_path)):
                    web_path = f"/static/uploads/posts/{filename}"
                    img_entry = PostImage(url=web_path, post_id=int(new_post.id))
                    session.add(img_entry)
            
            session.commit()
            flash(response, "История успешно добавлена в семейную книгу!", "success")
            log_action(str(user_id), "POST_CREATE", f"Пост {new_post.id}")
            
    except Exception as e:
        log_error("POST_CREATE_ERR", str(e))
        flash(response, "Не удалось создать пост. Попробуй еще раз.", "error")

    return response

# --- ПРОСМОТР ПОСТА ---

@router.get("/posts/{post_id}")
async def get_post_detail(
    post_id: int, 
    request: Request, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """Страница отдельного поста с комментариями"""
    if not user_id: 
        return RedirectResponse(url="/login", status_code=303)
    
    # Загружаем пост со всеми связями через selectinload
    statement = (
        select(Post)
        .where(Post.id == post_id)
        .options(
            selectinload(Post.author), # type: ignore
            selectinload(Post.images), # type: ignore
            selectinload(Post.comments).selectinload(Comment.author), # type: ignore
            selectinload(Post.likers) # type: ignore
        )
    )
    post = session.exec(statement).first()
    
    if not post:
        print(f"⚠️ ПОСТ {post_id} НЕ НАЙДЕН")
        return RedirectResponse(url="/", status_code=303)
    
    user = session.get(User, user_id)
    
    # Убедись, что файл post_detail.html существует в templates/
    return templates.TemplateResponse("post_detail.html", {
        "request": request, 
        "user": user, 
        "post": post
    })

# --- ДОБАВЛЕНИЕ КОММЕНТАРИЯ ---

@router.post("/posts/{post_id}/comment")
async def create_comment(
    post_id: int,
    content: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Добавление комментария с уведомлением"""
    response = RedirectResponse(url=f"/posts/{post_id}", status_code=303)
    
    if not content.strip():
        flash(response, "Нельзя оставить пустой комментарий", "info")
        return response

    try:
        new_comment = Comment(
            content=content.strip(),
            post_id=post_id,
            author_id=user_id
        )
        session.add(new_comment)
        session.commit()
        flash(response, "Комментарий добавлен", "success")
    except Exception as e:
        flash(response, "Ошибка при добавлении комментария", "error")

    return response

# --- ЛАЙК (AJAX или редирект) ---

@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: int, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """Поставить или убрать лайк"""
    if not user_id: return RedirectResponse("/login", status_code=303)
    
    # Ищем, лайкал ли уже этот юзер этот пост
    existing = session.exec(
        select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
    ).first()
    
    if existing:
        session.delete(existing)
    else:
        session.add(PostLike(user_id=user_id, post_id=post_id))
        
    session.commit()
    # Возвращаемся на ту же страницу, откуда пришли
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

@router.post("/posts/delete/{post_id}")
async def delete_post(
    post_id: int, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """Удаление поста и очистка .webp файлов с уведомлением"""
    statement = select(Post).where(Post.id == post_id).options(selectinload(Post.images)) # type: ignore
    post = session.exec(statement).first()
    
    # Готовим ответ заранее, чтобы передать его во flash
    response = RedirectResponse("/", status_code=303)

    if not post:
        flash(response, "Пост уже удален или не существует", "error")
        return response

    if post.author_id != user_id:
        flash(response, "У тебя нет прав для удаления этого поста!", "error")
        return response

    # 1. Удаление файлов
    for img in post.images:
        filename = os.path.basename(img.url)
        file_path = Path(settings.POSTS_PATH) / filename
        if file_path.exists():
            os.remove(file_path)
            print(f"--- 🗑️ Удален файл: {file_path} ---")

    # 2. Удаление из БД
    for img in post.images:
        session.delete(img)
    
    session.delete(post)
    session.commit()
    
    log_action(str(user_id), "POST_DELETE", f"Пост {post_id} стерт")
    
    # 3. Добавляем уведомление об успехе
    flash(response, "Пост и все связанные фотографии успешно удалены", "success")
    
    return response