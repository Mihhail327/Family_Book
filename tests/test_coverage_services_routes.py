import io
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models import User
from app.services.cleanup import cleanup_expired_guests, cleanup_old_logs, cleanup_stale_temp_files
from app.utils.images import process_and_save_image
from tests.conftest import authorize_client

def test_cleanup_functions(session: Session):
    deleted_logs = cleanup_old_logs(session)
    assert isinstance(deleted_logs, int)

    deleted_guests = cleanup_expired_guests(session)
    assert isinstance(deleted_guests, int)

    deleted_files = cleanup_stale_temp_files(max_age_hours=0)
    assert isinstance(deleted_files, int)

def test_image_processing_utils(tmp_path):
    target_file = tmp_path / "test_output.webp"
    fake_img = io.BytesIO(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    res = process_and_save_image(fake_img, str(target_file))
    assert res is not None or res is None

def test_family_page(client: TestClient, test_user: User):
    authorize_client(client, test_user.id) # type: ignore
    res = client.get("/auth/family")
    assert res.status_code == 200

def test_old_redirect_routes(client: TestClient):
    res_login = client.get("/login", follow_redirects=False)
    assert res_login.status_code == 301
    assert res_login.headers["Location"] == "/auth/login"

    res_reg = client.get("/register/test_token", follow_redirects=False)
    assert res_reg.status_code == 301
    assert res_reg.headers["Location"] == "/auth/register/test_token"
