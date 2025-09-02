import time

class InMemoryRateLimiter:
    def __init__(self, limit: int, window_ms: int = 10000):
        self.limit = limit
        self.window = window_ms
        self.buckets = {}  # identity -> [start_time, count]

    async def allow(self, identity: str) -> bool:
        now = int(time.time())
        bucket = self.buckets.get(identity)

        if not bucket or now - bucket[0] >= self.window:
            self.buckets[identity] = [now, 1]
            return True, self.retry_after(identity)

        if bucket[1] < self.limit:
            bucket[1] += 1
            return True, self.retry_after(identity)

        return False, self.retry_after(identity)

    def retry_after(self, identity: str) -> int:
        bucket = self.buckets.get(identity)
        if not bucket:
            return 0
        return max(0, self.window - (int(time.time()) - bucket[0]))

    async def remaining(self, identity: str) -> int:
        bucket = self.buckets.get(identity)
        if not bucket:
            return self.limit
        return max(0, self.limit - bucket[1])

