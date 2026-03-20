import pytest
from fastapi import HTTPException
from app.security import validate_security_input, validate_name_limits

def test_security_valid_input():
    """Проверяем, что нормальный текст проходит без проблем и ложных срабатываний."""
    assert validate_security_input("Привет, семья! Как дела?") == "Привет, семья! Как дела?"
    assert validate_security_input("Просто текст с цифрами 123") == "Просто текст с цифрами 123"
    assert validate_security_input("") == ""
    assert validate_security_input(None) is None # type: ignore


def test_security_xss_injection():
    """Тестируем защиту от межсайтового скриптинга (XSS)."""
    # Попытка прокинуть тег script
    with pytest.raises(HTTPException) as exc_info:
        validate_security_input("Привет! Посмотри фото <script>alert('hack')</script>")
    assert exc_info.value.status_code == 400
    assert "Security trigger" in exc_info.value.detail

    # Попытка прокинуть зловредный линк
    with pytest.raises(HTTPException) as exc_info:
        validate_security_input("javascript:alert('XSS')")
    assert exc_info.value.status_code == 400


def test_security_sql_injection():
    """Тестируем защиту от базовых SQL-инъекций."""
    # Классический обход авторизации (OR 1=1)
    with pytest.raises(HTTPException) as exc_info:
        validate_security_input("admin' OR 1=1 --")
    assert exc_info.value.status_code == 400

    # Попытка выгрузить чужие данные (UNION SELECT)
    with pytest.raises(HTTPException) as exc_info:
        validate_security_input("UNION SELECT username, password FROM user")
    assert exc_info.value.status_code == 400


def test_validate_name_limits():
    """Проверяем граничные значения для имен (чтобы не сломали верстку длинными никами)."""
    # Нормальный ник (от 3 до 15 символов)
    assert validate_name_limits("Brother", is_username=True) == "Brother"
    
    # Слишком короткий ник
    with pytest.raises(HTTPException) as exc_info:
        validate_name_limits("Bo", is_username=True)
    assert exc_info.value.status_code == 400
    
    # Слишком длинное имя (больше 25 символов)
    with pytest.raises(HTTPException):
        validate_name_limits("ЭтоОченьДлинноеИмяКотороеСломаетФронтенд", is_username=False)