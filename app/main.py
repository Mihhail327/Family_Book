from datetime import date
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request, Depends, Response, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from sqlalchemy import text

from app.routers import family
from app.config import STATIC_DIR, settings
from app.database import create_db_and_tables, engine, get_session
from app.api import auth, posts
from app.logger import log_action, log_error
from app.services.cleanup import cleanup_expired_guests, cleanup_old_logs
from app.routers import admin
from app.core.templates import templates
from app.security import get_current_user
from app.services.notifier import bot_alert, manager

# --- 1. ПРОВЕРКИ ---
print(f"🔍 Ищу файл тут: {os.path.join(str(STATIC_DIR), 'app.js')}")
print(f"❓ Файл реально существует? {os.path.exists(os.path.join(str(STATIC_DIR), 'app.js'))}")

# --- 2. МИГРАЦИИ БД ---
def fix_database_schema():
    print("🛠 Sentinel: STARTING EMERGENCY MIGRATION...")
    commands = [
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_guest BOOLEAN DEFAULT FALSE;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS push_token TEXT;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE;',
        'ALTER TABLE "postimage" ADD COLUMN IF NOT EXISTS position INTEGER DEFAULT 0;',
        'ALTER TABLE "postlike" ADD COLUMN IF NOT EXISTS reaction_type TEXT DEFAULT \'❤️\';',
        'ALTER TABLE "post" ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE;',
        """
        CREATE TABLE IF NOT EXISTS "notification" (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT DEFAULT 'info',
            link TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS "event" (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            event_time TEXT DEFAULT '00:00',
            event_date DATE NOT NULL,
            event_type TEXT DEFAULT 'other',
            user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS "auditlog" (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            ip_address TEXT,
            is_error BOOLEAN DEFAULT FALSE
        );
        """
    ]
    with engine.connect() as conn:
        for cmd in commands:
            try:
                clean_cmd = cmd.strip()
                if clean_cmd:
                    conn.execute(text(clean_cmd))
                    conn.commit()
                    print(f"✅ SQL OK: {clean_cmd[:45]}...")
            except Exception as e:
                print(f"⚠️ SQL SKIP: {str(e)[:100]}")
    print("🛠 Sentinel: MIGRATION COMPLETE!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    fix_database_schema()
    try:
        print(f"\n--- 🛠 СТАРТ FAMILY_BOOK {settings.VERSION} ---")
        create_db_and_tables()
        with Session(engine) as session:
            cleanup_expired_guests(session)
            cleanup_old_logs(session)
        log_action("SYSTEM", "STARTUP", f"Сервер запущен v{settings.VERSION}")
    except Exception as e:
        log_error("STARTUP", str(e))
    yield

# --- 3. ИНИЦИАЛИЗАЦИЯ APP ---
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# --- 4. СТАТИКА (МОНТИРУЕМ СРАЗУ ПОСЛЕ APP) ---
if not STATIC_DIR.exists():
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Папка статики не найдена по пути {STATIC_DIR}")
else:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    print(f"✅ Статика подключена: {STATIC_DIR}")

# --- 5. MIDDLEWARES ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def sentinel_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path == "/debug-test":
        return await call_next(request)
    try:
        response = await call_next(request)
        if response.status_code in [400, 403] and settings.ENV != "testing":
            await bot_alert.send_alert(
                f"🛡️ **SECURITY TRIGGER**\n📍 Path: `{request.url.path}`\n🚫 Code: `{response.status_code}`\n🌐 IP: `{request.client.host}`", # type: ignore
                level="SECURITY"
            )
        return response
    except Exception as exc:
        log_error("CRITICAL_FAIL", f"Error: {str(exc)} at {request.url.path}")
        if settings.ENV != "testing":
            await bot_alert.send_alert(f"🚨 **CRITICAL SERVER ERROR**\n❌ Error: `{str(exc)}`", level="CRITICAL")
        raise exc

# --- 6. PWA И СЛУЖЕБНЫЕ РОУТЫ ---
@app.get("/sw.js", include_in_schema=False)
async def serve_sw(): 
    file_path = STATIC_DIR / "sw.js" 
    if not file_path.exists(): return Response(status_code=404)  # noqa: E701
    return FileResponse(file_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

@app.get("/manifest.json", tags=["PWA"], include_in_schema=False)
async def serve_manifest(): 
    file_path = STATIC_DIR / "manifest.json" 
    return FileResponse(file_path) if file_path.exists() else Response(status_code=404)

@app.get("/debug-test")
async def debug_test(): return {"status": "ok", "message": "FastAPI работает!"}

# --- 7. КАЛЕНДАРЬ ---
@app.get("/calendar", response_class=HTMLResponse) 
async def calendar_page(request: Request, user=Depends(get_current_user)):
    if not user: return RedirectResponse(url="/auth/login", status_code=303)  # noqa: E701
    return templates.TemplateResponse(request=request, name="calendar.html", context={"user": user})

@app.get("/calendar/events")
async def get_calendar_events(month: int, year: int):
    from sqlmodel import select, func, extract
    from app.models import Event
    with Session(engine) as session:
        statement = select(func.distinct(extract('day', Event.event_date))).where(
            extract('month', Event.event_date) == month, extract('year', Event.event_date) == year
        )
        results = session.exec(statement).all()
        return {"events": [int(day) for day in results]}

@app.get("/calendar/day-details") 
async def get_calendar_day_details(day: int, month: int, year: int, request: Request, user=Depends(get_current_user)):
    from sqlmodel import select, extract
    from app.models import Event 
    with Session(engine) as session:
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
    from app.models import Event, EventType
    with Session(engine) as session:
        session.add(Event(title=title, event_date=date.fromisoformat(event_date), event_type=EventType(event_type), user_id=user_id))
        session.commit()
    return Response(headers={"HX-Refresh": "true"})

@app.delete("/calendar/events/{event_id}")
async def delete_event(event_id: int, current_user_id: int = Depends(get_current_user), session: Session = Depends(get_session)):
    from app.models import Event, User
    event = session.get(Event, event_id)
    user = session.get(User, current_user_id)
    if not event or not user: return Response(status_code=404)  # noqa: E701
    if event.user_id == current_user_id or user.role == "admin": 
        session.delete(event)
        session.commit()
        return Response(status_code=200)
    return Response(status_code=403)

# --- 8. РОУТЕРЫ ---
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(posts.router, tags=["Posts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(family.router, prefix="/auth", tags=["Family"])

@app.get("/login", include_in_schema=False)
async def redirect_old_login(): return RedirectResponse(url="/auth/login", status_code=301)

@app.get("/register/{token}", include_in_schema=False)
async def redirect_old_register(token: str): return RedirectResponse(url=f"/auth/register/{token}", status_code=301)

# --- 9. WEBSOCKET ---
@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()  # noqa: E701
    except Exception: manager.disconnect(websocket)  # noqa: E701

# --- 10. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ---
@app.exception_handler(404)
@app.exception_handler(500)
async def global_exception_handler(request: Request, exc):
    # 1. Получаем статус код безопасно
    status_code = 500
    if hasattr(exc, 'status_code'):
        status_code = exc.status_code
    elif hasattr(exc, 'code'): # Для некоторых типов ошибок
        status_code = exc.code

    # 2. Игнорируем спам от статики (чтобы бот не сходил с ума)
    if request.url.path.startswith("/static") or "favicon.ico" in request.url.path:
        return Response(status_code=status_code)

    # 3. Пытаемся узнать, кто «упал»
    user_info = "Неавторизованный гость"
    try:
        # ВАЖНО: используем await, так как функция асинхронная
        user = await get_current_user(request)  # type: ignore
        if user: 
            user_info = f"@{user.username} (ID: {user.id})"
    except:  # noqa: E722
        pass

    # 4. Отправляем алерт ТОЛЬКО если это не бесконечный редирект
    # И если это реально серьезная ошибка (500)
    if status_code == 500:
        await bot_alert.send_alert(
            f"🚨 **SENTINEL: CRITICAL ERROR**\n"
            f"👤 {user_info}\n"
            f"📂 Path: `{request.url.path}`\n"
            f"❌ Error: {type(exc).__name__}: {str(exc)}" # Добавили само описание ошибки! # type: ignore
        )

    # 5. УМНЫЙ РЕДИРЕКТ: 
    # Если мы уже на главной и там ошибка — не редиректим (чтобы не было петли)
    if request.url.path == "/" or request.url.path == "/auth/login":
        return HTMLResponse(
            content=f"<h1>Упс! Системная ошибка {status_code}</h1><p>Мы уже чиним. Попробуйте обновить через минуту.</p>", 
            status_code=status_code
        )
        
    return RedirectResponse(url="/?error_redirect=true")