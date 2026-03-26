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
from app.models import Post, PostLike, User, PostImage, Comment
# ДОБАВЛЕНО: validate_security_input для защиты от XSS
from app.security import get_current_user, validate_security_input 
from app.logger import log_action, log_error
from app.utils.images import process_and_save_image
from app.config import settings
from app.utils.flash import flash
from app.core.templates import templates
from app.services.notifier import bot_alert

router = APIRouter()

@router.get("/")
async def index(request: Request, user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id: 
        return RedirectResponse(url="/auth/login", status_code=303)

    user = session.get(User, user_id)
    if not user:
        response = RedirectResponse(url="/auth/login", status_code=303)
        response.delete_cookie("user_session")
        return response

    try:
        # 1. Формируем базовый запрос
        statement = (
            select(Post)
            .options(
                selectinload(Post.author), # type: ignore
                selectinload(Post.images), # type: ignore
                selectinload(Post.comments).selectinload(Comment.author), # type: ignore
                selectinload(Post.likers)  # type: ignore
            )
        )

        # 2. Магия изоляции
        # Добавляем # type: ignore, чтобы Pylance не ругался на "bool" в onclause
        statement = statement.join(User, Post.author_id == User.id) # type: ignore

        if user.is_guest:
            # Добавляем # noqa: E712, чтобы Ruff не просил убрать "== True"
            statement = statement.where(User.is_guest == True) # noqa: E712
        else:
            # Добавляем # noqa: E712, чтобы Ruff не просил использовать "not"
            statement = statement.where(User.is_guest == False) # noqa: E712

        statement = statement.order_by(col(Post.created_at).desc())
        posts = session.exec(statement).all()

        # --- 🟢 НОВЫЙ БЛОК: ПОДТЯГИВАЕМ ТВОИ ЛАЙКИ ---
        # --- 🕵️‍♂️ ДЕТЕКТИВНЫЙ БЛОК ЛАЙКОВ ---
        # 1. Четко определяем, кто зашел (приводим к int)
        try:
            current_uid = int(user_id)
        except (ValueError, TypeError):
            current_uid = 0
            
        post_ids = [p.id for p in posts if p.id is not None]
        
        # 2. Берем ИЗ БАЗЫ все лайки этого юзера для этих постов
        user_likes_in_db = session.exec(
            select(PostLike).where(
                PostLike.post_id.in_(post_ids), # type: ignore
                PostLike.user_id == current_uid
            )
        ).all()

        # 3. Создаем карту {post_id: reaction_type}
        # ВАЖНО: Приводим l.post_id к int для гарантии совпадения
        likes_map = {int(l.post_id): l.reaction_type for l in user_likes_in_db}  # noqa: E741

        print(f"--- СТАТИСТИКА ДЛЯ ЮЗЕРА ID: {current_uid} ---")
        print(f"Найдено лайков в базе: {len(user_likes_in_db)}")
        print(f"Карта лайков (ID поста: Эмодзи): {likes_map}")

        for p in posts:
            p_id = int(p.id) if p.id else 0
            # Записываем напрямую в __dict__
            p.__dict__["is_user_liked"] = p_id in likes_map # type: ignore
            p.__dict__["user_reaction"] = likes_map.get(p_id, "❤️") # type: ignore
            
            if p_id in likes_map:
                print(f"✅ Пост {p_id}: ЛАЙКНУТ (Emoji: {likes_map[p_id]})")
        print("---------------------------------------")

        return templates.TemplateResponse(
            request=request, 
            name="index.html", 
            context={"user": user, "posts": posts}
        )
    except Exception as e:
        log_error("INDEX_LOAD_ERR", str(e))
        raise e

@router.post("/posts/create")
async def create_post(
    request: Request,
    content: Optional[str] = Form(None),
    is_gift: bool = Form(False),
    files: List[UploadFile] = File(default=[]), 
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id: 
        return RedirectResponse("/auth/login", status_code=303)
        
    user = session.get(User, user_id)
    valid_files = [f for f in files if f.filename and f.filename.strip() != ""]
    
    if not content and not valid_files:
        response = RedirectResponse(url="/", status_code=303)
        flash(response, "Добавь хотя бы пару слов или фото! ✨", "info")
        return response

    # --- ПРОВЕРКА ЛИМИТА ФАЙЛОВ ---
    if len(valid_files) > 10:
        response = RedirectResponse(url="/", status_code=303)
        flash(response, "Максимум 10 фотографий! Мы же не архив NASA 🚀", "error")
        return response

    # --- БЛОК БЕЗОПАСНОСТИ ---
    safe_content = None
    if content:
        clean_text = content.strip()
        if len(clean_text) > 2000:
            response = RedirectResponse(url="/", status_code=303)
            flash(response, "История слишком длинная (максимум 2000 символов)", "error")
            return response
        try:
            safe_content = validate_security_input(clean_text)
        except Exception as e:
            response = RedirectResponse(url="/", status_code=303)
            flash(response, str(e), "error")
            return response

    try:
        new_post = Post(
            content=safe_content, author_id=user_id, is_gift=is_gift,
            is_opened=not is_gift, created_at=datetime.now(timezone.utc)
        )
        session.add(new_post); session.flush()  # noqa: E702
        
        if new_post.id is None:
            raise Exception("Не удалось получить ID поста")

        upload_path = Path(settings.POSTS_PATH).resolve()
        upload_path.mkdir(parents=True, exist_ok=True)
        
        for index, file in enumerate(files):
            if not file.filename or file.filename == "": 
                continue
            
            filename = f"{uuid.uuid4().hex}.webp"
            target_path = upload_path / filename
            
            if process_and_save_image(cast(Any, file.file), str(target_path)):
                img_entry = PostImage(
                    url=f"/static/uploads/posts/{filename}", 
                    post_id=new_post.id,
                    position=index
                )
                session.add(img_entry)
        
        session.commit() 
        log_action(str(user_id), "POST_CREATE", f"ID: {new_post.id}")

        # ПОДГОТОВКА ПОЛНОГО ПОСТА ДЛЯ ОТВЕТА
        statement = select(Post).where(Post.id == new_post.id).options(
            selectinload(Post.author), selectinload(Post.images),  # type: ignore
            selectinload(Post.likers), selectinload(Post.comments) # type: ignore
        )
        full_post = session.exec(statement).first()
        if full_post:
            full_post.__dict__.update({"user_reaction": None, "is_user_liked": False}) # type: ignore

        # 🟢 МАГИЯ ГИБКОСТИ: Если это HTMX или Тесты — отдаем 200 OK
        if request.headers.get("hx-request") == "true" or settings.ENV == "testing":
            return templates.TemplateResponse(
                request=request, name="includes/post_card.html",
                context={"post": full_post, "user": user}
            )
        
        # Для обычных форм делаем редирект
        res = RedirectResponse(url="/", status_code=303)
        flash(res, "История успешно добавлена! ✨", "success")
        return res
            
    except Exception as e:
        session.rollback()
        log_error("POST_CREATE_ERR", str(e))
        res = RedirectResponse(url="/", status_code=303)
        flash(res, "Ошибка при сохранении истории", "error")
        return res

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
    
    # 🟢 ЗАЩИТА ОТ ПОДСМАТРИВАНИЯ
    if user.is_guest and not post.author.is_guest: # type: ignore
        response = RedirectResponse(url="/", status_code=303)
        flash(response, "У вас нет доступа к этой части семейного архива", "error")
        return response
    
    can_edit = (post.author_id == user.id) or getattr(user, "role", "") == "admin"
    return templates.TemplateResponse(
    request=request, 
    name="post_detail.html", 
    context={"user": user, "post": post, "can_edit": can_edit}
)

@router.post("/posts/delete/{post_id}")
async def delete_post(
    post_id: int, request: Request, 
    user_id: int = Depends(get_current_user), session: Session = Depends(get_session)
):
    if not user_id: return RedirectResponse(url="/login", status_code=303)  # noqa: E701
        
    post = session.get(Post, post_id)
    user = session.get(User, user_id)
    res = RedirectResponse("/", status_code=303)

    if not post or not user:
        flash(res, "История не найдена", "error")
        return res

    # 🛡️ SENTINEL ACTIVATION
    is_admin = getattr(user, "role", "") == "admin"
    if post.author_id != user_id and not is_admin:
        log_error("SENTINEL_VIOLATION", f"User {user_id} tried to DELETE post {post_id}")
        
        # ✅ ТЕПЕРЬ ШЛЕМ АЛЕРТ В ТЕЛЕГУ
        if settings.ENV != "testing":
            await bot_alert.send_alert(
                f"⛔ **SECURITY ALERT**\nПопытка удаления чужого поста!\nЮзер: {user.display_name}\nID Поста: {post_id}\nIP: {request.client.host}",  # type: ignore
                level="SECURITY"
            )
        
        flash(res, "У тебя нет прав для удаления этой истории!", "error")
        return res

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
    flash(res, "Пост удален навсегда 🗑️", "success")
    return res

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