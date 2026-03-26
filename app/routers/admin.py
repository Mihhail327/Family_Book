from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select, col
from typing import List
from pydantic import BaseModel

from app.database import get_session
from app.models import Notification, User, AuditLog
from app.services.notification import create_system_notification
from app.security import get_current_user, validate_security_input
from app.logger import log_action
from app.core.templates import templates
from app.config import settings

router = APIRouter(tags=["Admin"])

# Схемы данных
class BroadcastSchema(BaseModel):
    title: str
    message: str
    category: str = "info"

class InviteRequest(BaseModel):
    role: str  # 'family' или 'guest'

# Зависимость "Бога"
def admin_required(
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    user = session.get(User, user_id)
    if not user or user.role != "admin":
        log_action("SECURITY", "UNAUTHORIZED_ADMIN_ACCESS", f"User ID {user_id} tried to enter admin panel")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещен")
    return user

# --- УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---

@router.get("/users", response_model=List[User])
async def get_all_users(session: Session = Depends(get_session), _: User = Depends(admin_required)):
    return session.exec(select(User)).all()

@router.delete("/users/{user_id}")
async def delete_user_manually(
    user_id: int, request: Request, 
    session: Session = Depends(get_session), admin: User = Depends(admin_required)
):
    user = session.get(User, user_id)
    if not user: 
        raise HTTPException(status_code=404)
    if user.id == admin.id: 
        raise HTTPException(status_code=400, detail="Себя удалять нельзя")

    username = user.username
    audit = AuditLog(
        user_id=admin.id, action="DELETE_USER", details=f"Удален: {username}",
        ip_address = request.client.host if request.client else "127.0.0.1"
    )
    session.add(audit)
    session.delete(user)
    session.commit()
    log_action("ADMIN", "DELETE_USER", f"Admin {admin.username} removed {username}")
    return {"status": "success", "detail": f"Пользователь {username} удален"}

# --- ГЕНЕРАЦИЯ ССЫЛОК (НОВОЕ) ---

@router.post("/generate-link")
async def generate_invite_link(
    data: InviteRequest, 
    request: Request, 
    admin: User = Depends(admin_required)
):
    """Генерация ссылок для семьи и гостевой песочницы"""
    base_url = str(request.base_url).rstrip('/')
    
    if data.role == "guest":
        # Ссылка для гостей (добавляем флаг is_guest)
        token = settings.REGISTRATION_TOKEN # Используем основной токен
        url = f"{base_url}/auth/register/{token}?is_guest=true"
        log_action("ADMIN", "GUEST_LINK_GEN", f"{admin.username} создал гостевой пропуск")
    else:
        # Прямая ссылка для семьи
        url = f"{base_url}/auth/register/{settings.REGISTRATION_TOKEN}"
        log_action("ADMIN", "FAMILY_LINK_GEN", f"{admin.username} скопировал семейную ссылку")
        
    return {"status": "success", "url": url}

# --- ПРОСМОТР ЛОГОВ (НОВОЕ) ---

@router.get("/logs")
async def get_system_logs(
    limit: int = 100, 
    session: Session = Depends(get_session), 
    _: User = Depends(admin_required)
):
    """Последние 100 логов для терминала"""
    statement = select(AuditLog).order_by(col(AuditLog.id).desc()).limit(limit)
    return session.exec(statement).all()

# --- РАССЫЛКА И ДАШБОРД ---

@router.post("/broadcast")
async def broadcast_message(
    data: BroadcastSchema, 
    session: Session = Depends(get_session), 
    admin: User = Depends(admin_required)
):
    """Массовая рассылка с 'пингом' для фронтенда"""
    safe_title = validate_security_input(data.title)
    safe_message = validate_security_input(data.message)

    # Создаем уведомления для всех (кроме админа, чтобы не спамить себе)
    # Предполагаем, что у тебя в БД есть таблица SystemNotification
    create_system_notification(
        session, 
        safe_title, 
        safe_message, 
        category=data.category,
        is_broadcast=True # Пометка, чтобы фронт вывел это как Toast # type: ignore
    )
    
    log_action("ADMIN", "BROADCAST_SENT", f"Рассылка: {safe_title}")
    return {"status": "success", "message": "Рассылка ушла в эфир!"}

@router.get("/dashboard")
async def admin_dashboard(request: Request, admin: User = Depends(admin_required)):
    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context={"user": admin})

class RoleUpdate(BaseModel):
    role: str

@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int, 
    data: RoleUpdate, 
    admin: User = Depends(admin_required),
    session: Session = Depends(get_session)
):
    """Блокировка или смена роли пользователя"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя менять роль самому себе")
    
    old_role = user.role
    user.role = data.role
    session.add(user)
    session.commit()
    
    log_action("ADMIN", "ROLE_CHANGE", f"Admin {admin.username} changed {user.username} from {old_role} to {data.role}")
    return {"status": "success"}

# Добавь / перед api, чтобы путь стал абсолютным
@router.get("/api/notifications/latest") 
async def get_latest_notification(
    user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Проверка новых уведомлений для текущего пользователя (Polling)"""
    if not user_id:
        return {"new_message": False}

    # Твой остальной код ...
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=2)
    statement = select(Notification).where(
        Notification.user_id == user_id,
        Notification.created_at > time_threshold
    ).order_by(col(Notification.id).desc())
    
    notif = session.exec(statement).first()
    if notif:
        return {
            "new_message": True,
            "title": notif.title,
            "message": notif.message,
            "category": notif.category
        }
    return {"new_message": False}