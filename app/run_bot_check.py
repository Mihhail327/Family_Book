import asyncio
from app.services.notifier import bot_alert
from app.config import settings

async def check():
    print(f"📡 Проверка связи... Токен: {settings.BOT_TOKEN[:10]}***")
    # Здесь будет реальная отправка
    await bot_alert.send_alert("🚀 **FamilyBook Sentinel v3.0**\nСистема оповещений активирована! Я на страже. 😎", level="SECURITY")
    print("✅ Готово! Проверяй Telegram.")

if __name__ == "__main__":
    asyncio.run(check())