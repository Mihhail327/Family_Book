import os
import uuid
from pathlib import Path
from typing import List, Any, cast, Optional

from fastapi import APIRouter, Request, Depends, Form, status, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.database import get_session
from app.models import Post, User, PostImage, Comment, PostLike
from app.security import get_current_user 
from app.logger import log_action, log_error
from app.utils.images import process_and_save_image
from app.config import settings
from app.utils.flash import flash, get_flashed_messages

router = APIRouter()

# Инициализация шаблонов: ищем папку templates на уровень выше папки static
templates = Jinja2Templates(directory=str(Path(settings.STATIC_PATH).parent / "templates"))
# Добавляем функцию flash-сообщений в глобальный контекст шаблонов Jinja2
templates.env.globals.update(get_flashed_messages=get_flashed_messages)

@router.get("/")
async def index(request: Request, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    """ ГЛАВНАЯ СТРАНИЦА: Список всех постов семьи """
    if not user_id: return RedirectResponse(url="/login", status_code=303)
    
    user = session.get(User, user_id)
    
    # Загружаем посты с предварительной подгрузкой всех связанных данных (Eager Loading)
    # Это предотвращает сотни мелких запросов к базе при рендеринге каждого поста
    statement = (
        select(Post)
        .options(
            selectinload(Post.author),    # type: ignore
            selectinload(Post.images),     # type: ignore
            selectinload(Post.likers),     # type: ignore
            selectinload(Post.comments).selectinload(Comment.author) # type: ignore
        )
        .order_by(col(Post.created_at).desc()) # Новые посты всегда сверху
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
    """ СОЗДАНИЕ ПОСТА: Обработка текста и загрузка нескольких изображений """
    if not user_id: return RedirectResponse("/login", status_code=303)
    response = RedirectResponse(url="/", status_code=303)

    try:
        # Получаем время ПРЯМО В МОМЕНТ создания поста
        current_time = datetime.now(timezone.utc)

        # 1. Создаем запись самого поста
        new_post = Post(
            content=content.strip() if content else None,
            author_id=user_id,
            is_gift=is_gift,
            is_opened=not is_gift, # Если не "подарок", то пост сразу открыт
            created_at=current_time
        )
        session.add(new_post)
        session.flush()   # flush() позволяет получить ID поста, не закрывая транзакцию
        session.refresh(new_post)

        # 2. Обработка изображений, если они есть
        if new_post.id:
            upload_path = Path(settings.POSTS_PATH).resolve()
            upload_path.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                if not file.filename: continue
                
                # Генерируем уникальное имя для файла во избежание конфликтов
                filename = f"{uuid.uuid4().hex}.webp"
                target_path = upload_path / filename
                
                # Оптимизируем и сохраняем изображение на диск
                if process_and_save_image(cast(Any, file.file), str(target_path)):
                    # Сохраняем путь к картинке в базе данных
                    web_path = f"/static/uploads/posts/{filename}"
                    img_entry = PostImage(url=web_path, post_id=int(new_post.id))
                    session.add(img_entry)
            
            session.commit() # Фиксируем все изменения в базе одним махом
            flash(response, "История успешно добавлена в семейную книгу!", "success")
            log_action(str(user_id), "POST_CREATE", f"Пост {new_post.id}")
            
    except Exception as e:
        session.rollback() # Если что-то пошло не так, отменяем все изменения в БД
        log_error("POST_CREATE_ERR", str(e))
        flash(response, "Не удалось создать пост. Попробуй еще раз.", "error")

    return response

@router.get("/posts/{post_id}")
async def get_post_detail(
    post_id: int, 
    request: Request, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """ ДЕТАЛЬНАЯ СТРАНИЦА ПОСТА: Просмотр одного события """
    if not user_id: return RedirectResponse(url="/login", status_code=303)
    
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
    if not user: return RedirectResponse("/login", status_code=303)
    
    # Флаг прав доступа: редактировать/удалять может автор ИЛИ админ
    can_edit = (post.author_id == user.id) or (user.role == "admin")

    return templates.TemplateResponse("post_detail.html", {
        "request": request, 
        "user": user, 
        "post": post,
        "can_edit": can_edit 
    })

@router.post("/posts/{post_id}/comment")
async def create_comment(
    post_id: int,
    content: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """ КОММЕНТИРОВАНИЕ: Добавление мнения под пост """
    response = RedirectResponse(url=f"/posts/{post_id}", status_code=303)
    
    if not content.strip():
        flash(response, "Нельзя оставить пустой комментарий", "info")
        return response

    try:
        new_comment = Comment(
            content=content.strip(),
            post_id=post_id,
            author_id=user_id,
            created_at=datetime.now(timezone.utc)
        )
        session.add(new_comment)
        session.commit()
        flash(response, "Комментарий добавлен", "success")
    except Exception as e:
        log_error("COMMENT_ERR", str(e))
        flash(response, "Ошибка при добавлении комментария", "error")

    return response

@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: int, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """ ЛАЙК: Переключатель (поставил/убрал) """
    if not user_id: return RedirectResponse("/login", status_code=303)
    
    # Проверяем наличие существующего лайка от этого пользователя
    existing = session.exec(
        select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
    ).first()
    
    if existing:
        # Если лайк уже есть — удаляем его (дизлайк)
        session.delete(existing)
    else:
        # Если лайка нет — создаем новую запись
        session.add(PostLike(user_id=user_id, post_id=post_id))
        
    session.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

@router.get("/api/posts/{post_id}/likers")
async def get_post_likers_api(
    post_id: int, 
    session: Session = Depends(get_session)
):
    """Отдает список лайкнувших в формате JSON для модального окна"""
    statement = select(Post).where(Post.id == post_id).options(selectinload(Post.likers)) # type: ignore
    post = session.exec(statement).first()
    
    if not post:
        return []
    
    # Возвращаем только нужные поля, чтобы не светить паролями или email
    return [
        {
            "display_name": user.display_name,
            "avatar_url": user.avatar_url or "/static/default_avatar.png"
        } 
        for user in post.likers
    ]

@router.post("/posts/delete/{post_id}")
async def delete_post(
    post_id: int, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    """ УДАЛЕНИЕ ПОСТА: Очистка диска от картинок и удаление из БД """
    statement = select(Post).where(Post.id == post_id).options(selectinload(Post.images)) # type: ignore
    post = session.exec(statement).first()
    user = session.get(User, user_id)
    
    response = RedirectResponse("/", status_code=303)

    if not post or not user:
        flash(response, "Пост уже удален или не существует", "error")
        return response

    # Проверка прав (только автор или админ могут стирать истории)
    if post.author_id != user_id and user.role != "admin":
        flash(response, "У тебя нет прав для удаления этого поста!", "error")
        return response

    # 1. Сначала физически удаляем файлы с сервера, чтобы не копить мусор
    for img in post.images:
        filename = os.path.basename(img.url)
        file_path = Path(settings.POSTS_PATH).resolve() / filename
        if file_path.exists():
            try:
                os.remove(file_path)
                print(f"--- 🗑️ Удален файл: {file_path} ---")
            except Exception as e:
                log_error("FILE_DEL_ERR", f"Не удалось удалить {filename}: {e}")

    # 2. Удаляем запись из базы (все связанные лайки и картинки удалятся по цепочке)
    session.delete(post)
    session.commit()
    
    log_action(str(user_id), "POST_DELETE", f"Пост {post_id} стерт")
    flash(response, "Пост и все фотографии успешно удалены", "success")
    
    return response