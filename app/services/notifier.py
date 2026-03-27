import httpx
from typing import List
from fastapi import WebSocket
from app.config import settings
from app.logger import log_error

# --- 1. ТВОЙ БОТ (Уже есть, оставляем без изменений) ---
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

# --- 2. НОВЫЙ МЕНЕДЖЕР (Для уведомлений на сайте) ---
class ConnectionManager:
    def __init__(self):
        # Храним просто список всех активных сокетов
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        """Отправить сообщение всем, кто онлайн"""
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                # Если сокет «протух», просто идем дальше
                continue

# --- ИНИЦИАЛИЗАЦИЯ (Экспортируем оба инструмента) ---
bot_alert = SentinelBot()
manager = ConnectionManager()