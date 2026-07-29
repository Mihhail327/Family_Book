import io
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User, Post
from tests.conftest import authorize_client

def test_post_creation_errors(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    
    # 1. Пустой пост без текста и картинок
    res_empty = client.post("/posts/create", data={"content": ""}, follow_redirects=False)
    assert res_empty.status_code == 303

    # 2. Слишком длинный пост (> 2000 символов)
    res_long = client.post("/posts/create", data={"content": "x" * 2005}, follow_redirects=False)
    assert res_long.status_code == 303

def test_delete_other_user_post_security_trigger(client: TestClient, test_user: User, session: Session):
    # Владелец поста
    owner = User(username="owner_user", display_name="Владелец", hashed_password="pwd", role="user")
    session.add(owner)
    session.commit()
    session.refresh(owner)

    post = Post(author_id=owner.id, content="Чужой пост")
    session.add(post)
    session.commit()
    session.refresh(post)

    # Авторизуемся под чужим обычным юзером
    authorize_client(client, test_user.id) # type: ignore
    res_del = client.post(f"/posts/delete/{post.id}", follow_redirects=False)
    assert res_del.status_code == 303

def test_media_upload_api(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    
    fake_img = io.BytesIO(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    files = {"file": ("test.gif", fake_img, "image/gif")}
    
    res = client.post("/api/media/upload", files=files)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "url" in res.json()

def test_edit_post_errors(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    # 1. Редактирование несуществующего поста
    res_nonexistent = client.post("/posts/edit/99999", data={"content": "Текст"}, follow_redirects=False)
    assert res_nonexistent.status_code == 303

    # 2. Слишком длинное редактирование
    post = Post(author_id=test_user.id, content="Короткий текст")
    session.add(post)
    session.commit()
    session.refresh(post)

    res_too_long = client.post(f"/posts/edit/{post.id}", data={"content": "a" * 2005}, follow_redirects=False)
    assert res_too_long.status_code == 303
