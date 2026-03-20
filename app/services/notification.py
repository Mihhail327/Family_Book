from sqlmodel import Session, select, col
from app.models import Notification, User
from typing import Optional

def create_system_notification(
    session: Session,
    title: str,
    message: str,
    user_id: Optional[int] = None,
    category: str = "info",
    link: Optional[str] = None
):
    try:
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
            # 1. Используем col().is_(False) для Ruff
            # 2. Добавляем проверку .is_not(None) для успокоения Pylance
            statement = select(User.id).where(
                User.is_guest.is_(False), # type: ignore
                col(User.id).is_not(None)
            )
            user_ids = session.exec(statement).all()
            
            for uid in user_ids:
                # Теперь uid гарантированно int
                new_note = Notification(
                    user_id=uid,  # type: ignore
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