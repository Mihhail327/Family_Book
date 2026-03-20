from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User


def test_guest_login_success(client: TestClient, session: Session):
    """Проверяем успешный вход: создание профиля, флаги и куки."""
    # ✅ ИСПРАВЛЕНО: Добавлен префикс /auth
    response = client.post(
        "/auth/guest", 
        data={"display_name": "Дядя Ваня (Демо)"}
    )
    
    # Должен быть успешный редирект на главную
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    
    # ✅ ИСПРАВЛЕНО: Теперь проверяем наличие access_token
    assert "access_token" in response.cookies
    assert "user_session" in response.cookies

    # Проверяем, что гость правильно записался в БД
    guest = session.exec(select(User).where(User.display_name == "Дядя Ваня (Демо)")).first()
    assert guest is not None
    assert guest.is_guest is True
    assert guest.role == "user"
    assert guest.expires_at is not None
    
    # Убеждаемся, что время жизни установлено в будущем
    assert guest.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_guest_login_name_too_short(client: TestClient, session: Session):
    """Проверка валидации: слишком короткое имя."""
    response = client.post(
        "/auth/guest", 
        data={"display_name": "Я"}
    )
    
    # ✅ ИСПРАВЛЕНО: Проверяем правильный путь редиректа
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"
    
    # В базе такого пользователя быть не должно
    guest = session.exec(select(User).where(User.display_name == "Я")).first()
    assert guest is None


def test_guest_login_name_too_long(client: TestClient, session: Session):
    """Проверка валидации: попытка сломать верстку длинным именем."""
    long_name = "А" * 25
    response = client.post(
        "/auth/guest", 
        data={"display_name": long_name}
    )
    
    # ✅ ИСПРАВЛЕНО: Проверяем правильный путь редиректа
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"
    
    guest = session.exec(select(User).where(User.display_name == long_name)).first()
    assert guest is None