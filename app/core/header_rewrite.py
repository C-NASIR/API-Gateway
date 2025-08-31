from typing import Optional
from starlette.types import Scope

class HeaderRewriter:
    def __init__(
        self,
        remove: Optional[list[str]] = None,
        set_: Optional[dict[str, str]] = None,
        append: Optional[dict[str, str]] = None
    ) -> None:
        self.remove = set(h.lower() for h in (remove or []))
        self.set = {k.lower(): v for k, v in (set_ or {}).items()}
        self.append = {k.lower(): v for k, v in (append or {}).items()}

    def rewrite(self, headers: list[tuple[bytes, bytes]], scope: Scope, trace_id: Optional[str] = None) -> dict[str, str]:
        hdict = {k.decode().lower(): v.decode() for k, v in headers}
        for h in self.remove:
            hdict.pop(h, None)
        for k, v in self.set.items():
            hdict[k] = v
        for k, v in self.append.items():
            hdict.setdefault(k, v)

        if trace_id:
            hdict["x-trace-id"] = trace_id

        return hdict
