from typing import Generator
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event 
from sqlalchemy.engine import Engine 
from app.config import settings
from app.models import User 
from app.security import hash_password
from app.logger import log_action, log_error

# 1. Проверяем, какая база используется
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# 2. Настраиваем движок и события в зависимости от типа базы
if is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    
    # Включаем PRAGMA только для SQLite
    # Переименовали connection_record в _, чтобы линтер не ругался
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # Для PostgreSQL (Render) создаем чистый engine БЕЗ событий
    engine = create_engine(settings.DATABASE_URL)

def create_db_and_tables():
    """Инициализация базы данных и настройка прав админа."""
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        log_error("DB_INIT", f"Не удалось создать таблицы: {e}")
        return

    with Session(engine) as session:
        try:
            secure_pwd = hash_password(settings.ADMIN_PASSWORD)
        
            # --- 1. Системный админ (всегда под рукой) ---
            admin_user = session.exec(select(User).where(User.username == "admin")).first()
            if admin_user:
                admin_user.hashed_password = secure_pwd
                admin_user.display_name = "Михаил (Система)" 
                session.add(admin_user)
            else:
                # Создаем системного админа, если база пустая
                session.add(User(
                    username="admin",
                    display_name="Михаил (Система)",
                    hashed_password=secure_pwd,
                    role="admin",
                    avatar_url="/static/default_avatar.png"
                ))

            # --- 2. Поиск твоего личного аккаунта (по нику) ---
            target_username = "Михаил" # Убедись, что в базе ты записан именно так!
            me = session.exec(select(User).where(User.username == target_username)).first()
            
            if me:
                me.role = "admin"
                session.add(me)
                log_action("SYSTEM", "DB_UPDATE", f"Права админа выданы пользователю {me.username}")
            else:
                # Полезно видеть, если аккаунт еще не найден
                print(f"--- INFO: Пользователь '{target_username}' пока не найден. Права не выданы. ---")

            session.commit()
            print("--- ✅ База данных успешно инициализирована ---")
            
        except Exception as e:
            session.rollback()
            log_error("DB_INIT", f"Ошибка настройки прав: {e}")

def get_session() -> Generator[Session, None, None]:
    """Генератор сессий для FastAPI (Dependency Injection)."""
    with Session(engine) as session:
        yield session