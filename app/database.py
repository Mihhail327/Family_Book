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
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # Для PostgreSQL (Render) создаем чистый engine БЕЗ событий
    engine = create_engine(settings.DATABASE_URL)

def create_db_and_tables():
    """Инициализация базы данных: создание таблиц и профиля админа."""
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        log_error("DB_INIT", f"Не удалось создать таблицы: {e}")
        return

    with Session(engine) as session:
        try:
            # 1. Ищем существующего админа
            admin_user = session.exec(select(User).where(User.username == "admin")).first()
            
            if admin_user:
                # 2. Если нашли — принудительно обновляем ему пароль и имя
                admin_user.hashed_password = hash_password("kP9$vR2_nZ7!mX")
                admin_user.display_name = "Михаил" 
                session.add(admin_user)
                session.commit()
                log_action("SYSTEM", "DB_UPDATE", "Профиль админа (Михаил) обновлен")
            else:
                # 3. Если вдруг его нет — создаем с нуля
                admin = User(
                    username="admin",
                    display_name="Михаил",
                    hashed_password=hash_password("kP9$vR2_nZ7!mX"),
                    role="admin",
                    avatar_url="/static/default_avatar.png" 
                )
                session.add(admin)
                session.commit()
                log_action("SYSTEM", "DB_INIT", "Первичный запуск: создан профиль admin (Михаил)")
        except Exception as e:
            session.rollback()
            log_error("DB_INIT", f"Ошибка при работе с профилем админа: {e}")

def get_session():
    """Генератор сессий для FastAPI (Dependency Injection)."""
    with Session(engine) as session:
        yield session