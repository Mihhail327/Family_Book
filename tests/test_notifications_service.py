import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User, Notification
from app.services.notification import create_system_notification
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

def test_notification_api_flow(client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    
    # 1. Создаем уведомление
    notif = Notification(
        user_id=test_user.id, # type: ignore
        title="Новый пост",
        message="Кто-то опубликовал историю",
        category="info",
        is_read=False
    )
    session.add(notif)
    session.commit()
    
    # 2. Запрашиваем через API
    res = client.get("/push/notifications")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Новый пост"
    
    # 3. Помечаем как прочитанное
    mark_res = client.post("/push/notifications/mark-read")
    assert mark_res.status_code == 200
    
    # 4. Проверяем в БД
    session.refresh(notif)
    assert notif.is_read is True
