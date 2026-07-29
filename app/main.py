import os
from datetime import date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request, Depends, Response, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select, func, extract, col

# Глобальные импорты на уровне модуля для оптимизации производительности
from app.models import User, Notification, Event, AuditLog
from app.routers import family, admin
from app.config import STATIC_DIR, settings
from app.database import engine, get_session
from app.api import auth, posts
from app.logger import log_action, log_error, log_exception, format_exception_details
from app.services.cleanup import cleanup_expired_guests, cleanup_old_logs, cleanup_stale_temp_files
from app.core.templates import templates
from app.security import get_current_user
from app.services.notifier import bot_alert, manager
from app.services import notification

from starlette.concurrency import run_in_threadpool

# --- 1. ПРОВЕРКИ ---
print(f"🔍 Ищу файл тут: {os.path.join(str(STATIC_DIR), 'app.js')}")
print(f"❓ Файл реально существует? {os.path.exists(os.path.join(str(STATIC_DIR), 'app.js'))}")

async def periodic_guest_cleanup():
    import asyncio
    while True:
        try:
            await asyncio.sleep(60)
            if settings.ENV != "testing":
                def _do_cleanup():
                    with Session(engine) as session:
                        cleanup_expired_guests(session)
                        cleanup_stale_temp_files()
                await run_in_threadpool(_do_cleanup)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            log_error("PERIODIC_CLEANUP_ERR", str(e))

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print(f"\n--- 🛠 СТАРТ FAMILY_BOOK {settings.VERSION} ---")
        def _do_startup_cleanup():
            with Session(engine) as session:
                cleanup_expired_guests(session)
                cleanup_old_logs(session)
                cleanup_stale_temp_files()
        await run_in_threadpool(_do_startup_cleanup)
        log_action("SYSTEM", "STARTUP", f"Сервер запущен v{settings.VERSION}")
    except Exception as e:  # noqa: BLE001
        log_error("STARTUP", str(e))
    
    import asyncio
    cleanup_task = asyncio.create_task(periodic_guest_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()

# --- 3. ИНИЦИАЛИЗАЦИЯ APP ---
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# --- 4. СТАТИКА ---
if not STATIC_DIR.exists():
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Папка статики не найдена по пути {STATIC_DIR}")
else:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    print(f"✅ Статика подключена: {STATIC_DIR}")

# --- 5. MIDDLEWARES ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://family-book-yh93.onrender.com",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
)

def _fetch_user_context(user_id: int):
    from datetime import datetime, timezone
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            return None, 0, False
        if user.is_guest and user.expires_at:
            now_utc = datetime.now(timezone.utc)
            exp_utc = user.expires_at if user.expires_at.tzinfo else user.expires_at.replace(tzinfo=timezone.utc)
            if exp_utc < now_utc:
                cleanup_expired_guests(session)
                return None, 0, True

        unread_count = session.exec(
            select(func.count())
            .where(
                Notification.user_id == user.id,
                col(Notification.is_read) == False
            )
        ).first() or 0
        session.expunge(user)
        return user, unread_count, False

@app.middleware("http")
async def user_injection_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path.startswith("/ws") or request.url.path in ("/debug-test", "/health"):
        request.state.user = None
        request.state.unread_notifications_count = 0
        return await call_next(request)
    try:
        user_id = get_current_user(request)
        if user_id:
            from app.core.redis import redis_client
            redis_key = f"user:{user_id}:unread_notifications_count"
            cached_val = await redis_client.get(redis_key)

            if cached_val is not None:
                try:
                    unread_count = int(cached_val)
                except (ValueError, TypeError):
                    unread_count = 0
                def _get_user_only():
                    with Session(engine) as session:
                        u = session.get(User, user_id)
                        if u:
                            session.expunge(u)
                        return u
                user = await run_in_threadpool(_get_user_only)
                is_expired = False
            else:
                user, unread_count, is_expired = await run_in_threadpool(_fetch_user_context, user_id)
                if user:
                    await redis_client.set(redis_key, str(unread_count), ex=86400)

            if is_expired and not request.url.path.startswith("/auth/"):
                from app.utils.flash import flash
                response = RedirectResponse("/auth/login", status_code=303)
                response.delete_cookie("user_session", path="/")
                response.delete_cookie("access_token", path="/")
                response.delete_cookie("refresh_token", path="/auth/refresh")
                flash(response, "Срок действия демо-доступа (30 минут) истек!", "info")
                return response

            request.state.user = user
            request.state.unread_notifications_count = unread_count
        else:
            request.state.user = None
            request.state.unread_notifications_count = 0
    except Exception as e:  # noqa: BLE001
        log_error("MIDDLEWARE_USER_ERR", str(e))
        request.state.user = None
        request.state.unread_notifications_count = 0
    return await call_next(request)

