from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User
from tests.conftest import authorize_client

def test_admin_generate_links(client: TestClient, admin_user: User):
    authorize_client(client, admin_user.id) # type: ignore
    
    # Семейная ссылка
    res_family = client.post("/admin/generate-link", json={"role": "family"})
    assert res_family.status_code == 200
    assert "register" in res_family.json()["url"]

    # Гостевая ссылка
    res_guest = client.post("/admin/generate-link", json={"role": "guest"})
    assert res_guest.status_code == 200
    assert "is_guest=true" in res_guest.json()["url"]

def test_admin_dashboard_and_logs_stream(client: TestClient, admin_user: User):
    authorize_client(client, admin_user.id) # type: ignore
    
    res_dashboard = client.get("/admin/dashboard")
    assert res_dashboard.status_code == 200

    res_stream = client.get("/admin/logs/stream")
    assert res_stream.status_code == 200

    res_users = client.get("/admin/users")
    assert res_users.status_code == 200
    assert isinstance(res_users.json(), list)

    res_logs = client.get("/admin/logs")
    assert res_logs.status_code == 200

def test_admin_delete_user_and_self_prevention(client: TestClient, admin_user: User, session: Session):
    authorize_client(client, admin_user.id) # type: ignore
    
    # Создаем юзера для удаления
    user_to_delete = User(username="victim", display_name="Жертва", hashed_password="pwd", role="user")
    session.add(user_to_delete)
    session.commit()
    session.refresh(user_to_delete)

    # 1. Попытка удалить самого себя
    res_self = client.delete(f"/admin/users/{admin_user.id}")
    assert res_self.status_code == 400

    # 2. Изменение роли пользователя
    res_role = client.patch(f"/admin/users/{user_to_delete.id}/role", json={"role": "blocked"})
    assert res_role.status_code == 200

    # 3. Удаление другого пользователя
    res_del = client.delete(f"/admin/users/{user_to_delete.id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

def test_admin_broadcast_and_notifications_polling(client: TestClient, admin_user: User):
    authorize_client(client, admin_user.id) # type: ignore
    
    res_broadcast = client.post("/admin/broadcast", json={
        "title": "Объявление",
        "message": "Семейная новость для всех",
        "category": "info"
    })
    assert res_broadcast.status_code == 200

    res_latest = client.get("/admin/api/notifications/latest")
    assert res_latest.status_code == 200
