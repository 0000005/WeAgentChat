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
        if key in self.data.store:
            self.data.expire[key] = time.time() + time_sec
            return True
        return False
        
    async def incrby(self, key, value=1):
        self._check_expiry(key)
        current = self.data.store.get(key, 0)
        try:
            current = int(current)
        except ValueError:
            current = 0 
        
        new_val = current + value
        self.data.store[key] = new_val 
        return new_val

    async def eval(self, script, numkeys, *keys_and_args):
        # Mocking the specific Lua script used in buffer_background.py
        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]
        
        if "redis.call" in script and "get" in script and "del" in script:
            # Assume it's the unlock script
            if len(keys) >= 1 and len(args) >= 1:
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
