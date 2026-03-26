import httpx
from app.config import settings
from app.logger import log_error

class SentinelBot:
    """Голос FamilyBook в Telegram. Отвечает за алерты и уведомления."""
    
    def __init__(self):
        # Берем данные из твоего обновленного config.py
        self.api_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        self.admin_id = settings.ADMIN_CHAT_ID

    async def send_alert(self, message: str, level: str = "INFO"):
        """Отправка системного сообщения администратору."""
        # Выбираем иконку в зависимости от серьезности
        icons = {
            "INFO": "ℹ️",
            "SECURITY": "🛡️",  # Для Honeypot и попыток взлома
            "ERROR": "🚨",     # Для ошибок 400/403
            "CRITICAL": "🔥"   # Для падения сервера 500
        }
        icon = icons.get(level, "💬")

        payload = {
            "chat_id": self.admin_id,
            "text": f"{icon} **FB SENTINEL: {level}**\n\n{message}",
            "parse_mode": "Markdown"
        }

        try:
            async with httpx.AsyncClient() as client:
                # Ставим небольшой тайм-аут, чтобы бот не вешал сервер, если Telegram тормозит
                response = await client.post(self.api_url, json=payload, timeout=5.0)
                response.raise_for_status()
        except Exception as e:
            # Если бот не смог отправить сообщение, пишем в лог, чтобы не потерять инфу
            log_error("BOT_ERROR", f"Не удалось отправить уведомление: {e}")

# Создаем один экземпляр, который будем импортировать везде
bot_alert = SentinelBot()