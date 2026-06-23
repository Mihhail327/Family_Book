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


def test_delete_post(client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore

    # 1. Create a post
    post = Post(content="История для удаления", author_id=test_user.id)
    session.add(post)
    session.commit()
    session.refresh(post)

    post_id = post.id

    # 2. Delete the post using HX-Request
    response = client.post(
        f"/posts/delete/{post_id}",
        headers={"HX-Request": "true"}
    )
    
    assert response.status_code == 200
    assert "HX-Redirect" not in response.headers
    assert "HX-Refresh" not in response.headers

    session.expire_all()
    deleted_post = session.get(Post, post_id)
    assert deleted_post is None


def test_delete_post_from_detail_page(client: TestClient, session: Session, test_user: User):
    authorize_client(client, test_user.id) # type: ignore

    # 1. Create a post
    post = Post(content="История для удаления из деталей", author_id=test_user.id)
    session.add(post)
    session.commit()
    session.refresh(post)

    post_id = post.id

    # 2. Delete the post simulating being on the post detail page
    response = client.post(
        f"/posts/delete/{post_id}",
        headers={
            "HX-Request": "true",
            "HX-Current-URL": f"http://localhost:8000/posts/{post_id}"
        }
    )
    
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/"

    session.expire_all()
    deleted_post = session.get(Post, post_id)
    assert deleted_post is None


def test_comment_on_another_user_post_triggers_notification(client: TestClient, session: Session, test_user: User):
    # Create another user (the author of the post)
    other_user = User(username="other_author", display_name="Other Author", hashed_password="123")
    session.add(other_user)
    session.commit()
    session.refresh(other_user)

    # other_user creates a post
    post = Post(content="История другого автора", author_id=other_user.id)
    session.add(post)
    session.commit()
    session.refresh(post)

    # We authorize the client as test_user
    authorize_client(client, test_user.id)

    # test_user comments on other_user's post
    response = client.post(
        f"/posts/{post.id}/comment",
        data={"content": "Отличная история!"},
        headers={"HX-Request": "true"}
    )
    assert response.status_code == 200

    # Verify that a Notification was created for other_user
    session.expire_all()
    from app.models import Notification
    notifications = session.exec(
        select(Notification).where(Notification.user_id == other_user.id)
    ).all()
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.category == "info"
    assert "прокомментировал вашу историю" in notification.message
    assert notification.link == f"/posts/{post.id}"


def test_get_and_mark_read_notifications(client: TestClient, session: Session, test_user: User):
    import asyncio
    from app.core.redis import redis_client
    
    # Clear fake Redis data to isolate test state
    if hasattr(redis_client, "_fake"):
        redis_client._fake._data.clear()
        
    redis_key = f"user:{test_user.id}:unread_notifications_count"
    
    # Create some notifications for test_user
    from app.models import Notification
    n1 = Notification(user_id=test_user.id, title="Title 1", message="Msg 1", category="info", is_read=False)
    n2 = Notification(user_id=test_user.id, title="Title 2", message="Msg 2", category="success", is_read=False)
    session.add(n1)
    session.add(n2)
    session.commit()

    authorize_client(client, test_user.id)

    # Redis key shouldn't exist initially
    assert asyncio.run(redis_client.get(redis_key)) is None

    # 1. Fetch notifications - triggers middleware which warms up cache
    response = client.get("/push/notifications")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Title 2" # Sorted desc by date/id
    assert data[0]["is_read"] is False

    # Redis key should be warmed up by the middleware to 2
    val = asyncio.run(redis_client.get(redis_key))
    assert val == b"2"

    # Now, creating a notification for test_user should atomically increment it
    from app.services.notification import create_system_notification
    asyncio.run(create_system_notification(
        session=session,
        title="Title 3",
        message="Msg 3",
        user_id=test_user.id,
        category="info"
    ))
    
    val = asyncio.run(redis_client.get(redis_key))
    assert val == b"3"

    # 2. Mark them as read
    response_read = client.post("/push/notifications/mark-read")
    assert response_read.status_code == 200
    assert response_read.json() == {"status": "success"}

    # Redis key should be set to "0"
    val = asyncio.run(redis_client.get(redis_key))
    assert val == b"0"

    # 3. Verify in DB
    session.expire_all()
    db_notifs = session.exec(select(Notification).where(Notification.user_id == test_user.id)).all()
    assert all(n.is_read is True for n in db_notifs)