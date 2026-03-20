from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User, Post, PostImage
from app.services.cleanup import cleanup_expired_guests
from app.security import hash_password


def test_cleanup_expired_guests(client: TestClient, session: Session):
    """Тестируем Garbage Collector: должен удалять только просроченных гостей и их файлы."""
    
    # 1. СОЗДАЕМ ИСТЕКШЕГО ГОСТЯ (Путь БЕЗ static в начале, код сам его добавит)
    expired_guest = User(
        username="expired_guest",
        display_name="Просроченный",
        hashed_password=hash_password("123"),
        is_guest=True,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        avatar_url="/uploads/avatars/old_avatar.webp" # Убрали static отсюда
    )
    session.add(expired_guest)
    session.commit()
    session.refresh(expired_guest)

    # Пост с картинкой (тоже без static в URL)
    post = Post(content="Мусор", author_id=expired_guest.id) # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    image = PostImage(url="/uploads/posts/old_pic.webp", post_id=post.id) # type: ignore
    session.add(image)
    session.commit()
    session.expire_all()

    # 2. СОЗДАЕМ АКТИВНОГО ГОСТЯ (Его время выйдет только через 30 минут)
    active_time = datetime.now(timezone.utc) + timedelta(minutes=30)
    active_guest = User(
        username="active_guest",
        display_name="Живой",
        hashed_password=hash_password("123"),
        is_guest=True,
        expires_at=active_time
    ) # type: ignore
    session.add(active_guest)
    session.commit()
    session.expire_all()

    # 3. ЗАПУСКАЕМ МЕТЛУ
    # Мокаем os.path.exists и os.remove, чтобы тест не пытался реально удалять файлы с диска
    with patch("app.services.cleanup.Path") as mock_path_class:
        # Настраиваем поведение
        mock_path_class.return_value.exists.return_value = True
        mock_path_class.return_value.is_file.return_value = True
        # Магия: любой результат деления (/) тоже будет нашим моком
        mock_path_class.return_value.__truediv__.return_value = mock_path_class.return_value
        
        deleted_count = cleanup_expired_guests(session)

    # 4. ПРОВЕРЯЕМ РЕЗУЛЬТАТЫ
    assert deleted_count == 1  # Метла должна была смахнуть ровно 1 профиль

    # Убеждаемся, что истекший гость и его пост стерты из базы
    assert session.exec(select(User).where(User.username == "expired_guest")).first() is None
    assert session.exec(select(Post).where(Post.author_id == expired_guest.id)).first() is None

    # Убеждаемся, что активный гость остался цел и невредим
    assert session.exec(select(User).where(User.username == "active_guest")).first() is not None

    # Убеждаемся, что скрипт дважды попытался удалить файлы (1 аватар + 1 фото в посте)
    assert mock_path_class.return_value.unlink.call_count == 2