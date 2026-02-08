import bcrypt
from fastapi import Request
from typing import Optional
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired

# Импортируем настройки
from app.config import settings 

# Создаем подписчика
signer = TimestampSigner(settings.SECRET_KEY)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def create_session_token(user_id: int) -> str:
    """Создает токен сессии"""
    return signer.sign(str(user_id)).decode('utf-8')

def get_current_user(request: Request) -> Optional[int]:
    """Извлекает ID из куки с проверкой подписи"""
    session_token = request.cookies.get("user_session")
    
    # --- ДЕБАГ: Если хочешь увидеть, что прилетает в консоль ---
    # print(f"DEBUG: Кука из браузера: {session_token}")
    
    if not session_token:
        return None
        
    try:
        # Проверяем подпись (токен живет 14 дней)
        unsigned_id = signer.unsign(session_token, max_age=1209600)
        return int(unsigned_id)
    except (BadSignature, SignatureExpired, ValueError) as e:
        # Если подпись неверна или истекла
        print(f"DEBUG: Ошибка авторизации: {e}")
        return None