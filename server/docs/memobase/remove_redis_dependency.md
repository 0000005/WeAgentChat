# Remove Redis Dependency

This document outlines the plan to remove the Redis dependency from the `mem-system` project and replace it with an in-memory solution. This change simplifies the deployment architecture for local development and single-instance deployments.

## Rationale

Redis is currently used for:
1.  **LLM Caching:** Storing context IDs for Doubao LLM.
2.  **Profile Caching:** Caching user profiles to reduce database load.
3.  **Background Buffer Processing:**
    - Queueing tasks (`rpush`/`lpop`).
    - Distributed locking (`set nx=True`, Lua scripts).
4.  **Auth/Token:** Caching project secrets and status.
5.  **Telemetry:** Capture key logic.

For a standalone or local setup, these requirements can be met with process-local memory (Python dictionaries and lists), assuming the application runs as a single instance (or the limitations of non-shared memory between workers are accepted).

## Implementation Plan

### 1. Create `LocalMemoryCache` Class

We will create a class `LocalMemoryCache` in `memobase_server/connectors.py` (or a new file `memobase_server/memory_store.py` if preferred, but keeping it close to the connector logic is fine for now).

**Requirements for `LocalMemoryCache`:**
- **Shared State:** Must use class-level attributes or a singleton pattern to share data across different "client" instances.
- **API Compatibility:** Must implement the subset of `redis.asyncio.Redis` methods used in the project:
    - `get(key)`
    - `set(key, value, ex=None, nx=False)`
    - `delete(key)`
    - `expire(key, time)`
    - `rpush(key, *values)`
    - `lpop(key)`
    - `llen(key)`
    - `ping()`
    - `eval(script, numkeys, *keys_and_args)` (specifically handling the lock release Lua script)
    - Context manager support (`async with ...`).

### 2. Refactor `memobase_server/connectors.py`

- **Remove** `redis` import and `REDIS_URL` dependency.
- **Remove** `init_redis_pool`.
- **Modify** `get_redis_client` to return an instance of `LocalMemoryCache`.
- **Remove** `redis_health_check` logic (or make it always return True).

### 3. Updates to Dependent Files

The following files use `get_redis_client` and should work transparently if the mock is implemented correctly, but they should be verified:

- `memobase_server/telemetry/capture_key.py`
- `memobase_server/llms/doubao_cache_llm.py`
- `memobase_server/controllers/profile.py`
- `memobase_server/controllers/buffer_background.py` (Crucial: relies on list operations and locking)
- `memobase_server/auth/token.py`
- `memobase_server/api_layer/chore.py` (Update health check logic if necessary)
- `api.py` (Remove `init_redis_pool` call)

### 4. Dependency Management

- Remove `redis` from `pyproject.toml`.
- Update `uv.lock`.

## Detailed `LocalMemoryCache` Implementation

```python
import time
import asyncio

class LocalMemoryStore:
    """Singleton storage for local memory cache simulation"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalMemoryStore, cls).__new__(cls)
            cls._instance.store = {}
            cls._instance.expire = {}
            cls._instance.lists = {}
        return cls._instance

class LocalMemoryCache:
    def __init__(self):
        self.data = LocalMemoryStore()

    async def get(self, key):
        self._check_expiry(key)
        return self.data.store.get(key)

    async def set(self, key, value, ex=None, nx=False):
        self._check_expiry(key)
        
        if nx and key in self.data.store:
            return False
            
        self.data.store[key] = value
        if ex:
            self.data.expire[key] = time.time() + ex
        elif key in self.data.expire:
            del self.data.expire[key]
            
        return True

    async def delete(self, key):
        self._delete(key)
        return 1

    async def rpush(self, key, *values):
        if key not in self.data.lists:
            self.data.lists[key] = []
        self.data.lists[key].extend(values)
        return len(self.data.lists[key])

    async def lpop(self, key):
        if key in self.data.lists and self.data.lists[key]:
            return self.data.lists[key].pop(0)
        return None

    async def llen(self, key):
        return len(self.data.lists.get(key, []))

    async def expire(self, key, time_sec):
        # Only supporting expiry for simple keys for now, as per usage
        if key in self.data.store:
            self.data.expire[key] = time.time() + time_sec
            return True
        return False

    async def eval(self, script, numkeys, *keys_and_args):
        # Mocking the specific Lua script used in buffer_background.py
        # script: if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end
        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]
        
        if "redis.call" in script and "get" in script and "del" in script:
            # Assume it's the unlock script
            key = keys[0]
            val = args[0]
            current = await self.get(key)
            if current == val:
                await self.delete(key)
                return 1
            return 0
        return None

    async def ping(self):
        return True

    def _check_expiry(self, key):
        if key in self.data.expire and time.time() > self.data.expire[key]:
            self._delete(key)

    def _delete(self, key):
        if key in self.data.store: del self.data.store[key]
        if key in self.data.expire: del self.data.expire[key]
        if key in self.data.lists: del self.data.lists[key]
        
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def aclose(self):
        pass
```

## Considerations

- **Multi-Process:** This solution **will not work** if the application runs with multiple worker processes (e.g., `uvicorn ... --workers 4`), as the memory is not shared. It is suitable for `workers=1` (default).
- **Persistence:** All data (locks, queues, caches) is lost on restart. This is generally acceptable for caching and transient locks, but ensures the background queue should be drained or resilient to data loss (the `BufferZone` status in DB is the source of truth, so retries might handle it, but in-memory queue loss means pending tasks are dropped until re-queued).