import httpx
from typing import List, Optional
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
        # Храним сопоставление user_id -> список сокетов (у одного юзера может быть открыто несколько вкладок/устройств)
        self.active_connections: dict[int, List[WebSocket]] = {}
        # Список для неавторизованных/гостевых сокетов
        self.anonymous_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, user_id: Optional[int] = None):
        await websocket.accept()
        if user_id is not None:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
        else:
            self.anonymous_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: Optional[int] = None):
        if user_id is not None and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        elif websocket in self.anonymous_connections:
            self.anonymous_connections.remove(websocket)

    async def broadcast(self, data: dict, user_id: Optional[int] = None):
        """Отправить сообщение конкретному пользователю или вообще всем, кто онлайн"""
        if user_id is not None:
            # Отправляем только конкретному адресату
            connections = self.active_connections.get(user_id, [])
            for connection in connections:
                try:
                    await connection.send_json(data)
                except Exception:
                    continue
        else:
            # Отправляем всем авторизованным пользователям
            for connections_list in list(self.active_connections.values()):
                for connection in connections_list:
                    try:
                        await connection.send_json(data)
                    except Exception:
                        continue
            # И всем анонимным/гостевым сессиям
            for connection in self.anonymous_connections:
                try:
                    await connection.send_json(data)
                except Exception:
                    continue

# --- ИНИЦИАЛИЗАЦИЯ (Экспортируем оба инструмента) ---
bot_alert = SentinelBot()
manager = ConnectionManager()