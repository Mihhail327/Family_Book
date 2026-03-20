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
def create_jwt_token(data: dict, expires_delta: timedelta): # Исправлено: data вместо date
    """Универсальная функция создания токена"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    # Сохраняем exp как timestamp для совместимости с библиотекой
    to_encode.update({"exp": int(expire.timestamp())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

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
    1. Сначала ищем JWT в заголовке Authorization (Access Token)
    2. Если нет - ищем подписанную сессию в куках
    """
    # --- 1. Пытаемся достать JWT (Access Token) ---
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_jwt_token(token)
        if payload and "sub" in payload:
            return int(payload["sub"])

    # --- 2. Если JWT нет, ищем подписанную куку (Session) ---
    session_token = request.cookies.get("user_session")
    if not session_token:
        return None
    
    try:
        unsigned_data = signer.unsign(session_token, max_age=1209600)
        return int(unsigned_data.decode('utf-8') if isinstance(unsigned_data, bytes) else unsigned_data)
    except Exception:
        return None
    
def create_session_token(user_id: int) -> str:
    """
    Создает подписанную строку из ID пользователя для хранения в куках.
    Именно это имя (create_session_token) ожидает твой auth.py.
    """
    # Превращаем ID в строку и подписываем её
    return signer.sign(str(user_id)).decode('utf-8')

def create_refresh_token(data: dict):
    """Создает долгоживущий токен для обновления"""
    # Ставим 30 дней по дефолту
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)