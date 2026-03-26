import pytest
import asyncio
from app.services.notifier import bot_alert
from app.config import settings

@pytest.mark.asyncio
async def test():
    print(f"📡 Пробую докричаться до админа {settings.ADMIN_CHAT_ID}...")
    await bot_alert.send_alert("FamilyBook Sentinel v3.0.0 на связи! Проверка системы прошла успешно. ✅", level="INFO")
    print("🚀 Сообщение отправлено! Проверь Telegram.")

if __name__ == "__main__":
    asyncio.run(test())