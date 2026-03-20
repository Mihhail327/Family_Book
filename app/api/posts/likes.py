from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from pydantic import BaseModel

from app.database import get_session
from app.models import PostLike, User
from app.security import get_current_user

router = APIRouter()

# Схема для парсинга входящего JSON от фронтенда
class ReactionRequest(BaseModel):
    reaction: str = "❤️"

@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: int, 
    payload: ReactionRequest, # 🟢 Ловим JSON из тела запроса
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    # Раз это фоновый JS-запрос, отдаем 401 ошибку вместо редиректа
    if not user_id: 
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться")
    
    existing = session.exec(
        select(PostLike).where(PostLike.user_id == user_id, PostLike.post_id == post_id)
    ).first()
    
    if existing:
        if existing.reaction_type == payload.reaction:
            # Юзер кликнул на тот же эмодзи -> удаляем лайк
            session.delete(existing)
            action = "unliked"
        else:
            # Юзер выбрал другой эмодзи -> обновляем
            existing.reaction_type = payload.reaction
            session.add(existing)
            action = "updated"
    else:
        # Новая реакция
        new_like = PostLike(user_id=user_id, post_id=post_id, reaction_type=payload.reaction)
        session.add(new_like)
        action = "liked"
        
    session.commit()
    
    # Считаем актуальное количество реакций для этого поста
    likes_count = session.exec(
        select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
    ).one()
    
    # Возвращаем JSON, чтобы app.js мог мгновенно обновить UI
    return {
        "status": action, 
        "likes_count": likes_count
    }

@router.get("/api/posts/{post_id}/likers")
async def get_post_likers_api(post_id: int, session: Session = Depends(get_session)):
    statement = (
        select(User.display_name, User.avatar_url)
        .join(PostLike)
        .where(PostLike.post_id == post_id)
    )
    results = session.exec(statement).all()
    
    return [
        {
            "display_name": res.display_name, # type: ignore
            "avatar_url": res.avatar_url or "/static/default_avatar.png" # type: ignore
        } 
        for res in results
    ]