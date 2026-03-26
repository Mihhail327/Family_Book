from sqlmodel import Session, select, col
from app.models import Notification, User # Проверь, что в моделях это Notification
from typing import Optional


def create_system_notification(
    session: Session,
    title: str,
    message: str,
    user_id: Optional[int] = None,
    category: str = "info",
    link: Optional[str] = None,
    is_broadcast: bool = False # Добавили, чтобы вызов из admin.py не падал
):
    try:
        if user_id:
            # Уведомление конкретному пользователю
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
            statement = select(User.id).where(
                User.is_guest.is_(False), # type: ignore
                col(User.id).is_not(None)
            )
            user_ids = session.exec(statement).all()
            
            for uid in user_ids:
                new_note = Notification(
                    user_id=uid, # type: ignore
                    title=title,
                    message=message,
                    category=category,
                    link=link
                )
                session.add(new_note)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
