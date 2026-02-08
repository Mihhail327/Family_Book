import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends, status, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload
from app.utils.flash import get_flashed_messages

# Подгружаем настройки ПЕРВЫМИ
from app.config import settings

# Находим корень проекта для sys.path
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR.parent) not in sys.path:
    sys.path.append(str(APP_DIR.parent))

from app.database import create_db_and_tables, get_session 
from app.api import auth, posts
from app.api.auth import get_current_user 
from app.models import User, Post, Comment
from app.logger import log_action, log_error

# Используем путь к шаблонам строго через конфиг
templates = Jinja2Templates(directory=str(Path(settings.STATIC_PATH).parent / "templates"))

# РЕГИСТРИРУЕМ FLASH-УВЕДОМЛЕНИЯ
# Это позволит вызывать get_flashed_messages(request) прямо внутри любого HTML-файла
templates.env.globals.update(get_flashed_messages=get_flashed_messages)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    try:
        # Берем ПУТЬ СТРОГО ИЗ SETTINGS
        static_path = Path(settings.STATIC_PATH)
        uploads_posts = Path(settings.POSTS_PATH)
        
        print(f"\n--- 🛠 ФИНАЛЬНАЯ ДИАГНОСТИКА ---")
        print(f"Статика (settings): {static_path}")
        print(f"Папка существует?: {static_path.exists()}")
        
        # Проверка пельмешки
        pelmen = static_path / "default_avatar.png"
        print(f"✅ ПЕЛЬМЕШКА: {'Найдена' if pelmen.exists() else '❌ НЕТ ФАЙЛА'}")
        
        # Проверка постов
        print(f"📁 Ищу посты в: {uploads_posts}")
        if uploads_posts.exists():
            count = len(list(uploads_posts.glob("*")))
            print(f"✅ ПАПКА POSTS: OK (Файлов: {count})")
        else:
            print(f"❌ ПАПКА POSTS: НЕ НАЙДЕНА!")
        print(f"-------------------------------\n")
            
        create_db_and_tables()
        log_action("SYSTEM", "STARTUP", "Сервер запущен")
    except Exception as e:
        log_error("STARTUP", str(e))
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- МОНТИРОВАНИЕ СТАТИКИ (ЕДИНАЯ ТОЧКА) ---

# Монтируем строго ту папку, в которую пишут роутеры
if Path(settings.STATIC_PATH).exists():
    app.mount("/static", StaticFiles(directory=settings.STATIC_PATH), name="static")
else:
    print(f"⚠️ КРИТИЧЕСКАЯ ОШИБКА: Директория {settings.STATIC_PATH} не найдена!")

# Роуты для PWA (тоже через settings)
@app.get("/sw.js", include_in_schema=False)
async def serve_sw(): 
    return FileResponse(Path(settings.STATIC_PATH) / "sw.js")

@app.get("/manifest.json", include_in_schema=False)
async def serve_manifest(): 
    return FileResponse(Path(settings.STATIC_PATH) / "manifest.json")

# --- РОУТЕРЫ ---
app.include_router(auth.router, tags=["Auth"])
app.include_router(posts.router, tags=["Posts"])

@app.get("/")
async def index(request: Request, db: Session = Depends(get_session)):
    user_id = get_current_user(request)
    if not user_id: return RedirectResponse("/login", status_code=303)
    user = db.get(User, user_id)
    if not user: return RedirectResponse("/login", status_code=303)

    try:
        statement = (
            select(Post)
            .options(
                selectinload(Post.author), # type: ignore
                selectinload(Post.images), # type: ignore
                selectinload(Post.comments).selectinload(Comment.author) # type: ignore
            )
            .order_by(col(Post.created_at).desc())
        )
        posts_list = db.exec(statement).all() 
        return templates.TemplateResponse("index.html", {"request": request, "posts": posts_list, "user": user})
    except Exception as e:
        log_error("INDEX_PAGE", str(e))
        return templates.TemplateResponse("index.html", {"request": request, "posts": [], "user": user})

@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    if request.url.path.startswith("/static"):
        return Response(status_code=404)
    return RedirectResponse("/", status_code=303)

@app.get("/settings")
async def settings_page(request: Request, db: Session = Depends(get_session)):
    user_id = get_current_user(request)
    if not user_id: return RedirectResponse("/login", status_code=303)
    
    user = db.get(User, user_id)
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})