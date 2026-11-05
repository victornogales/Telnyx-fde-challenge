import json
import os
import time
from typing import Any

_FUNC_NAME = os.environ.get("FUNC_NAME", "unknown")


def log(event: str, **fields: Any) -> None:
    line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": "info",
        "fn": _FUNC_NAME,
        "event": event,
    }
    line.update(fields)
    print(json.dumps(line, default=str), flush=True)


class Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
