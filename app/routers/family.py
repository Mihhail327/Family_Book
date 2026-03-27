from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.models import User
from app.core.templates import templates  # Убедись, что в этом файле создан объект 'templates'
from app.security import get_current_user
from app.database import get_session

# 1. ОБЯЗАТЕЛЬНО инициализируем роутер!
router = APIRouter()

@router.get("/family", response_class=HTMLResponse)
async def family_page(request: Request, session: Session = Depends(get_session)):
    # 2. Получаем ID текущего юзера
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse("/auth/login", status_code=303)

    # 3. Загружаем всех пользователей
    users = session.exec(select(User).order_by(User.display_name)).all()
    current_user = session.get(User, user_id)

    # 4. Рендерим страницу (используем объект templates)
    return templates.TemplateResponse(
        request=request, 
        name="family.html", 
        context={
            "users": users, 
            "user": current_user, 
            "now": datetime.now(timezone.utc)
        }
    )