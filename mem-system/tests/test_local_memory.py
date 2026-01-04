import pytest
import asyncio
from memobase_server.memory_store import LocalMemoryCache

@pytest.mark.asyncio
async def test_local_memory_cache_basic_ops():
    cache = LocalMemoryCache()
    
    # Test set/get
    await cache.set("test_key", "test_value")
    val = await cache.get("test_key")
    assert val == "test_value"
    
    # Test delete
    await cache.delete("test_key")
    val = await cache.get("test_key")
    assert val is None

@pytest.mark.asyncio
async def test_local_memory_cache_expiry():
    cache = LocalMemoryCache()
    
    # Test expire
    await cache.set("expire_key", "expire_value", ex=0.1)
    val = await cache.get("expire_key")
    assert val == "expire_value"
    
    await asyncio.sleep(0.2)
    val = await cache.get("expire_key")
    assert val is None

@pytest.mark.asyncio
async def test_local_memory_cache_nx():
    cache = LocalMemoryCache()
    
    # Test nx (not exists)
    res = await cache.set("nx_key", "val1", nx=True)
    assert res is True
    val = await cache.get("nx_key")
    assert val == "val1"
    
    res = await cache.set("nx_key", "val2", nx=True)
    assert res is False
    val = await cache.get("nx_key")
    assert val == "val1"

@pytest.mark.asyncio
async def test_local_memory_cache_list_ops():
    cache = LocalMemoryCache()
    
    # Test rpush, llen, lpop
    await cache.rpush("list_key", "item1", "item2")
    length = await cache.llen("list_key")
    assert length == 2
    
    item = await cache.lpop("list_key")
    assert item == "item1"
    
    length = await cache.llen("list_key")
    assert length == 1
    
    item = await cache.lpop("list_key")
    assert item == "item2"
    
    item = await cache.lpop("list_key")
    assert item is None

@pytest.mark.asyncio
async def test_local_memory_cache_incrby():
    cache = LocalMemoryCache()
    
    # Test incrby
    await cache.set("counter", 10)
    val = await cache.incrby("counter", 5)
    assert val == 15
    
    val = await cache.get("counter")
    assert val == 15
    
    # Test incrby on non-existent key
    val = await cache.incrby("new_counter", 1)
    assert val == 1
    
@pytest.mark.asyncio
async def test_local_memory_cache_eval():
    cache = LocalMemoryCache()
    
    # Test eval (mocked lock release)
    key = "lock_key"
    lock_val = "uuid-123"
    
    await cache.set(key, lock_val)
    
    # Script matching the one in buffer_background.py
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    
    # Correct release
    res = await cache.eval(script, 1, key, lock_val)
    assert res == 1
    val = await cache.get(key)
    assert val is None
    
    # Incorrect release (key doesn't exist or value mismatch)
    await cache.set(key, lock_val)
    res = await cache.eval(script, 1, key, "wrong-uuid")
    assert res == 0
    val = await cache.get(key)
    assert val == lock_val
