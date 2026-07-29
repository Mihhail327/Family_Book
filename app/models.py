from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, timezone, date
from enum import Enum


# --- 1. ТАБЛИЦА СВЯЗИ ЛАЙКОВ (Many-to-Many) ---
class PostLike(SQLModel, table=True):
    """
    Промежуточная таблица для связи Many-to-Many между User и Post.
    """
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE", index=True, primary_key=True)
    # ✅ ИСПРАВЛЕНО: Тип реакции теперь живет здесь
    reaction_type: str = Field(default="❤️")

# --- 2. МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    display_name: str
    role: str = Field(default="member")
    
    is_guest: bool = Field(default=False)
    expires_at: datetime | None = Field(default=None, nullable=True)
    
    avatar_url: str | None = Field(default=None, nullable=True) 
    referred_by: int | None = Field(default=None, nullable=True)
    
    # Токен для Web Push уведомлений
    push_token: str | None = Field(default=None, nullable=True)

    # ✅ ИСПРАВЛЕНО: Убраны все дубликаты связей. Оставлено по одной.
    posts: list["Post"] = Relationship(
        back_populates="author", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"} 
    )
    comments: list["Comment"] = Relationship(back_populates="author")
    liked_posts: list["Post"] = Relationship(back_populates="likers", link_model=PostLike)
    
    notifications: list["Notification"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# --- 3. МОДЕЛЬ ПОСТА ---
class Post(SQLModel, table=True):
    model_config = {"extra": "allow"}
    id: int | None = Field(default=None, primary_key=True)
    content: str | None = Field(default=None)
    
    # Время создания (обязательно UTC для серверов)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    is_gift: bool = Field(default=False)
    is_opened: bool = Field(default=False)

    author_id: int = Field(foreign_key="user.id")

    # Relationships
    author: Optional["User"] = Relationship(
        back_populates="posts",
        sa_relationship_kwargs={"lazy": "joined"} # Загружаем автора сразу (анти N+1 проблема)
    )
    
    # При удалении поста удаляем все картинки и комментарии (cascade)
    images: list["PostImage"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    comments: list["Comment"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    likers: list["User"] = Relationship(
        back_populates="liked_posts",
        link_model=PostLike
    )

# --- 4. МОДЕЛЬ ИЗОБРАЖЕНИЙ ---
class PostImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url: str 
    # ✅ ИСПРАВЛЕНО: Убраны ошибочные поля user_id и reaction_type
    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE", index=True)

    post: Optional["Post"] = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"passive_deletes": True} 
    )

    position: int = Field(default=0)

# --- 5. МОДЕЛЬ КОММЕНТАРИЕВ ---
class Comment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE", index=True)
    author_id: int = Field(foreign_key="user.id")
    parent_id: int | None = Field(default=None, foreign_key="comment.id", ondelete="CASCADE")

    post: Optional["Post"] = Relationship(
        back_populates="comments",
        sa_relationship_kwargs={"passive_deletes": True}
    )
    author: Optional["User"] = Relationship(back_populates="comments")

    parent: Optional["Comment"] = Relationship(
        back_populates="replies",
        sa_relationship_kwargs={"remote_side": "Comment.id"}
    )
    replies: list["Comment"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

# --- 6. МОДЕЛЬ ДЛЯ GOD-MODE ---
class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: int | None = Field(default=None, foreign_key="user.id")
    action: str
    details: str
    ip_address: str | None = None
    is_error: bool = Field(default=False)

# --- 7. МОДЕЛЬ УВЕДОМЛЕНИЙ ---
class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    title: str
    message: str
    category: str = Field(default="info")  # success, error, info, system
    is_read: bool = Field(default=False)
    
    # Ссылка на объект (опционально), например если уведомление о новом посте
    link: str | None = Field(default=None) 
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: User | None = Relationship(back_populates="notifications")

class EventType(str, Enum):
    BIRTHDAY = "birthday"
    MEETING = "meeting"
    CELEBRATION = "celebration"
    OTHER = "other"

class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    event_time: str | None = Field(default="00:00")
    event_date: date 
    event_type: EventType = Field(default=EventType.OTHER)
    user_id: int = Field(foreign_key="user.id")
    creator: Optional["User"] = Relationship()


class PushSubscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Специфичные данные, которые выдает браузер телефона
    endpoint: str = Field(index=True) # Уникальный URL устройства от Google/Apple
    p256dh: str # Публичный ключ устройства
    auth: str # Секрет устройства
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))