
from typing import Optional
from asyncio import Lock
import time

class PathRouter:
    def __init__(self, route_table: dict[str, str]):
        self.route_table = route_table
        self.last_reload = 0
        self.lock = Lock()

    def match(self, path: str) -> Optional[tuple[str, dict]]:
        for route_prefix, config in self.route_table.items():
            if path.startswith(route_prefix):
                backend = config["backend"]
                return backend, config
        return None, None

    async def update_route_table(self, new_routes: dict):
        async with self.lock:
            self.route_table = new_routes
            self.last_reload = time.time()
