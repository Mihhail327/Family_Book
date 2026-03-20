import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request, Depends, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.config import STATIC_DIR, settings
from app.database import create_db_and_tables, engine
from app.api import auth, posts
from app.logger import log_action, log_error
from app.services.cleanup import cleanup_expired_guests 
from app.routers import admin
from app.core.templates import templates
from app.security import get_current_user

print(f"🔍 Ищу файл тут: {os.path.join(str(STATIC_DIR), 'app.js')}")
print(f"❓ Файл реально существует? {os.path.exists(os.path.join(str(STATIC_DIR), 'app.js'))}")

router = APIRouter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения v2.0"""
    try:
        print(f"\n--- 🛠 СТАРТ FAMILY_BOOK {settings.VERSION} ---")
        create_db_and_tables()
        
        # Запускаем метлу при старте сервера
        with Session(engine) as session:
            deleted_count = cleanup_expired_guests(session)
            if deleted_count > 0:
                print(f"🧹 Очистка: Удалено {deleted_count} просроченных гостей")
        
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

# Монтируем статику
if not STATIC_DIR.exists():
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Папка статики не найдена по пути {STATIC_DIR}")
else:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"✅ Статика подключена: {STATIC_DIR}")

# Подключаем доменные роутеры (главная страница '/' теперь обрабатывается внутри posts.router)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(posts.router, tags=["Posts"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(router)

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

@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, user=Depends(get_current_user)):
    # Если юзер не залогинен — отправляем на вход
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
        
    return templates.TemplateResponse(
        "calendar.html", 
        {"request": request, "user": user}
    )

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