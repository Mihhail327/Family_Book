from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime

# --- 1. ТАБЛИЦА СВЯЗИ ЛАЙКОВ (Many-to-Many) ---
class PostLike(SQLModel, table=True):
    """
    Промежуточная таблица для связи Many-to-Many между User и Post.
    """
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    post_id: int = Field(foreign_key="post.id", primary_key=True)

# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str
    display_name: str
    role: str = Field(default="member")
    
    # ИСПРАВЛЕНО: Убираем default=None, чтобы не мешать инициализации
    avatar_url: Optional[str] = Field(nullable=True) 
    referred_by: Optional[int] = Field(default=None)

    # Связи остаются без изменений...
    posts: List["Post"] = Relationship(back_populates="author")
    comments: List["Comment"] = Relationship(back_populates="author")
    liked_posts: List["Post"] = Relationship(back_populates="likers", link_model=PostLike)

# --- 3. МОДЕЛЬ ПОСТА ---
class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: Optional[str] = Field(default=None)
    
    # Время создания (обязательно UTC для серверов)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    is_gift: bool = Field(default=False)
    is_opened: bool = Field(default=False)

    author_id: int = Field(foreign_key="user.id")

    # Relationships
    author: Optional["User"] = Relationship(
        back_populates="posts",
        sa_relationship_kwargs={"lazy": "joined"} # Загружаем автора сразу (анти N+1 проблема)
    )
    
    # При удалении поста удаляем все картинки и комментарии (cascade)
    images: List["PostImage"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    comments: List["Comment"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    
    likers: List["User"] = Relationship(
        back_populates="liked_posts",
        link_model=PostLike
    )

# --- МОДЕЛЬ ИЗОБРАЖЕНИЙ ---
class PostImage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str 
    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE") 

    post: Optional["Post"] = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"passive_deletes": True} 
    )

# --- 5. МОДЕЛЬ КОММЕНТАРИЕВ ---
class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    post_id: int = Field(foreign_key="post.id", ondelete="CASCADE")
    author_id: int = Field(foreign_key="user.id")

    # Добавляем сюда тоже для симметрии и надежности
    post: Optional["Post"] = Relationship(
        back_populates="comments",
        sa_relationship_kwargs={"passive_deletes": True}
    )
    author: Optional["User"] = Relationship(back_populates="comments")