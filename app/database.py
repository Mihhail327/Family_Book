from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event 
from sqlalchemy.engine import Engine 
from app.config import settings
from app.models import User 
from app.security import hash_password
from app.logger import log_action, log_error

# 1. Проверяем, какая база используется
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# 2. Настраиваем аргументы подключения (для Postgres оставляем пустыми)
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args
)

# 3. ВКЛЮЧАЕМ ПРАГМУ ТОЛЬКО ЕСЛИ ЭТО SQLITE
if is_sqlite:
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Эта команда нужна только для SQLite
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# --- ВКЛЮЧЕНИЕ КАСКАДНОГО УДАЛЕНИЯ ---
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # Без этой команды SQLite проигнорирует ondelete="CASCADE" в моделях
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def create_db_and_tables():
    """Инициализация базы данных: создание таблиц и профиля админа."""
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        log_error("DB_INIT", f"Не удалось создать таблицы: {e}")
        return

    with Session(engine) as session:
        admin_exists = session.exec(select(User).where(User.username == "admin")).first()
        
        if not admin_exists:
            try:
                admin = User(
                    username="admin",
                    display_name="Глава Семьи",
                    hashed_password=hash_password("admin123"),
                    role="admin",
                    # ВАЖНО: Убедись, что файл на диске называется именно так. 
                    # Если ты скачал пельмешку как JPG, переименуй файл в default_avatar.png
                    avatar_url="/static/default_avatar.png" 
                )
                session.add(admin)
                session.commit()
                log_action("SYSTEM", "DB_INIT", "Первичный запуск: создан профиль admin (Глава Семьи)")
            except Exception as e:
                session.rollback()
                log_error("DB_INIT", f"Ошибка при создании админа: {e}")

def get_session():
    """Генератор сессий для FastAPI (Dependency Injection)."""
    with Session(engine) as session:
        yield session