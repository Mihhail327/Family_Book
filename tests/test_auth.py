from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User
from app.config import settings
from app.security import hash_password

def test_register_user(client: TestClient, session: Session):
    token = settings.REGISTRATION_TOKEN
    
    # ✅ ИСПРАВЛЕНО: Добавлен префикс /auth
    response = client.post(
        f"/auth/register/{token}", 
        data={"display_name": "Брат"},
        follow_redirects=False 
    )

    # Проверяем успешный редирект на главную
    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    
    # Проверяем БД
    user = session.exec(select(User).where(User.display_name == "Брат")).first()
    assert user is not None

def test_login_existing_user(client: TestClient, test_user: User):
    # ✅ ИСПРАВЛЕНО: Полный путь к логину
    response = client.post(
        "/auth/login", 
        data={"display_name": test_user.display_name},
        follow_redirects=False
    )
    
    assert response.status_code == 303
    # ✅ ИСПРАВЛЕНО: Проверяем новые куки из Family_Book 2.0
    assert "access_token" in response.cookies
    assert "user_session" in response.cookies

def test_refresh_token_flow(client: TestClient, session: Session):
    user = User(
        display_name="Mihhail", 
        username="mihhail327", 
        hashed_password=hash_password(settings.DEFAULT_USER_PASSWORD),
        role="user"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # 1. Логинимся (через /auth/login)
    login_res = client.post("/auth/login", data={"display_name": "Mihhail"}, follow_redirects=False)
    
    # ✅ ИСПРАВЛЕНО: Проверяем наличие refresh_token
    # Напоминаю: в auth.py он ставится на путь /auth/refresh
    assert "refresh_token" in login_res.cookies 
    
    # 2. Пробуем обновить (у нас это теперь GET запрос по ТЗ)
    refresh_res = client.get("/auth/refresh") 
    
    # В твоем auth.py refresh возвращает 204 No Content при успехе
    assert refresh_res.status_code == 204
    assert "access_token" in refresh_res.cookies