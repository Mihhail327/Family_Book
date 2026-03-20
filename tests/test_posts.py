import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User, Post, PostLike, Comment
from tests.conftest import login_client_fix


def test_create_and_read_post(client: TestClient, session: Session, test_user: User, login_client_fix):
    login_client_fix(client, test_user)

    # 1. Создаем пост
    response = client.post(
        "/posts/create",
        data={
            "content": "Первая тестовая история в Family_Book!", 
            "is_gift": "false"
        },
        follow_redirects=True
    )
    assert response.status_code == 200 
    
    # 2. Проверяем БД (это главная проверка надежности)
    session.expire_all()
    # Важно: подтягиваем пост заново из базы
    post = session.exec(select(Post).where(Post.author_id == test_user.id)).first()
    
    assert post is not None
    assert post.content == "Первая тестовая история в Family_Book!"
    
    # 3. Проверяем наличие Flash-сообщения (подтверждаем, что фронт ответил)
    assert "История успешно добавлена" in response.text


@patch("app.api.posts.feed.process_and_save_image", return_value=True)
def test_create_post_with_mocked_image(
    mock_process, client: TestClient, session: Session, test_user: User
):
    login_client_fix(client, test_user)

    fake_file = io.BytesIO(b"fake_image_bytes")
    fake_file.name = "family_photo.jpg"

    response = client.post(
        "/posts/create",
        data={"content": "Смотрите, какое фото!"},
        files=[("files", (fake_file.name, fake_file, "image/jpeg"))],
        follow_redirects=True
    )

    assert response.status_code == 200
    mock_process.assert_called_once()


def test_toggle_like(client, session, test_user, login_client_fix): 
    login_client_fix(client, test_user)

    assert test_user.id is not None
    post = Post(content="Пост для лайка", author_id=test_user.id)
    session.add(post)
    session.commit()
    session.refresh(post)

    # 1. Ставим лайк (теперь это API запрос с JSON)
    # ✅ ИСПРАВЛЕНО: Передаем обязательный reaction
    response_like = client.post(
        f"/posts/{post.id}/like", 
        json={"reaction": "❤️"}
    )
    assert response_like.status_code == 200 # ✅ ИСПРАВЛЕНО: Теперь ждем 200 OK (JSON)
    
    data = response_like.json()
    assert data["status"] == "liked"
    assert data["likes_count"] == 1

    session.expire_all()
    like_in_db = session.exec(
        select(PostLike).where(PostLike.post_id == post.id)
    ).first()
    assert like_in_db is not None
    assert like_in_db.reaction_type == "❤️"

    # 2. Убираем лайк (повторный клик тем же эмодзи)
    response_unlike = client.post(
        f"/posts/{post.id}/like", 
        json={"reaction": "❤️"}
    )
    assert response_unlike.json()["status"] == "unliked"
    
    session.expire_all()
    like_removed = session.exec(
        select(PostLike).where(PostLike.post_id == post.id)
    ).first()
    assert like_removed is None


def test_comment_on_post(client: TestClient, session: Session, test_user: User):
    login_client_fix(client, test_user)

    assert test_user.id is not None
    post = Post(content="Обсуждаем планы на выходные", author_id=test_user.id)
    session.add(post)
    session.commit()
    session.refresh(post)

    # Оставляем комментарий
    response = client.post(
        f"/posts/{post.id}/comment", 
        data={"content": "Отличная идея, я за!"},
        follow_redirects=True
    )
    assert response.status_code == 200

    session.expire_all()
    comment = session.exec(select(Comment).where(Comment.post_id == post.id)).first()
    assert comment is not None
    assert comment.content == "Отличная идея, я за!"
    assert comment.author_id == test_user.id