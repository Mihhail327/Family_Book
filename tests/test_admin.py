from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User, Notification, AuditLog

def test_admin_access_denied_for_regular_user(client: TestClient, normal_user_token_headers):
    """Обычный юзер не должен видеть список всех пользователей"""
    response = client.get("/admin/users", headers=normal_user_token_headers)
    assert response.status_code == 403
    assert "Доступ запрещен" in response.json()["detail"]

def test_admin_get_users_list(client: TestClient, admin_token_headers):
    """Админ успешно получает список пользователей"""
    response = client.get("/admin/users", headers=admin_token_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_admin_broadcast_notification(client: TestClient, admin_token_headers, session: Session):
    """Тестируем массовую рассылку через админку (v2.1 с JSON)"""
    # Очищаем уведомления перед тестом, чтобы проверка len была точной
    session.exec(select(Notification)).all() 
    
    # Создаем 3-х пользователей для теста
    for i in range(3):
        session.add(User(username=f"user_{i}", display_name=f"User {i}", hashed_password="123"))
    session.commit()

    payload = {
        "title": "Внимание всем!",
        "message": "Системное обновление",
        "category": "system"
    }
    
    # ✅ ИСПРАВЛЕНО: Используем json= вместо params=
    response = client.post("/admin/broadcast", json=payload, headers=admin_token_headers)
    
    assert response.status_code == 200
    
    # Проверяем записи в БД
    notes = session.exec(select(Notification)).all()
    # Минимум 4 уведомления (3 юзера + админ)
    assert len(notes) >= 4
    # Проверяем, что хотя бы одно уведомление соответствует нашей рассылке
    assert any(n.category == "system" and n.title == "Внимание всем!" for n in notes)

def test_admin_delete_user_and_audit_log(client: TestClient, admin_token_headers, session: Session):
    """Тестируем удаление пользователя и запись в аудит (Атомарная транзакция)"""
    # Создаем жертву
    victim = User(username="victim", display_name="Жертва", hashed_password="123")
    session.add(victim)
    session.commit()
    session.refresh(victim)

    response = client.delete(f"/admin/users/{victim.id}", headers=admin_token_headers)
    assert response.status_code == 200
    
    # Проверяем, что юзера нет
    # Важно: делаем expire_all или refresh, чтобы session увидел изменения после commit в роуте
    session.expire_all()
    assert session.get(User, victim.id) is None
    
    # Проверяем AuditLog
    logs = session.exec(select(AuditLog).where(AuditLog.action == "DELETE_USER")).all()
    assert len(logs) > 0
    assert "victim" in logs[0].details