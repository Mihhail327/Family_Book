from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import cast, List
from sqlmodel import Session, select, col, delete
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import User, Post, PostImage, AuditLog
from app.logger import log_action, log_error

def cleanup_expired_guests(session: Session) -> int:
    """Удаляет просроченных гостей, их аватары и файлы постов."""
    now = datetime.now(timezone.utc)

    # Лайфхак: Жадная загрузка связанных таблиц (избегаем N+1)
    statement = (
        select(User)
        .where(
            User.is_guest, 
            col(User.expires_at).is_not(None), 
            col(User.expires_at) < now
        )
        .options(
            selectinload(User.posts).selectinload(Post.images) # type: ignore
        )
    )
    expired_guests = session.exec(statement).all()

    if not expired_guests:
        return 0

    count = 0
    for guest in expired_guests:
        g = cast(User, guest)
        deleted_files = 0

        # 1. Удаляем аватар (если он загружен, а не дефолтный)
        if g.avatar_url and "/uploads/avatars/" in g.avatar_url:
            avatar_path = Path(settings.STATIC_PATH) / g.avatar_url.lstrip("/")
            if avatar_path.exists() and avatar_path.is_file():
                try:
                    avatar_path.unlink()
                    deleted_files += 1
                except Exception as e:
                    log_error("CLEANUP", f"Не удалось удалить аватар {g.avatar_url}: {e}")

        # 2. Удаляем картинки из постов (с типизацией для линтера)
        posts_to_clean: List[Post] = g.posts
        for post in posts_to_clean:
            images_to_clean: List[PostImage] = post.images
            for img in images_to_clean:
                file_path = Path(settings.STATIC_PATH) / img.url.lstrip("/")
                if file_path.exists() and file_path.is_file():
                    try:
                        file_path.unlink()
                        deleted_files += 1
                    except Exception as e:
                        log_error("CLEANUP", f"Не удалось удалить фото {img.url}: {e}")

        # 3. Удаляем профиль (ondelete="CASCADE" почистит БД)
        session.delete(g)
        log_action("SYSTEM_GC", "GUEST_CLEANUP", f"Удален гость {g.username}. Файлов стерто: {deleted_files}")
        count += 1

    session.commit()
    return count


def cleanup_old_logs(session: Session) -> int:
    """Удаляет логи старше 30 дней, чтобы база не раздувалась."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    try:
        # Убедись, что поле с датой в модели AuditLog называется именно created_at!
        # Если оно называется timestamp, замени AuditLog.created_at на AuditLog.timestamp
        statement = delete(AuditLog).where(AuditLog.created_at < thirty_days_ago)  # type: ignore
        result = session.exec(statement)
        session.commit()
        
        deleted_count = result.rowcount
        if deleted_count > 0:
            log_action("SYSTEM_GC", "LOGS_CLEANUP", f"Удалено {deleted_count} старых записей логов")
            
        return deleted_count
    except Exception as e:
        session.rollback()
        log_error("CLEANUP", f"Ошибка при удалении старых логов: {e}")
        return 0