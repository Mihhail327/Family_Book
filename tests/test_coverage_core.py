import pytest
from app.core.redis import redis_client
from app.database import create_db_and_tables

@pytest.mark.asyncio
async def test_redis_operations():
    # Фейковый Redis в режиме тестирования
    await redis_client.set("test_key", "test_value", ex=60)
    val = await redis_client.get("test_key")
    if isinstance(val, bytes):
        val = val.decode()
    assert val == "test_value"

    exists = await redis_client.exists("test_key")
    assert bool(exists) is True

    await redis_client.incr("test_counter")
    c = await redis_client.get("test_counter")
    if isinstance(c, bytes):
        c = c.decode()
    assert c == "1"

def test_init_db_execution():
    create_db_and_tables()
