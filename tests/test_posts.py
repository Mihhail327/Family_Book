import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User, Post, PostLike, Comment
# Импортируем наш хелпер напрямую
from tests.conftest import authorize_client 

def test_create_and_read_post(client: TestClient, session: Session, test_user: User):
    # ✅ ИСПРАВЛЕНО: Используем хелпер вместо фикстуры
    authorize_client(client, test_user.id)  # type: ignore

    # 1. Создаем пост
    response = client.post(
        "/posts/create",
        data={
            "content": "Первая тестовая история в Family_Book!", 
            "is_gift": "false"
        },
        headers={"HX-Request": "true"}
    )
    # В Sentinel 3.0 мы используем HTMX, поэтому ждем 200 и фрагмент HTML
    assert response.status_code == 200 
    assert "Первая тестовая история" in response.text
    
    # 2. Проверяем БД
    session.expire_all()
    post = session.exec(select(Post).where(Post.author_id == test_user.id)).first()
    
    assert post is not None
    assert post.content == "Первая тестовая история в Family_Book!"


@patch("app.api.posts.feed.process_and_save_image", return_value=True)
def test_create_post_with_mocked_image(
    mock_process, client: TestClient, session: Session, test_user: User
):
    # ✅ ИСПРАВЛЕНО
    authorize_client(client, test_user.id) # type: ignore

    fake_file = io.BytesIO(b"fake_image_bytes")
    fake_file.name = "family_photo.jpg"

    response = client.post(
        "/posts/create",
        data={"content": "Смотрите, какое фото!"},
        files=[("files", (fake_file.name, fake_file, "image/jpeg"))],
        headers={"HX-Request": "true"}
    )

    assert response.status_code == 200
    mock_process.assert_called()


def test_toggle_like(client: TestClient, session: Session, test_user: User): 
    # ✅ ИСПРАВЛЕНО
    authorize_client(client, test_user.id) # type: ignore

    post = Post(content="Пост для лайка", author_id=test_user.id) # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # 1. Ставим лайк
    response_like = client.post(
        f"/posts/{post.id}/like", 
        json={"reaction": "❤️"},
        headers={"HX-Request": "true"}
    )
    # Если возвращается 401 — значит authorize_client не прокинул куку
    assert response_like.status_code == 200 
    
    data = response_like.json()
    assert data["status"] == "liked"

    session.expire_all()
    like_in_db = session.exec(
        select(PostLike).where(PostLike.post_id == post.id)
    ).first()
    assert like_in_db is not None


def test_comment_on_post(client: TestClient, session: Session, test_user: User):
    # ✅ ИСПРАВЛЕНО
    authorize_client(client, test_user.id) # type: ignore

    post = Post(content="Обсуждаем планы", author_id=test_user.id) # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # Оставляем комментарий (HTMX запрос)
    response = client.post(
        f"/posts/{post.id}/comment", 
        data={"content": "Отличная идея, я за!"},
        headers={"HX-Request": "true"}
    )
    assert response.status_code == 200

    session.expire_all()
    comment = session.exec(select(Comment).where(Comment.post_id == post.id)).first()
    assert comment is not None
    assert comment.content == "Отличная идея, я за!"