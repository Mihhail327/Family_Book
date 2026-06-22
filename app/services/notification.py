import json
import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select, col
from app.database import get_session
from app.security import get_current_user
from app.models import Notification, User, PushSubscription
from typing import Optional
from app.services.notifier import manager 
from app.config import settings
from pywebpush import webpush, WebPushException

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


def _send_single_push(sub_dict: dict, payload_data: dict):
    """Синхронный вызов pywebpush"""
    email = settings.VAPID_CLAIM_EMAIL
    if email.startswith("mailto:"):
        email = email[len("mailto:"):]
    webpush(
        subscription_info=sub_dict,
        data=json.dumps(payload_data),
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": f"mailto:{email}"}
    )

async def deliver_push_notifications(
    session: Session,
    user_id: Optional[int],
    title: str,
    message: str,
    link: Optional[str] = None,
    exclude_user_id: Optional[int] = None
):
    """Фоновая отправка push-уведомлений"""
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_CLAIM_EMAIL:
        return

    # Выбираем подписки
    if user_id:
        statement = select(PushSubscription).where(PushSubscription.user_id == user_id)
    else:
        # Всем кроме гостей
        statement = select(PushSubscription).join(User, PushSubscription.user_id == User.id).where(User.is_guest == False)

    if exclude_user_id:
        statement = statement.where(PushSubscription.user_id != exclude_user_id)

    subscriptions = session.exec(statement).all()
    if not subscriptions:
        return

    payload = {
        "title": title,
        "body": message,
        "url": link or "/"
    }

    for sub in subscriptions:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            # Сетевой I/O выносим в отдельный поток
            await asyncio.to_thread(_send_single_push, sub_info, payload)
        except WebPushException as ex:
            # Если подписка неактивна (404/410), удаляем её
            if ex.response is not None and ex.response.status_code in [404, 410]:
                session.delete(sub)
                session.commit()