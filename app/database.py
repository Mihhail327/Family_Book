from typing import Generator
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event 
from sqlalchemy.engine import Engine 

from app.config import settings
from app.models import User, AuditLog 
from app.security import hash_password, verify_password  
from app.logger import log_action, log_error

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

if is_sqlite:
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def create_db_and_tables():
    """Инициализация базы v2.0"""
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        log_error("DB_INIT", f"Критическая ошибка создания таблиц: {e}")
        return

    with Session(engine) as session:
        try:
            admin = session.exec(select(User).where(User.username == "admin")).first()
            
            if not admin:
                # Хешируем только если админа еще нет
                secure_pwd = hash_password(settings.ADMIN_PASSWORD)
                admin = User(
                    username="admin",
                    display_name="Михаил",
                    hashed_password=secure_pwd,
                    role="admin",
                    avatar_url="/static/default_avatar.png"
                )
                session.add(admin)
                log_action("SYSTEM", "DB_INIT", "Первая инициализация админа")
                session.add(AuditLog(action="SYSTEM_INIT", details="База данных v2.0 создана"))
            else:
                # ОПТИМИЗАЦИЯ: Обновляем хеш ТОЛЬКО если пароль в env изменился
                if not verify_password(settings.ADMIN_PASSWORD, admin.hashed_password):
                    admin.hashed_password = hash_password(settings.ADMIN_PASSWORD)
                    session.add(admin)
                    log_action("SYSTEM", "DB_UPDATE", "Пароль администратора обновлен из настроек")

            session.commit()
            print("--- ✅ База v3.0 готова к работе ---")
            
        except Exception as e:
            session.rollback()
            log_error("DB_INIT", f"Ошибка инициализации данных: {e}")

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session