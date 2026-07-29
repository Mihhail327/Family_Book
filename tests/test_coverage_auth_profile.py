import io
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User
from app.config import settings
from tests.conftest import authorize_client

def test_register_flow_validation(client: TestClient, session: Session):
    token = settings.REGISTRATION_TOKEN
    
    # 1. Слишком короткое имя
    res = client.post(f"/auth/register/{token}", data={"display_name": "A"}, follow_redirects=False)
    assert res.status_code == 303
    assert "/auth/register/" in res.headers["Location"]

    # 2. Неверный инвайт-токен
    res_bad_token = client.post("/auth/register/bad_token_123", data={"display_name": "Тестер"}, follow_redirects=False)
    assert res_bad_token.status_code == 403

def test_profile_page_access(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    res = client.get(f"/auth/profile/{test_user.username}")
    assert res.status_code == 200
    assert test_user.display_name in res.text

def test_profile_page_not_found(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    res = client.get("/auth/profile/non_existent_user_999", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["Location"] == "/"

def test_update_name_success(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    res = client.post("/auth/update-name", data={"display_name": "Новое Имя"}, follow_redirects=False)
    assert res.status_code == 303
    
    updated_user = session.get(User, test_user.id)
    assert updated_user is not None
    assert updated_user.display_name == "Новое Имя"

def test_update_avatar_success(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    fake_img = io.BytesIO(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    files = {"avatar": ("test.gif", fake_img, "image/gif")}
    res = client.post("/auth/update-avatar", files=files, follow_redirects=False)
    assert res.status_code == 303

def test_logout(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    res = client.get("/auth/logout", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["Location"] == "/"
