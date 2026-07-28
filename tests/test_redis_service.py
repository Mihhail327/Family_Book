import pytest
from app.core.redis import ResilientRedis

@pytest.mark.asyncio
async def test_resilient_redis_fake_fallback():
    redis = ResilientRedis()
    
    # 1. Проверяем работу set / get
    await redis.set("test_key", "hello_world")
    val = await redis.get("test_key")
    assert val == b"hello_world"
    
    # 2. Проверяем incr
    c1 = await redis.incr("counter")
    assert c1 == 1
    c2 = await redis.incr("counter")
    assert c2 == 2
    
    # 3. Проверяем exists
    assert await redis.exists("counter") == 1
    assert await redis.exists("non_existent") == 0

@pytest.mark.asyncio
async def test_resilient_redis_next_client_boundary():
    redis = ResilientRedis()
    # Имитируем ошибку подключения
    redis._next_client()
    assert redis._use_fake is True
    # Повторный вызов не ломает состояние
    redis._next_client()
    assert redis._use_fake is True
