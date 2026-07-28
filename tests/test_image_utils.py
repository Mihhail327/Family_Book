from pathlib import Path
from app.utils.images import resolve_static_path
from app.config import settings

def test_resolve_static_path_variants():
    # 1. URL с ведущим слэшем /static/
    p1 = resolve_static_path("/static/uploads/avatars/test.webp")
    assert str(p1).endswith(str(Path("uploads/avatars/test.webp")))

    # 2. URL с префиксом static/ без ведущего слэша
    p2 = resolve_static_path("static/uploads/posts/demo.webp")
    assert str(p2).endswith(str(Path("uploads/posts/demo.webp")))

    # 3. Прямой путь /uploads/...
    p3 = resolve_static_path("/uploads/avatars/pic.webp")
    assert str(p3).endswith(str(Path("uploads/avatars/pic.webp")))
