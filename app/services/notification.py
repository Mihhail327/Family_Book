from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select, col
from app.database import get_session
from app.security import get_current_user
from app.models import Notification, User, PushSubscription
from typing import Optional
from app.services.notifier import manager 
from app.config import settings

router = APIRouter(prefix="/push", tags=["Push Notifications"])

async def create_system_notification(
    session: Session,
    title: str,
    message: str,
    user_id: Optional[int] = None,
    category: str = "info",
    link: Optional[str] = None,
    is_broadcast: bool = False
):
    try:
        # --- 1. ЗАПИСЬ В БАЗУ ---
        if user_id:
            new_note = Notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                link=link
            )
            session.add(new_note)
        else:
            # Массовая рассылка (всем кроме гостей)
            statement = select(User.id).where(col(User.is_guest) == False)  # noqa: E712
            user_ids = session.exec(statement).all()
            for uid in user_ids:
                session.add(Notification(
                    user_id=uid, # type: ignore
                    title=title,
                    message=message,
                    category=category,
                    link=link
                ))
        
        session.commit()

        # --- 2. ЖИВОЕ УВЕДОМЛЕНИЕ (WebSocket) ---
        payload = {
            "title": title,
            "message": message,
            "category": category,
            "link": link,
            "type": "new_broadcast" # Добавляем тип, чтобы JS в base.html поймал событие
        }
        
        if user_id:
            await manager.broadcast(payload, user_id=user_id) # type: ignore
        else:
            await manager.broadcast(payload)

    except Exception as e:
        session.rollback()
        print(f"❌ Notification Error: {e}")

# Схема того, что пришлет браузер
class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: SubscriptionKeys

@router.get("/public-key")
async def get_public_key():
    """Отдаем публичный ключ фронтенду, чтобы он мог подписаться"""
    return {"publicKey": settings.VAPID_PUBLIC_KEY}   # type: ignore
@router.post("/subscribe")
async def subscribe_user(
    sub_data: PushSubscriptionCreate,
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Сохраняем токен телефона пользователя в базу"""
    if not user_id:
        return {"status": "error", "detail": "Не авторизован"}

    # Проверяем, нет ли уже такой подписки (чтобы не плодить дубли)
    existing = session.exec(
        select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == sub_data.endpoint
        )
    ).first()

    if existing:
        return {"status": "success", "detail": "Уже подписан"}

    new_sub = PushSubscription(
        user_id=user_id,
        endpoint=sub_data.endpoint,
        p256dh=sub_data.keys.p256dh,
        auth=sub_data.keys.auth
    )
    session.add(new_sub)
    session.commit()
    return {"status": "success", "detail": "Подписка оформлена!"}