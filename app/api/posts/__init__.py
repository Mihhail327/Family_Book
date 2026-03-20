from fastapi import APIRouter
from . import feed, comments, likes

router = APIRouter()

# Собираем эндпоинты контента
router.include_router(feed.router)
router.include_router(comments.router)
router.include_router(likes.router)