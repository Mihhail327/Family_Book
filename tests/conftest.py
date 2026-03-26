import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import User
from app.security import hash_password, create_jwt_token
from app.config import settings

# --- ⚙️ ОКРУЖЕНИЕ ---
sqlite_url = "sqlite:///:memory:"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

@pytest.fixture(autouse=True)
def mock_bot_alert():
    with patch("app.main.bot_alert", new_callable=AsyncMock) as mock:
        yield mock

@pytest.fixture(autouse=True)
def speed_up_tests():
    with patch("asyncio.sleep", return_value=None):
        yield

# --- 🧪 ФИКСТУРЫ ---

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session): 
    app.dependency_overrides[get_session] = lambda: session
    
    # ✅ Указываем base_url, чтобы куки авторизации всегда "прилипали" к домену
    client = TestClient(app, base_url="http://testserver", follow_redirects=False)
    
    # Патч для Honeypot
    original_post = client.post
    def patched_post(url, *args, **kwargs):
        if any(path in url for path in ["/auth/register/", "/auth/guest"]):
            data = kwargs.get("data", {})
            data.setdefault("confirm_email_address", "")
            kwargs["data"] = data
        return original_post(url, *args, **kwargs)
    
    client.post = patched_post # type: ignore
    yield client
    app.dependency_overrides.clear()

# ✅ ИСПРАВЛЕНО: Теперь это обычная функция-хелпер, а не фикстура
def authorize_client(client: TestClient, user_id: int):
    token = create_jwt_token(
        data={"sub": str(user_id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # 1. Ставим куки (для обычных переходов)
    client.cookies.set("user_session", token, domain="testserver", path="/")
    client.cookies.set("access_token", token, domain="testserver", path="/")
    
    # 2. Прописываем заголовок (для API запросов лайков/комментов)
    client.headers.update({"Authorization": f"Bearer {token}"})
    
    return token

@pytest.fixture
def test_user(session: Session):
    user = User(
        username="test_user_123",
        display_name="Тестер",
        hashed_password=hash_password("123"),
        role="user"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture
def admin_user(session: Session, client: TestClient):
    user = User(
        username="god_mode",
        display_name="Admin",
        hashed_password=hash_password("admin_pass"),
        role="admin"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    authorize_client(client, user.id) # type: ignore
    return user

@pytest.fixture
def normal_user_token_headers(client: TestClient, test_user: User):
    token = authorize_client(client, test_user.id) # type: ignore
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def admin_token_headers(client: TestClient, admin_user: User):
    token = authorize_client(client, admin_user.id) # type: ignore
    return {"Authorization": f"Bearer {token}"}