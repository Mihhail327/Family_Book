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


@patch("app.core.celery_app.process_and_save_image", return_value=True)
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


def test_nested_comments_and_deletion(client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore

    post = Post(content="Пост для обсуждения", author_id=test_user.id) # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # 1. Добавляем родительский комментарий
    res_parent = client.post(
        f"/posts/{post.id}/comment",
        data={"content": "Родительский комментарий"},
        headers={"HX-Request": "true"}
    )
    assert res_parent.status_code == 200

    session.expire_all()
    parent_comment = session.exec(select(Comment).where(Comment.parent_id == None)).first()
    assert parent_comment is not None

    # 2. Отвечаем на комментарий
    res_child = client.post(
        f"/posts/{post.id}/comment",
        data={"content": "Ответ на комментарий", "parent_id": parent_comment.id},
        headers={"HX-Request": "true"}
    )
    assert res_child.status_code == 200

    session.expire_all()
    child_comment = session.exec(select(Comment).where(Comment.parent_id == parent_comment.id)).first()
    assert child_comment is not None
    assert child_comment.content == "Ответ на комментарий"

    # 3. Удаляем родительский комментарий и проверяем каскадное удаление ответа
    res_delete = client.delete(
        f"/posts/comments/{parent_comment.id}"
    )
    assert res_delete.status_code == 200

    session.expire_all()
    deleted_parent = session.get(Comment, parent_comment.id)
    deleted_child = session.get(Comment, child_comment.id)
    assert deleted_parent is None
    assert deleted_child is None


@patch("app.core.celery_app.process_image_task.delay", return_value=None)
def test_pre_upload_media(mock_delay, client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    
    fake_file = io.BytesIO(b"another_fake_image_bytes")
    fake_file.name = "vacation.jpg"
    
    response = client.post(
        "/api/media/upload",
        files=[("file", (fake_file.name, fake_file, "image/jpeg"))]
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "url" in data
    assert data["url"].startswith("/static/uploads/posts/")
    assert data["url"].endswith(".webp")
    mock_delay.assert_called()