import re
import bcrypt
from fastapi import Request, HTTPException
from typing import Optional
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from itsdangerous import TimestampSigner

# Импортируем настройки
from app.config import settings 

# Создаем подписчика
signer = TimestampSigner(settings.SECRET_KEY)

# Новый эшалон защиты
def validate_security_input(text: str):
    if not text: 
        return text
    patterns = [r"UNION\s+SELECT", r"--", r"OR\s+1=1", r"<script", r"javascript:"]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Security trigger: Nice try!")
    return text

def validate_name_limits(name: str, is_username: bool = False):
    """Проверка длины имени"""
    if is_username and (len(name) < 3 or len(name) > 15):
        raise HTTPException(status_code=400, detail="Ник должен быть от 3 до 15 символов")
    if not is_username and len(name) > 25:
        raise HTTPException(status_code=400, detail="Имя слишком длинное (макс 25 символов)")
    return name

# хешируем пароль
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception: 
        return False
    
# JWT логика (для PWA и Silent Refresh)
def create_jwt_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": int(expire.timestamp())})
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Приводим алгоритм и ключ к строке явно
    return jwt.encode(to_encode, str(settings.SECRET_KEY), algorithm="HS256")

def decode_jwt_token(token: str) -> Optional[dict]:
    """Декодирует и проверяет токен"""
    try:
        # jose сама выкинет JWTError, если токен протух (exp истек)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
    
# Получение текущего Юзера
def get_current_user(request: Request) -> Optional[int]:
    """
    Универсальное извлечение ID пользователя:
    1. Ищем JWT в куках (access_token) - для обычных переходов и HTMX
    2. Ищем JWT в заголовке Authorization (для API/PWA)
    3. Ищем подписанную сессию (для старых пользователей)
    """
    # --- 1. Пытаемся достать JWT из КУК (самый приоритетный сейчас) ---
    token = request.cookies.get("access_token")
    
    # --- 2. Если в куках нет, смотрим заголовок Authorization ---
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    # Если токен найден (неважно где), декодируем
    if token:
        payload = decode_jwt_token(token)
        if payload and "sub" in payload:
            try:
                return int(payload["sub"])
            except (ValueError, TypeError):
                pass

    # --- 3. Если JWT нет совсем, ищем старую подписанную куку (Session) ---
    session_token = request.cookies.get("user_session")
    if session_token:
        try:
            # max_age=1209600 (14 дней)
            unsigned_data = signer.unsign(session_token, max_age=1209600)
            # Приводим к строке, если это байты
            user_id_str = unsigned_data.decode('utf-8') if hasattr(unsigned_data, 'decode') else unsigned_data
            return int(user_id_str)
        except Exception:
            return None
    
    return None
    
def create_session_token(user_id: int) -> str:
    """
    Создает подписанную строку из ID пользователя для хранения в куках.
    Именно это имя (create_session_token) ожидает твой auth.py.
    """
    # Превращаем ID в строку и подписываем её
    return signer.sign(str(user_id)).decode('utf-8')

def create_refresh_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: str() вокруг настроек
    return jwt.encode(to_encode, str(settings.SECRET_KEY), algorithm=str(settings.JWT_ALGORITHM))