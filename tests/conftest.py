import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models import User
from app.security import hash_password, create_jwt_token
from app.config import settings


# SQLite в памяти
sqlite_url = "sqlite:///:memory:"
engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@pytest.fixture
def login_client_fix():
    """Фикстура-фабрика для авторизации клиента"""
    def _login(client, user):
        from app.security import create_jwt_token
        from datetime import timedelta
        from app.config import settings
        
        token = create_jwt_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        # Устанавливаем куку
        client.cookies.set("access_token", token, domain="testserver", path="/")
    
    return _login

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session): 
    def get_session_override():
        return session
    
    app.dependency_overrides[get_session] = get_session_override
    # Важно: follow_redirects=False помогает ловить 303 статус
    client = TestClient(app, follow_redirects=False)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture(name="test_user")
def test_user_fixture(session: Session):
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

# ✅ ИСПРАВЛЕНО: Теперь фикстуры ставят КУКИ в клиент
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
    
    # Генерируем токен и сразу «логиним» клиент через куки
    token = create_jwt_token(
    data={"sub": str(user.id)}, 
    expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) 
)
    client.cookies.set("access_token", token, domain="testserver", path="/")
    return user

@pytest.fixture
def normal_user_token_headers(client: TestClient, test_user: User):
    from datetime import timedelta
    from app.security import create_jwt_token
    from app.config import settings

    access_token = create_jwt_token(
        data={"sub": str(test_user.id)}, # ✅ ИСПРАВЛЕНО: используем test_user
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    client.cookies.set("access_token", access_token, domain="testserver", path="/")
    return {"Authorization": f"Bearer {access_token}"}

@pytest.fixture
def admin_token_headers(client: TestClient, admin_user: User):
    from datetime import timedelta
    from app.security import create_jwt_token
    from app.config import settings

    # ✅ ИСПРАВЛЕНО: Заменили user.id на admin_user.id
    token = create_jwt_token(
        data={"sub": str(admin_user.id)}, 
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # ✅ КРИТИЧНО: ставим куку для админа
    client.cookies.set("access_token", token, domain="testserver", path="/")
    
    return {"Authorization": f"Bearer {token}"}