from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User, Post, Comment
from tests.conftest import authorize_client

def test_add_and_delete_comment(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    post = Post(author_id=test_user.id, content="Тестовый пост для комментариев") # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # Добавление комментария
    res_add = client.post(f"/posts/{post.id}/comment", data={"content": "Отличная история!"}, follow_redirects=False)
    assert res_add.status_code == 303

    comment = session.query(Comment).filter(Comment.post_id == post.id).first()
    assert comment is not None
    assert comment.content == "Отличная история!"

    # Удаление комментария
    res_del = client.delete(f"/posts/comments/{comment.id}")
    assert res_del.status_code == 200

def test_toggle_like(client: TestClient, test_user: User, session: Session):
    authorize_client(client, test_user.id) # type: ignore
    
    post = Post(author_id=test_user.id, content="Тестовый пост для лайка") # type: ignore
    session.add(post)
    session.commit()
    session.refresh(post)

    # Ставим лайк
    res_like = client.post(f"/posts/{post.id}/like", json={"reaction": "❤️"})
    assert res_like.status_code == 200
    json_data = res_like.json()
    assert json_data["status"] == "liked"

    # Снимаем лайк
    res_unlike = client.post(f"/posts/{post.id}/like", json={"reaction": "❤️"})
    assert res_unlike.status_code == 200
    json_data_unlike = res_unlike.json()
    assert json_data_unlike["status"] == "unliked"
