import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.main import global_exception_handler
from app.services.notifier import manager
from app.models import User
from tests.conftest import authorize_client

@pytest.mark.asyncio
async def test_global_exception_handler_direct():
    # Создаем фейковый Request для тестирования обработчика 500
    scope = {"type": "http", "method": "GET", "path": "/test-error", "headers": []}
    req = Request(scope)
    res = await global_exception_handler(req, ValueError("Тестовое неперехваченное исключение"))
    assert res.status_code in [303, 500]

@pytest.mark.asyncio
async def test_connection_manager_full():
    mock_ws = AsyncMock()
    # Подключение и отключение анонимного сокета
    await manager.connect(mock_ws, user_id=None)
    assert mock_ws in manager.anonymous_connections

    manager.disconnect(mock_ws, user_id=None)
    assert mock_ws not in manager.anonymous_connections

    # Подключение и отключение пользователя
    await manager.connect(mock_ws, user_id=999)
    assert 999 in manager.active_connections

    await manager.broadcast({"type": "test_broadcast"}, user_id=999)
    manager.disconnect(mock_ws, user_id=999)
    assert 999 not in manager.active_connections

def test_refresh_token_valid(client: TestClient, test_user: User):
    login_res = client.post("/auth/login", data={"display_name": test_user.display_name}, follow_redirects=False)
    refresh_token = login_res.cookies.get("refresh_token")
    
    if refresh_token:
        client.cookies.set("refresh_token", refresh_token, path="/auth/refresh")
        res_ref = client.get("/auth/refresh")
        assert res_ref.status_code == 204
