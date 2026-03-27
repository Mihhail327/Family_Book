from sqlmodel import Session, select, col
from app.models import Notification, User
from typing import Optional
from app.services.notifier import manager 

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