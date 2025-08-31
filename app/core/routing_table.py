
from typing import Optional

class PathRouter:
    def __init__(self, route_table: dict[str, str]):
        self.route_table = route_table

    def match(self, path: str) -> Optional[tuple[str, dict]]:
        for route_prefix, config in self.route_table.items():
            if path.startswith(route_prefix):
                backend = config["backend"]
                return backend, config
        return None, None
