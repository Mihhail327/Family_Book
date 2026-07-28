from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.config import settings


def test_guest_login_success(client: TestClient, session: Session):
    """Проверяем успешный вход: создание профиля, флаги и куки."""
    response = client.post(
        f"/auth/guest/{settings.REGISTRATION_TOKEN}", 
        data={"display_name": "Дядя Ваня (Демо)"}
    )
    
    # Должен быть успешный редирект на главную
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    
    assert "access_token" in response.cookies
    assert "user_session" in response.cookies

    # Проверяем, что гость правильно записался в БД
    guest = session.exec(select(User).where(User.display_name == "Дядя Ваня (Демо)")).first()
    assert guest is not None
    assert guest.is_guest is True
    assert guest.role in ("guest", "user")
    assert guest.expires_at is not None
    
    assert guest.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_guest_login_without_token_blocked(client: TestClient):
    """Проверяем, что вход без инвайт-токена блокируется."""
    response = client.post("/auth/guest", data={"display_name": "Хакер"})
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_guest_login_name_too_short(client: TestClient, session: Session):
    """Проверка валидации: слишком короткое имя."""
    response = client.post(
        f"/auth/guest/{settings.REGISTRATION_TOKEN}", 
        data={"display_name": "Я"}
    )
    
    assert response.status_code == 303
    assert response.headers["location"] == f"/auth/guest/{settings.REGISTRATION_TOKEN}"
    
    guest = session.exec(select(User).where(User.display_name == "Я")).first()
    assert guest is None


def test_guest_login_name_too_long(client: TestClient, session: Session):
    """Проверка валидации: попытка сломать верстку длинным именем."""
    long_name = "А" * 25
    response = client.post(
        f"/auth/guest/{settings.REGISTRATION_TOKEN}", 
        data={"display_name": long_name}
    )
    
    assert response.status_code == 303
    guest = session.exec(select(User).where(User.display_name == long_name)).first()
    assert guest is None


def test_register_with_guest_invite_link(client: TestClient, session: Session):
    """Проверяем регистрацию по гостевой инвайт-ссылке (?is_guest=true)."""
    from app.config import settings
    token = settings.REGISTRATION_TOKEN
    
    response = client.post(
        f"/auth/register/{token}?is_guest=true",
        data={"display_name": "Гостевой Посетитель", "is_guest": "true"},
        follow_redirects=False
    )
    
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    
    guest = session.exec(select(User).where(User.display_name == "Гостевой Посетитель")).first()
    assert guest is not None
    assert guest.is_guest is True
    assert guest.role == "guest"
    assert guest.expires_at is not None


def test_register_with_normal_family_invite_link(client: TestClient, session: Session):
    """Проверяем регистрацию по стандартной семейной инвайт-ссылке (без is_guest)."""
    from app.config import settings
    token = settings.REGISTRATION_TOKEN
    
    response = client.post(
        f"/auth/register/{token}",
        data={"display_name": "Двоюродный Брат"},
        follow_redirects=False
    )
    
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    
    member = session.exec(select(User).where(User.display_name == "Двоюродный Брат")).first()
    assert member is not None
    assert member.is_guest is False
    assert member.role == "user"
    assert member.expires_at is None