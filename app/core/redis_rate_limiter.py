import time
import redis.asyncio as redis
from typing import Optional


LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- cleanup old requests
redis.call("ZREMRANGEBYSCORE", key, "-inf", now - window)

-- count active
local count = redis.call("ZCARD", key)
if count >= limit then
  local ttl = redis.call("PTTL", key)
  return ttl
end

-- add current request
redis.call("ZADD", key, now, now)
redis.call("PEXPIRE", key, window)
return 0
"""

class RedisRateLimiter:
    def __init__(self, redis_client: redis.Redis, limit: int, window_ms: int = 10000):
        self.redis = redis_client
        self.limit = limit
        self.window_ms = window_ms
        self.script_sha = None

    async def _now(self) -> int:
        return int(time.time() * 1000)

    async def load_script(self):
        if not self.script_sha:
            self.script_sha = await self.redis.script_load(LUA_SCRIPT)

    async def allow(self, identity: str) -> tuple[bool, Optional[int]]:
        await self.load_script()
        now = await self._now()
        try:
            ttl = await self.redis.evalsha(self.script_sha,1,identity,now,
                                            self.window_ms, self.limit)
            if int(ttl) > 0:
                return False, int(ttl / 1000)
            return True, None
        except redis.ResponseError as e:
            if "NOSCRIPT" in str(e):
                self.script_sha = None
                return await self.allow(identity)
            raise

    async def remaining(self, identity: str) -> int:
        now = await self._now()
        await self.redis.zremrangebyscore(identity, "-inf", now - self.window_ms)
        return max(0, self.limit - await self.redis.zcard(identity))