def inject_user(request: Request):
    return {
        "user": getattr(request.state, "user", None),
        "unread_notifications_count": getattr(request.state, "unread_notifications_count", 0),
        "VERSION": str(settings.VERSION)
    }

templates.context_processors.append(inject_user)

@app.middleware("http")
async def sentinel_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path.startswith("/ws") or request.url.path == "/debug-test":
        return await call_next(request)
    try:
        response = await call_next(request)
        if response.status_code in [400, 403] and settings.ENV != "testing":
            client_ip = request.client.host if request.client else "127.0.0.1"
            await bot_alert.send_alert(
                f"🛡️ **SECURITY TRIGGER**\n📍 Path: `{request.url.path}`\n🚫 Code: `{response.status_code}`\n🌐 IP: `{client_ip}`",
                level="SECURITY"
            )
        return response
    except Exception as exc:
        log_error("CRITICAL_FAIL", f"Error: {exc!s} at {request.url.path}")
        if settings.ENV != "testing":
            await bot_alert.send_alert(f"🚨 **CRITICAL SERVER ERROR**\n❌ Error: `{exc!s}`", level="CRITICAL")
        raise

# --- 6. PWA И СЛУЖЕБНЫЕ РОУТЫ ---
@app.get("/sw.js", include_in_schema=False)
async def serve_sw(): 
    file_path = STATIC_DIR / "sw.js" 
    if not file_path.exists():
        return Response(status_code=404)
    return FileResponse(file_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

@app.get("/manifest.json", tags=["PWA"], include_in_schema=False)
async def serve_manifest(): 
    file_path = STATIC_DIR / "manifest.json" 
    return FileResponse(file_path) if file_path.exists() else Response(status_code=404)

@app.get("/debug-test")
async def debug_test(): return {"status": "ok", "message": "FastAPI работает!"}

# --- 7. КАЛЕНДАРЬ ---
@app.get("/calendar", response_class=HTMLResponse) 
async def calendar_page(request: Request, user_id=Depends(get_current_user), session: Session = Depends(get_session)):
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)
    user = session.get(User, user_id)
    return templates.TemplateResponse(request=request, name="calendar.html", context={"user": user})

@app.get("/calendar/events")
async def get_calendar_events(month: int, year: int):
    with Session(engine) as session:
        statement = select(func.distinct(extract('day', Event.event_date))).where(
            extract('month', Event.event_date) == month, extract('year', Event.event_date) == year
        )
        results = session.exec(statement).all()
        return {"events": [int(day) for day in results]}

@app.get("/calendar/day-details") 
async def get_calendar_day_details(day: int, month: int, year: int, request: Request, user_id=Depends(get_current_user)):
    with Session(engine) as session:
        user = session.get(User, user_id)
        statement = select(Event).where(
            extract('day', Event.event_date) == day,
            extract('month', Event.event_date) == month,
            extract('year', Event.event_date) == year
        )
        events = session.exec(statement).all()
        return templates.TemplateResponse(request=request, name="includes/_calendar_day_content.html", 
                                        context={"events": events, "selected_date": f"{day:02d}.{month:02d}.{year}", "user": user})

@app.post("/calendar/events/add")
async def add_calendar_event(title: str = Form(...), event_date: str = Form(...), event_type: str = Form(...), user_id=Depends(get_current_user)):
    from app.models import Event, EventType, AuditLog
    with Session(engine) as session:
        new_event = Event(title=title, event_date=date.fromisoformat(event_date), event_type=EventType(event_type), user_id=user_id)
        session.add(new_event)
        session.flush()
        audit = AuditLog(
            user_id=user_id,
            action="EVENT_CREATE",
            details=f"Создано событие в календаре: '{title}' ({event_date})"
        )
        session.add(audit)
        session.commit()
    return Response(headers={"HX-Refresh": "true"})

