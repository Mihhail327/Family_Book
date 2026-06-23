import logging
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from app.config import settings

logger = logging.getLogger("redis_client")

class FakeRedis:
    def __init__(self):
        self._data = {}

    async def get(self, key: str):
        val = self._data.get(key)
        if val is not None:
            return str(val).encode('utf-8')
        return None

    async def set(self, key: str, value: str, ex: int = None):
        self._data[key] = str(value)
        return True

    async def incr(self, key: str):
        val = self._data.get(key, 0)
        try:
            val = int(val)
        except (ValueError, TypeError):
            val = 0
        val += 1
        self._data[key] = str(val)
        return val

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def ping(self):
        return True

class ResilientRedis:
    def __init__(self):
        self._fake = FakeRedis()
        self._redis = None
        self._use_fake = False
        
        if settings.ENV == "testing":
            self._use_fake = True
            return

        # Setup primary redis client
        url = settings.CELERY_BROKER_URL
        self._urls = [url]
        if "redis://redis" in url:
            self._urls.append(url.replace("redis://redis", "redis://localhost"))
        
        self._current_url_index = 0
        self._init_client()

    def _init_client(self):
        if self._current_url_index < len(self._urls):
            url = self._urls[self._current_url_index]
            self._redis = aioredis.from_url(url, socket_timeout=1.0, decode_responses=False)
        else:
            self._use_fake = True

    async def get(self, key: str):
        if self._use_fake:
            return await self._fake.get(key)
        try:
            return await self._redis.get(key)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis get error: {e}. Falling back or trying next host.")
            self._current_url_index += 1
            self._init_client()
            return await self.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        if self._use_fake:
            return await self._fake.set(key, value, ex)
        try:
            return await self._redis.set(key, value, ex=ex)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis set error: {e}. Falling back or trying next host.")
            self._current_url_index += 1
            self._init_client()
            return await self.set(key, value, ex)

    async def incr(self, key: str):
        if self._use_fake:
            return await self._fake.incr(key)
        try:
            return await self._redis.incr(key)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis incr error: {e}. Falling back or trying next host.")
            self._current_url_index += 1
            self._init_client()
            return await self.incr(key)

    async def exists(self, key: str) -> int:
        if self._use_fake:
            return await self._fake.exists(key)
        try:
            return await self._redis.exists(key)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(f"Redis exists error: {e}. Falling back or trying next host.")
            self._current_url_index += 1
            self._init_client()
            return await self.exists(key)

redis_client = ResilientRedis()
