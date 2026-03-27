import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, File, UploadFile
from fastapi.responses import RedirectResponse

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.core.templates import templates
from app.models import User, Post
from app.database import get_session
from app.security import get_current_user
from app.utils.images import process_and_save_image
from app.config import settings
from app.logger import log_action
from app.utils.flash import flash

router = APIRouter()


@router.get("/profile/{username}")
async def profile_page(request: Request, username: str, session: Session = Depends(get_session)):
    user_id = get_current_user(request)
    if not user_id:
        res = RedirectResponse("/auth/login", status_code=303)
        res.delete_cookie("user_session", path="/")
        return res
        
    target_user = session.exec(select(User).where(User.username == username)).first()
    if not target_user: 
        return RedirectResponse("/", status_code=303)
    
    current_user = session.get(User, user_id)
    
    statement = select(Post).where(Post.author_id == target_user.id).options(
        selectinload(Post.author), # type: ignore
        selectinload(Post.images), # type: ignore
        selectinload(Post.comments) # type: ignore
    ).order_by(Post.created_at.desc()) # type: ignore
    
    user_posts = session.exec(statement).all()
    
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "target_user": target_user,
            "user": current_user,
            "posts": user_posts 
        }
    )

@router.post("/update-avatar")
async def update_avatar(
    avatar: UploadFile = File(...),
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user: 
        return RedirectResponse("/auth/logout", status_code=303)

    res = RedirectResponse(f"/auth/profile/{user.username}", status_code=303)

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

@router.post("/update-name")
async def update_name(
    display_name: str = Form(...),
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user: 
        return RedirectResponse("/auth/login", status_code=303)

    redirect_url = f"/auth/profile/{user.username}"
    new_name = display_name.strip()
    res = RedirectResponse(redirect_url, status_code=303)

    if len(new_name) < 2 or len(new_name) > 25:
        flash(res, "Некорректная длина имени", "error")
        return res

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