
class PathRouter:
    def __init__(self, route_table: dict[str, str]):
        self.route_table = route_table

    def match(self, path: str) -> str | None:
        # Longest prefix match
        best_prefix = ""
        for prefix in self.route_table:
            if path.startswith(prefix) and len(prefix) > len(best_prefix):
                best_prefix = prefix
        return self.route_table.get(best_prefix)
