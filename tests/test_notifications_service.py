import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User, Notification
from app.services.notification import create_system_notification, deliver_push_notifications
from tests.conftest import authorize_client

@pytest.mark.asyncio
async def test_create_system_notification(session: Session, test_user: User):
    await create_system_notification(
        session=session,
        title="Тест",
        message="Приветственное сообщение",
        user_id=test_user.id,
        category="info"
    )
    
    notifs = session.exec(select(Notification).where(Notification.user_id == test_user.id)).all()
    assert len(notifs) == 1
    assert notifs[0].title == "Тест"
    assert notifs[0].is_read is False

    # Системное веерное уведомление для всех
    await create_system_notification(
        session=session,
        title="Глобальное объявление",
        message="Всем пользователям сайта",
        user_id=None,
        category="info"
    )

def test_notification_api_flow(client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    
    # 1. Публичный ключ
    res_pk = client.get("/push/public-key")
    assert res_pk.status_code == 200
    assert "publicKey" in res_pk.json()

    # 2. Подписка на Push
    res_sub = client.post("/push/subscribe", json={
        "endpoint": "https://push.example.com/sub/123",
        "keys": {"p256dh": "dummy_p256dh", "auth": "dummy_auth"}
    })
    assert res_sub.status_code == 200

    # 3. Повторная подписка (уже есть)
    res_sub_again = client.post("/push/subscribe", json={
        "endpoint": "https://push.example.com/sub/123",
        "keys": {"p256dh": "dummy_p256dh", "auth": "dummy_auth"}
    })
    assert res_sub_again.status_code == 200

    # 4. Создаем и проверяем уведомления
    notif = Notification(
        user_id=test_user.id, # type: ignore
        title="Новый пост",
        message="Кто-то опубликовал историю",
        category="info",
        is_read=False
    )
    session.add(notif)
    session.commit()
    
    res = client.get("/push/notifications")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Новый пост"
    
    mark_res = client.post("/push/notifications/mark-read")
    assert mark_res.status_code == 200
    
    session.refresh(notif)
    assert notif.is_read is True

@pytest.mark.asyncio
async def test_deliver_push_notifications(session: Session, test_user: User):
    await deliver_push_notifications(
        session=session,
        user_id=test_user.id,
        title="Push test",
        message="Message",
        link="/"
    )
