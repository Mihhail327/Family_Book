import os
import uuid
from pathlib import Path
from typing import List, Any, cast, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse

from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Post, User, PostImage, Comment
# ДОБАВЛЕНО: validate_security_input для защиты от XSS
from app.security import get_current_user, validate_security_input 
from app.logger import log_action, log_error
from app.utils.images import process_and_save_image
from app.config import settings
from app.utils.flash import flash
from app.core.templates import templates

router = APIRouter()

@router.get("/")
async def index(request: Request, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id: 
        return RedirectResponse(url="/auth/login", status_code=303)
    user = session.get(User, user_id)
    
    user = session.get(User, user_id)
    
    # Если юзер в куках есть, а в новой базе его нет (базу-то мы удалили!)
    if not user:
        response = RedirectResponse(url="/auth/login", status_code=303)
        response.delete_cookie("user_session") # Чистим битую сессию
        return response

    statement = (
        select(Post)
        .options(
            selectinload(Post.author),     # type: ignore
            selectinload(Post.images),     # type: ignore
            selectinload(Post.likers),     # type: ignore
            selectinload(Post.comments).selectinload(Comment.author) # type: ignore
        )
        .order_by(col(Post.created_at).desc())
    )
    posts = session.exec(statement).all()
    return templates.TemplateResponse(
    request=request, 
    name="index.html", 
    context={"user": user, "posts": posts}
)

@router.post("/posts/create")
async def create_post(
    content: Optional[str] = Form(None),
    is_gift: bool = Form(False),
    files: List[UploadFile] = File(default=[]), 
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id: 
        return RedirectResponse("/auth/login", status_code=303)
    response = RedirectResponse(url="/", status_code=303)

    # --- БЛОК БЕЗОПАСНОСТИ (Triple-S Rebuild) ---
    safe_content = None
    if content:
        clean_text = content.strip()
        if len(clean_text) > 2000:
            flash(response, "История слишком длинная (максимум 2000 символов)", "error")
            return response
        try:
            safe_content = validate_security_input(clean_text)
        except Exception as e:
            flash(response, str(e), "error")
            return response
    # ---------------------------------------------

    try:
        new_post = Post(
            content=safe_content,
            author_id=user_id,
            is_gift=is_gift,
            is_opened=not is_gift,
            created_at=datetime.now(timezone.utc)
        )
        session.add(new_post)
        session.flush() 
        session.refresh(new_post)

        if new_post.id:
            upload_path = Path(settings.POSTS_PATH).resolve()
            upload_path.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                if not file.filename: 
                    continue
                filename = f"{uuid.uuid4().hex}.webp"
                target_path = upload_path / filename
                
                if process_and_save_image(cast(Any, file.file), str(target_path)):
                    img_entry = PostImage(url=f"/static/uploads/posts/{filename}", post_id=int(new_post.id))
                    session.add(img_entry)
            
            session.commit()
            flash(response, "История успешно добавлена в семейную книгу!", "success")
            log_action(str(user_id), "POST_CREATE", f"Пост {new_post.id}")
            
    except Exception as e:
        session.rollback()
        log_error("POST_CREATE_ERR", str(e))
        flash(response, "Не удалось создать пост. Попробуй еще раз.", "error")

    return response

@router.get("/posts/{post_id}")
async def get_post_detail(post_id: int, request: Request, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id: 
        return RedirectResponse(url="/auth/login", status_code=303)
    
    statement = select(Post).where(Post.id == post_id).options(
        selectinload(Post.author), # type: ignore
        selectinload(Post.images), # type: ignore
        selectinload(Post.comments).selectinload(Comment.author), # type: ignore
        selectinload(Post.likers) # type: ignore
    )
    post = session.exec(statement).first()
    if not post: 
        return RedirectResponse(url="/", status_code=303)
    
    user = session.get(User, user_id)
    if not user: 
        return RedirectResponse(url="/auth/login", status_code=303)
    
    can_edit = (post.author_id == user.id) or getattr(user, "role", "") == "admin"
    return templates.TemplateResponse(
    request=request, 
    name="post_detail.html", 
    context={"user": user, "post": post, "can_edit": can_edit}
)

@router.post("/posts/delete/{post_id}")
async def delete_post(post_id: int, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    statement = select(Post).where(Post.id == post_id).options(selectinload(Post.images)) # type: ignore
    post = session.exec(statement).first()
    user = session.get(User, user_id)
    response = RedirectResponse("/", status_code=303)

    if not post or not user:
        flash(response, "Пост уже удален или не существует", "error")
        return response

    if post.author_id != user_id and getattr(user, "role", "") != "admin":
        flash(response, "У тебя нет прав для удаления этого поста!", "error")
        return response

    for img in post.images:
        filename = os.path.basename(img.url)
        file_path = Path(settings.POSTS_PATH).resolve() / filename
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                log_error("FILE_DEL_ERR", f"Не удалось удалить {filename}: {e}")

    session.delete(post)
    session.commit()
    log_action(str(user_id), "POST_DELETE", f"Пост {post_id} стерт")
    flash(response, "Пост и все фотографии успешно удалены", "success")
    return response

@router.post("/posts/edit/{post_id}")
async def edit_post(
    request: Request, # Добавили request для работы flash
    post_id: int, 
    content: str = Form(...), 
    user_id: int = Depends(get_current_user), # Используем user_id как в других роутерах
    session: Session = Depends(get_session)
):
    # 1. Ищем пост и пользователя
    post = session.get(Post, post_id)
    user = session.get(User, user_id)
    response = RedirectResponse(url="/", status_code=303)

    if not post or not user:
        flash(response, "История потерялась в архивах", "error")
        return response

    # 2. Проверка прав: автор или админ
    if post.author_id != user_id and getattr(user, "role", "") != "admin":
        flash(response, "Это не ваша история, чтобы её менять", "error")
        return response

    # 3. БОНУС: Твоя Triple-S защита для контента
    clean_text = content.strip()
    if len(clean_text) > 2000:
        flash(response, "Слишком много слов (максимум 2000)", "error")
        return response
    
    try:
        # Прогоняем через твой валидатор безопасности
        safe_content = validate_security_input(clean_text)
        
        # 4. Обновляем данные
        post.content = safe_content
        # post.updated_at = datetime.now(timezone.utc) # Если добавишь это поле в модель
        
        session.add(post)
        session.commit()
        
        flash(response, "История успешно обновлена! ✨", "success")
        log_action(str(user_id), "POST_EDIT", f"Пост {post_id} изменен")
        
    except Exception as e:
        session.rollback()
        log_error("POST_EDIT_ERR", str(e))
        flash(response, "Не удалось сохранить правки", "error")

    return response