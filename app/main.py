from datetime import date
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from sqlalchemy import text

#from app.models import User
from app.routers import family
from app.config import STATIC_DIR, settings
from app.database import create_db_and_tables, engine, get_session
from app.api import auth, posts
from app.logger import log_action, log_error
from app.services.cleanup import cleanup_expired_guests, cleanup_old_logs
from app.routers import admin
from app.core.templates import templates
from app.security import get_current_user
from app.services.notifier import bot_alert

print(f"🔍 Ищу файл тут: {os.path.join(str(STATIC_DIR), 'app.js')}")
print(f"❓ Файл реально существует? {os.path.exists(os.path.join(str(STATIC_DIR), 'app.js'))}")

def fix_database_schema():
    print("🛠 Sentinel: Checking database schema...")
    columns_to_add = [
        ('is_guest', 'BOOLEAN DEFAULT FALSE'),
        ('expires_at', 'TIMESTAMP WITH TIME ZONE'),
        ('push_token', 'TEXT'),
        ('last_seen', 'TIMESTAMP WITH TIME ZONE')
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            try:
                # Пытаемся добавить колонку, если её нет
                conn.execute(text(f'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS {col_name} {col_type};'))
                conn.commit()
                print(f"✅ Column {col_name} checked/added.")
            except Exception as e:
                print(f"⚠️ Column {col_name} skip: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения v3.0"""
    try:
        print(f"\n--- 🛠 СТАРТ FAMILY_BOOK {settings.VERSION} ---")
        fix_database_schema()
        create_db_and_tables()
        
        # Запускаем метлу при старте сервера
        with Session(engine) as session:
            # Чистим гостей
            deleted_count = cleanup_expired_guests(session)
            if deleted_count > 0:
                print(f"🧹 Очистка: Удалено {deleted_count} просроченных гостей")
                
            # 🟢 ДОБАВЛЕНО: Чистим старые логи (старше 30 дней)
            deleted_logs = cleanup_old_logs(session)
            if deleted_logs > 0:
                print(f"🧹 Очистка: Удалено {deleted_logs} старых логов")
                
        log_action("SYSTEM", "STARTUP", f"Сервер запущен v{settings.VERSION}")
    except Exception as e:
        log_error("STARTUP", str(e))
    yield

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# МОНИТОРИНГ(Alert)
# --- ЕДИНЫЙ МОНИТОРИНГ (Sentinel + Alert Bot) ---
@app.middleware("http")
async def sentinel_middleware(request: Request, call_next):
    # 1. Пропускаем статику и тесты
    if request.url.path.startswith("/static") or request.url.path == "/debug-test":
        return await call_next(request)

    try:
        # 2. Ждем ответ от системы
        response = await call_next(request)
        
        # 3. Если это ошибка (400, 403) — логируем и шлем алерт
        if response.status_code in [400, 403] and settings.ENV != "testing":
            log_error("SENTINEL", f"Detected {response.status_code} on {request.method} {request.url.path}")
            
            await bot_alert.send_alert(
                f"🛡️ **SECURITY TRIGGER**\n"
                f"📍 Path: `{request.url.path}`\n"
                f"🚫 Code: `{response.status_code}`\n"
                f"🌐 IP: `{request.client.host}`", # type: ignore
                level="SECURITY"
            )
        
        return response

    except Exception as exc:
        # 4. Если сервер упал (500)
        log_error("CRITICAL_FAIL", f"Error: {str(exc)} at {request.url.path}")
        
        if settings.ENV != "testing":
            await bot_alert.send_alert(
                f"🚨 **CRITICAL SERVER ERROR**\n"
                f"❌ Error: `{str(exc)}`\n"
                f"📍 Path: `{request.url.path}`",
                level="CRITICAL"
            )
        raise exc
        
# async def update_last_seen_middleware(request: Request, call_next):
#     if request.url.path.startswith("/static") or request.url.path == "/debug-test":
#         return await call_next(request)

#     response = await call_next(request)
    
#     try:
#         user_id = get_current_user(request)
#         if user_id:
#             with Session(engine) as session:
#                 user = session.get(User, user_id)
#                 if user:
#                     from datetime import datetime, timezone
#                     now = datetime.now(timezone.utc)

#                     # Берем время и чиним его (если база выдала naive)
#                     user_ts = user.last_seen
#                     if user_ts and user_ts.tzinfo is None:
#                         user_ts = user_ts.replace(tzinfo=timezone.utc)
                    
#                     # Если времени в базе еще нет ИЛИ прошло больше 60 сек
#                     if not user_ts or (now - user_ts).total_seconds() > 60:
#                         user.last_seen = now
#                         session.add(user)
#                         session.commit()
#     except Exception as e:
#         print(f"❌ Middleware Online Error: {e}")
            
#     return response

# Монтируем статику
if not STATIC_DIR.exists():
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Папка статики не найдена по пути {STATIC_DIR}")
else:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"✅ Статика подключена: {STATIC_DIR}")

# PWA магия (Service Worker и Manifest)
@app.get("/sw.js", include_in_schema=False)
async def serve_sw(): 
    file_path = STATIC_DIR / "sw.js" 
    if not file_path.exists():
        log_error("PWA", f"sw.js not found at {file_path}")
        return Response(status_code=404)
    return FileResponse(
        file_path, 
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )

@app.get("/manifest.json", tags=["PWA"], include_in_schema=False)
async def serve_manifest(): 
    file_path = STATIC_DIR / "manifest.json" 
    if not file_path.exists():
        return Response(status_code=404)
    return FileResponse(file_path)

# --- КОРНЕВЫЕ РОУТЫ И КАЛЕНДАРЬ ---

@app.get("/calendar", response_class=HTMLResponse) 
async def calendar_page(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("calendar.html", {"request": request, "user": user})

@app.get("/calendar/events")
async def get_calendar_events(month: int, year: int):
    # МЕНЯЕМ Post на Event!
    from sqlmodel import select, func, extract
    from app.models import Event # <--- Важно!
    
    with Session(engine) as session:
        # Ищем уникальные дни в таблице Event по полю event_date
        statement = select(func.distinct(extract('day', Event.event_date))).where(
            extract('month', Event.event_date) == month,
            extract('year', Event.event_date) == year
        )
        results = session.exec(statement).all()
        return {"events": [int(day) for day in results]}

@app.get("/calendar/day-details") 
async def get_calendar_day_details(
    day: int, month: int, year: int, 
    request: Request, 
    user=Depends(get_current_user)
):
    from sqlmodel import select, extract
    from app.models import Event 
    
    with Session(engine) as session:
        statement = select(Event).where(
            extract('day', Event.event_date) == day,
            extract('month', Event.event_date) == month,
            extract('year', Event.event_date) == year
        )
        events = session.exec(statement).all()
        
        # Рендерим новый файл, где только события
        return templates.TemplateResponse(
            "includes/_calendar_day_content.html", 
            {
                "request": request, 
                "events": events,
                "selected_date": f"{day:02d}.{month:02d}.{year}",
                "user": user
            }
        )
    
@app.delete("/calendar/events/{event_id}")
async def delete_event(
    event_id: int, 
    current_user_id: int = Depends(get_current_user),
    session: Session = Depends(get_session) 
):
    from app.models import Event, User
    
    event = session.get(Event, event_id)
    user = session.get(User, current_user_id)
    
    if not event or not user:
        return Response(status_code=404)

    # ✅ РАЗРЕШАЕМ: если это мой ивент ИЛИ я админ
    if event.user_id == current_user_id or user.role == "admin": 
        session.delete(event)
        session.commit()
        return Response(status_code=200)
        
    return Response(status_code=403)
    
@app.post("/calendar/events/add")
async def add_calendar_event(
    title: str = Form(...),
    event_date: str = Form(...),
    event_type: str = Form(...), 
    user_id=Depends(get_current_user) 
):
    from app.models import Event, EventType
    
    if not user_id:
        return Response(status_code=401)
        
    with Session(engine) as session:
        # Вариант А: Если в БД нужно сохранить именно ID (самый простой)
        new_event = Event(
            title=title,
            event_date=date.fromisoformat(event_date),
            event_type=EventType(event_type), 
            user_id=user_id  # Просто используем число, которое пришло из Depends
        )
        
        session.add(new_event)
        session.commit()
    
    return Response(headers={"HX-Refresh": "true"})

# --- ПОДКЛЮЧЕНИЕ РОУТЕРОВ ---
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(posts.router, tags=["Posts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(family.router, prefix="/auth", tags=["Family"])


for route in app.routes:
    print(f"Путь: {route.path} | Имя: {getattr(route, 'name', '???')}") # type: ignore
# ✅ «Заплатка» для старых ссылок, чтобы убрать петлю
@app.get("/login", include_in_schema=False)
async def redirect_old_login():
    return RedirectResponse(url="/auth/login", status_code=301)

@app.get("/register/{token}", include_in_schema=False)
async def redirect_old_register(token: str):
    return RedirectResponse(url=f"/auth/register/{token}", status_code=301)

@app.get("/debug-test")
async def debug_test():
    return {"status": "ok", "message": "FastAPI работает!"}