@app.delete("/calendar/events/{event_id}")
async def delete_event(event_id: int, current_user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    from app.models import Event, User, AuditLog
    event = session.get(Event, event_id)
    user = session.get(User, current_user_id)
    if not event or not user:
        return Response(status_code=404)
    if event.user_id == current_user_id or user.role == "admin": 
        event_title = event.title
        session.delete(event)
        audit = AuditLog(
            user_id=current_user_id,
            action="EVENT_DELETE",
            details=f"Удалено событие из календаря: '{event_title}' (ID: {event_id})"
        )
        session.add(audit)
        session.commit()
        return Response(status_code=200)
    return Response(status_code=403)

# --- 8. РОУТЕРЫ ---
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(posts.router, tags=["Posts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(family.router, prefix="/auth", tags=["Family"])
app.include_router(notification.router)

@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/login", include_in_schema=False)
async def redirect_old_login():
    return RedirectResponse(url="/auth/login", status_code=301)

@app.get("/register/{token}", include_in_schema=False)
async def redirect_old_register(token: str):
    return RedirectResponse(url=f"/auth/register/{token}", status_code=301)

# --- 9. WEBSOCKET ---
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    user_id = get_current_user(websocket)  # type: ignore
    await manager.connect(websocket, user_id=user_id)
    try:
        while True:
            await websocket.receive_text()
    except Exception:  # noqa: BLE001
        manager.disconnect(websocket, user_id=user_id)

# --- 10. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ВСЕХ ОШИБОК (SENTINEL TELEMETRY) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    status_code = 500
    exc_status = getattr(exc, "status_code", None)
    exc_code = getattr(exc, "code", None)
    
    if exc_status is not None:
        try:
            status_code = int(exc_status)
        except (ValueError, TypeError):
            status_code = 500
    elif exc_code is not None:
        try:
            status_code = int(exc_code)
        except (ValueError, TypeError):
            status_code = 500

    # 1. Игнорируем спам от статики и фавикона
    if request.url.path.startswith("/static") or "favicon.ico" in request.url.path:
        try:
            return Response(status_code=status_code)
        except Exception:  # noqa: BLE001
            return Response(status_code=500)

    # 2. Извлекаем данные о пользователе и IP
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_info = f"Гость ({client_ip})"
    user_obj = None

    try:
        user_id = get_current_user(request)
        if user_id:
            def _get_user_info():
                with Session(engine) as session:
                    u = session.get(User, user_id)
                    if u:
                        session.expunge(u)
                    return u
            user_obj = await run_in_threadpool(_get_user_info)
            if user_obj:
                user_info = f"@{user_obj.username} (ID: {user_obj.id}, Имя: '{user_obj.display_name}', Роль: {user_obj.role})"
    except Exception as e:  # noqa: BLE001
        log_error("USER_FETCH_ERR", f"Не удалось извлечь контекст пользователя: {e}")

    # 3. Подробный стек-трейс ошибки
    stack_snippet = format_exception_details(exc)
    log_exception(f"ROUTE_FAIL [{request.method} {request.url.path}]", exc, user_info=user_info)

    # 4. Сохранение в БД AuditLog (для просмотра администратором в Админ-Панели)
    if status_code >= 500:
        def _save_audit_error():
            with Session(engine) as session:
                audit = AuditLog(
                    user_id=user_obj.id if user_obj else None,
                    action="CRITICAL_ERROR",
                    details=f"Path: {request.method} {request.url.path} | Error: {type(exc).__name__}: {exc!s} | Stack: {stack_snippet[:150]}",
                    ip_address=client_ip
                )
                session.add(audit)
                session.commit()
        try:
            await run_in_threadpool(_save_audit_error)
        except Exception as e:  # noqa: BLE001
            log_error("AUDIT_SAVE_ERR", str(e))

    # 5. Telegram-Алерт в бот (с форматированием и стеком)
    if status_code >= 500 and settings.ENV != "testing":
        try:
            message = (
                f"🚨 **SENTINEL: CRITICAL ERROR (500)**\n\n"
                f"👤 **Пользователь:** `{user_info}`\n"
                f"📍 **Маршрут:** `{request.method} {request.url.path}`\n"
                f"🌐 **Client IP:** `{client_ip}`\n"
                f"❌ **Ошибка:** `{type(exc).__name__}: {exc!s}`\n\n"
                f"📜 **Стек-трейс:**\n```python\n{stack_snippet[:500]}\n```"
            )
            await bot_alert.send_alert(message, level="CRITICAL")
        except Exception as alert_err:  # noqa: BLE001
            log_error("SENTINEL_ALERT_ERR", str(alert_err))

    # 6. Безопасный ответ пользователю
    if request.url.path == "/" or request.url.path == "/auth/login":
        return HTMLResponse(
            content=f"<h1>Упс! Системная ошибка {status_code}</h1><p>Мы уже чиним. Попробуйте обновить страницу через минуту.</p>",
            status_code=status_code
        )

    return RedirectResponse(url="/?error_redirect=true", status_code=303)

