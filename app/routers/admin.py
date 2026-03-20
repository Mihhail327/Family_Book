from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel

from app.database import get_session
from app.models import User, AuditLog
from app.services.notification import create_system_notification
# ДОБАВЛЕНО: Защита ввода
from app.security import get_current_user, validate_security_input
from app.logger import log_action

router = APIRouter(tags=["Admin"])

# Схема для рассылки (удобно для Swagger и валидации)
class BroadcastSchema(BaseModel):
    title: str
    message: str
    category: str = "info"

# Зависимость для проверки прав "Бога"
def admin_required(
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    user = session.get(User, user_id)
    
    if not user or user.role != "admin":
        log_action("SECURITY", "UNAUTHORIZED_ADMIN_ACCESS", f"User ID {user_id} tried to enter admin panel")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="У вас недостаточно прав для этого действия"
        )
    return user

@router.get("/users", response_model=List[User])
async def get_all_users(
    session: Session = Depends(get_session),
    _: User = Depends(admin_required)
):
    return session.exec(select(User)).all()

@router.post("/broadcast")
async def broadcast_message(
    data: BroadcastSchema, # Используем схему
    session: Session = Depends(get_session),
    admin: User = Depends(admin_required)
):
    """Массовая рассылка уведомлений с защитой от XSS"""
    # Валидируем ввод
    safe_title = validate_security_input(data.title)
    safe_message = validate_security_input(data.message)

    create_system_notification(session, safe_title, safe_message, category=data.category)
    
    log_action("ADMIN", "BROADCAST", f"Admin {admin.username} sent: {safe_title}")
    return {"status": "success", "message": "Уведомления отправлены"}

@router.delete("/users/{user_id}")
async def delete_user_manually(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    admin: User = Depends(admin_required)
):
    """Полное удаление пользователя и его следов"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Вы не можете удалить самого себя")

    username = user.username
    
    # Сначала создаем запись в аудите
    audit = AuditLog(
        user_id=admin.id,
        action="DELETE_USER",
        details=f"Deleted user: {username}",
        ip_address = request.client.host if request.client else "127.0.0.1"
    )
    session.add(audit)
    
    # Затем удаляем пользователя (каскад в models.py удалит и его посты/фото)
    session.delete(user)
    
    # Один коммит на обе операции (Атомарность)
    session.commit()
    
    log_action("ADMIN", "DELETE_USER", f"Admin {admin.username} removed {username}")
    return {"status": "success", "detail": f"Пользователь {username} удален"}