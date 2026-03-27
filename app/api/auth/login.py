from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.models import User
from app.database import get_session
from app.security import create_session_token, create_jwt_token, create_refresh_token, decode_jwt_token
from app.config import settings
from app.utils.flash import flash
from app.core.templates import templates

router = APIRouter()


def set_auth_cookies(response: Response, user_id: int):
    # Генерация токенов
    access_token = create_jwt_token(
        data={"sub": str(user_id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(data={"sub": str(user_id)})

    is_prod = settings.ENV == "production"

    # 1. Refresh Token - СТРОГО HttpOnly, доступен только для роута обновления
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/auth/refresh",
        secure=is_prod,
        samesite="lax",
    )

    # 2. Access Token - Кладем в куки для бесшовной работы FastAPI + HTMX
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        secure=is_prod,
        samesite="lax",
    )

    # 3. Классическая сессия (user_session) - Для обратной совместимости старых юзеров
    session_token = create_session_token(user_id)
    response.set_cookie(
        key="user_session", 
        value=session_token, 
        httponly=True, 
        secure=is_prod, 
        path="/"
    )

    return access_token


@router.get("/login")
async def login_page(request: Request):
    # Добавь settings в контекст!
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"settings": settings}
    )


@router.post("/login")
async def login(display_name: str = Form(...), session: Session = Depends(get_session)):
    name = display_name.strip()
    user = session.exec(select(User).where(User.display_name == name)).first()

    if not user:
        res = RedirectResponse("/auth/login", status_code=303)
        flash(res, "Семья тебя не узнала. Проверь имя или обратись за инвайтом!", "error")
        return res

    res = RedirectResponse("/", status_code=303)
    flash(res, f"Рады видеть тебя, {user.display_name}!", "success")

    # ✅ Вот правильная и безопасная запись для линтера
    if user.id is not None:
        set_auth_cookies(res, user.id)

    return res


@router.get("/logout")
async def logout():
    res = RedirectResponse("/auth/login", status_code=303)
    # Удаляем все следы пользователя
    res.delete_cookie("user_session", path="/")
    res.delete_cookie("access_token", path="/")
    res.delete_cookie("refresh_token", path="/auth/refresh")
    return res


# ИСПРАВЛЕНО: Изменили на GET, чтобы HTMX мог стучаться из фона
@router.get("/refresh")
async def refresh_access_token(request: Request): # Убрали response из параметров
    token = request.cookies.get("refresh_token")
    if not token:
        return Response(status_code=204)
    
    payload = decode_jwt_token(token)
    if not payload or payload.get("type") != "refresh":
        return Response(status_code=204)
    
    user_id = payload.get("sub")
    
    # ✅ Создаем НОВЫЙ ответ с явным статус-кодом
    res = Response(status_code=204)
    
    if user_id is not None:
        set_auth_cookies(res, int(user_id))
    
    return res