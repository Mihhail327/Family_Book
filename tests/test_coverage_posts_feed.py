import io
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User, Post
from tests.conftest import authorize_client

def test_feed_pagination_and_search(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    # Создаем тестовые посты
    p1 = Post(author_id=test_user.id, content="Первая семейная история #новости", tags="новости") # type: ignore
    p2 = Post(author_id=test_user.id, content="Вторая семейная история #архив", tags="архив") # type: ignore
    session.add_all([p1, p2])
    session.commit()

    # GET главной страницы
    res = client.get("/")
    assert res.status_code == 200
    assert "Первая семейная история" in res.text

    # Просмотр конкретного поста
    res_detail = client.get(f"/posts/{p1.id}")
    assert res_detail.status_code == 200
    assert "Первая семейная история" in res_detail.text

def test_create_post_with_image(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    fake_img = io.BytesIO(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    files = [("files", ("photo.gif", fake_img, "image/gif"))]
    data = {"content": "Пост с фотографией #фото"}
    
    res = client.post("/posts/create", data=data, files=files, follow_redirects=False)
    assert res.status_code in [200, 303]

def test_edit_and_delete_post(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    post = Post(author_id=test_user.id, content="Старый контент") # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # Редактирование
    res_edit = client.post(f"/posts/edit/{post.id}", data={"content": "Обновленный контент #новое"}, follow_redirects=False)
    assert res_edit.status_code == 303

    # Удаление
    res_del = client.post(f"/posts/delete/{post.id}", follow_redirects=False)
    assert res_del.status_code == 303
