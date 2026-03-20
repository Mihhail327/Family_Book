from fastapi import APIRouter

from . import login, register, profile, guest

router = APIRouter()

# Собираем все мелкие роутеры в один большой доменный
router.include_router(login.router)
router.include_router(register.router)
router.include_router(profile.router)
router.include_router(guest.router)