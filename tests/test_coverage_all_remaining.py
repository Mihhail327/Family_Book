import pytest
from datetime import timedelta
from fastapi import HTTPException
from fastapi.responses import Response
from app.security import (
    create_jwt_token, create_refresh_token, decode_jwt_token,
    hash_password, verify_password, validate_security_input
)
from app.services.notifier import SentinelBot, ConnectionManager
from app.utils.flash import flash

def test_security_utils_deep():
    # Токены
    jwt = create_jwt_token({"sub": "123"}, expires_delta=timedelta(minutes=30))
    assert jwt is not None

    ref = create_refresh_token({"sub": "123"})
    assert ref is not None

    decoded = decode_jwt_token(jwt)
    assert decoded is not None and decoded.get("sub") == "123"

    bad_decoded = decode_jwt_token("invalid.jwt.token")
    assert bad_decoded is None

    # Пароли
    pwd_hash = hash_password("secret")
    assert verify_password("secret", pwd_hash) is True
    assert verify_password("wrong", pwd_hash) is False

    # Валидатор безопасности (успешная строка)
    safe_text = validate_security_input("Привет Семья!")
    assert safe_text == "Привет Семья!"

    # Валидатор безопасности (перехват вредоносного скрипта)
    with pytest.raises(HTTPException):
        validate_security_input("Hello <script>alert(1)</script>")

def test_flash_messages_utility():
    response = Response()
    flash(response, "Тестовое флеш-сообщение", "info")
    assert response is not None

@pytest.mark.asyncio
async def test_notifier_bot_and_manager():
    bot = SentinelBot()
    await bot.send_alert("Тестовое сообщение", level="INFO")

    cm = ConnectionManager()
    await cm.broadcast({"message": "test broadcast"})
