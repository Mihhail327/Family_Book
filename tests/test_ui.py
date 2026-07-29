from fastapi.testclient import TestClient

def test_login_glass_ui(client: TestClient):
    """Проверка рендеринга элементов Glassmorphism на странице входа"""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "glass-card" in response.text
    assert "display_name" in response.text

def test_mobile_adaptive_elements(client: TestClient):
    """Проверка наличия мобильных и адаптивных стилей в верстке"""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "md:hidden" in response.text or "flex" in response.text
    assert "FamilyBook" in response.text or "Летопись" in response.text