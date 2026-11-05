import json
import os
from typing import Any

import httpx

from .log import log

_INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")


class SessionError(Exception):
    pass


async def call(
    client: httpx.AsyncClient,
    method: str,
    caller_key: str,
    args: dict[str, Any],
    trace_id: str,
    timeout: float = 7.0,
) -> Any:
    url = f"{os.environ.get('CALLER_SESSION_URL', '')}/rpc"
    payload = {
        "method": method,
        "caller_key": caller_key,
        "args": args,
    }
    try:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": _INTERNAL_TOKEN,
                "X-Trace-Id": trace_id,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise SessionError(data.get("error", "gateway error"))
        return data.get("result")
    except SessionError:
        raise
    except Exception as exc:
        log("session_client_error", method=method, caller_key=caller_key, trace_id=trace_id, error=str(exc))
        raise SessionError(str(exc))
