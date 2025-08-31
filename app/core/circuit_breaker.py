import time
from collections import defaultdict

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = defaultdict(int)
        self.last_failure_time = defaultdict(float)
        self.open_until = defaultdict(float)

    def allow_request(self, backend: str) -> bool:
        now = time.time()
        if self.open_until[backend] > now:
            return False  # circuit is open
        return True

    def record_success(self, backend: str):
        self.failure_count[backend] = 0
        self.open_until[backend] = 0

    def record_failure(self, backend: str):
        now = time.time()
        self.failure_count[backend] += 1
        self.last_failure_time[backend] = now
        if self.failure_count[backend] >= self.failure_threshold:
            self.open_until[backend] = now + self.recovery_time
    
    def get_status(self) -> dict[str, str]:
        now = time.time()
        status = {}
        for backend in set(self.failure_count.keys()) | set(self.open_until.keys()):
            if self.open_until[backend] > now:
                status[backend] = "open"
            else:
                status[backend] = "closed"
        return status

