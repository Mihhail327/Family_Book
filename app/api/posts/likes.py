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
    payload: ReactionRequest, 
    user_id: int = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    if not user_id: 
        raise HTTPException(status_code=401, detail="Необходимо авторизоваться")
    
    # 1. Ищем существующую запись
    statement = select(PostLike).where(
        PostLike.user_id == user_id, 
        PostLike.post_id == post_id
    )
    existing = session.exec(statement).first()
    
    action = "liked"
    
    if existing:
        if existing.reaction_type == payload.reaction:
            # Если кликнули по той же реакции — удаляем (дизлайк)
            session.delete(existing)
            action = "unliked"
        else:
            # Если кликнули по другой реакции — обновляем тип
            existing.reaction_type = payload.reaction
            session.add(existing)
            action = "updated"
    else:
        # Создаем новый лайк
        new_like = PostLike(
            user_id=user_id, 
            post_id=post_id, 
            reaction_type=payload.reaction
        )
        session.add(new_like)

    session.commit()

    # 2. Считаем количество СВЕЖИМ запросом
    likes_count = session.exec(
        select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
    ).one()
    
    return {
        "status": action, 
        "likes_count": likes_count,
        "reaction": payload.reaction if action != "unliked" else "❤️"
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