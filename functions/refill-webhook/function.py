import asyncio
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Shared helpers (inlined because the platform build supports only flat modules)
# ---------------------------------------------------------------------------

_FUNC_NAME = os.environ.get("FUNC_NAME", "unknown")
_API_BASE = "https://api.telnyx.com/v2/storage/kvs"
_TELNYX_API_KEY = os.environ.get("TELNYX_API_KEY", "")
_INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")
_CALLER_SESSION_URL = os.environ.get("CALLER_SESSION_URL", "")


def _log(event: str, **fields: Any) -> None:
    line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": "info",
        "fn": _FUNC_NAME,
        "event": event,
    }
    line.update(fields)
    print(json.dumps(line, default=str), flush=True)


class _Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)


def _caller_key(e164: str) -> str:
    digest = hashlib.sha256(e164.encode("utf-8")).hexdigest()
    return digest[:16]


def _new_trace_id() -> str:
    return "tr_" + secrets.token_hex(6)


_PATIENTS: dict[str, str] = {
    "+15550000001": "Maria",
    "+442045202115": "James",
    "+15551112222": "David",
    "+15552223333": "Sarah",
    "+15553334444": "Robert",
}


def _find_patient_name(e164: str) -> str:
    return _PATIENTS.get(e164, "")


class _SessionError(Exception):
    pass


def _new_trace_id() -> str:
    return "tr_" + secrets.token_hex(6)


# In-memory dedup cache for call_control_id (prevents double-counting on webhook redelivery)
_DEDUP_WINDOW_SECS = 300.0
_seen_call_ids: dict[str, float] = {}


def _is_duplicate_call(call_control_id: str | None) -> bool:
    if not call_control_id:
        return False
    now = time.monotonic()
    # Prune old entries
    cutoff = now - _DEDUP_WINDOW_SECS
    stale = [k for k, v in _seen_call_ids.items() if v < cutoff]
    for k in stale:
        del _seen_call_ids[k]
    # Check
    if call_control_id in _seen_call_ids:
        return True
    _seen_call_ids[call_control_id] = now
    return False


async def _retry_async(coro_factory, *, attempts: int = 3, base_delay_ms: int = 100):
    """Retry an async callable with exponential backoff."""
    for i in range(attempts):
        try:
            return await coro_factory()
        except Exception:
            if i == attempts - 1:
                raise
            await asyncio.sleep((2 ** i * base_delay_ms) / 1000.0)


class _SessionError(Exception):
    pass


async def _session_call(
    client: httpx.AsyncClient,
    method: str,
    caller_key: str,
    args: dict[str, Any],
    trace_id: str,
    timeout: float = 7.0,
) -> Any:
    url = f"{_CALLER_SESSION_URL}/rpc"
    payload = {
        "method": method,
        "caller_key": caller_key,
        "args": args,
    }

    async def _do_call():
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
            raise _SessionError(data.get("error", "gateway error"))
        return data.get("result")

    try:
        return await _retry_async(_do_call, attempts=3, base_delay_ms=100)
    except _SessionError:
        raise
    except Exception as exc:
        _log("session_client_error", method=method, caller_key=caller_key, trace_id=trace_id, error=str(exc))
        raise _SessionError(str(exc))


class _KV:
    def __init__(self, client: httpx.AsyncClient, namespace_id: str) -> None:
        self._client = client
        self._ns = namespace_id
        self._flag_cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl_secs = 15.0

    def _url(self, key: str) -> str:
        encoded = urllib.parse.quote(key, safe="")
        return f"{_API_BASE}/{self._ns}/keys/{encoded}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_TELNYX_API_KEY}",
            "Content-Type": "application/json",
        }

    async def get(self, key: str, timeout: float = 5.0) -> str | None:
        async def _do_get():
            resp = await self._client.get(
                self._url(key),
                headers=self._headers(),
                timeout=timeout,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("value")

        try:
            return await _retry_async(_do_get, attempts=3, base_delay_ms=100)
        except Exception as exc:
            _log("kv_get_error", key=key, error_type=type(exc).__name__, error=str(exc))
            return None

    async def put(
        self,
        key: str,
        value: str | bytes,
        ttl_secs: int | None = None,
        timeout: float = 5.0,
    ) -> bool:
        async def _do_put():
            url = self._url(key)
            if ttl_secs is not None:
                url = f"{url}?ttl_secs={ttl_secs}"
            payload = {"value": value}
            resp = await self._client.put(
                url,
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return True

        try:
            return await _retry_async(_do_put, attempts=3, base_delay_ms=100)
        except Exception as exc:
            _log("kv_put_error", key=key, error_type=type(exc).__name__, error=str(exc))
            return False

    async def get_flag(self, name: str, default: str = "false") -> str:
        now = time.monotonic()
        cached = self._flag_cache.get(name)
        if cached is not None:
            value, cached_at = cached
            if now - cached_at < self._cache_ttl_secs:
                return value
        value = await self.get(f"flag/{name}")
        if value is None:
            value = default
        self._flag_cache[name] = (value, now)
        return value


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------

_HTTP_CLIENT: httpx.AsyncClient | None = None
_KV_INSTANCE: _KV | None = None


def _get_kv() -> _KV:
    global _KV_INSTANCE
    if _KV_INSTANCE is None:
        _KV_INSTANCE = _KV(_client(), _KV_NAMESPACE_ID)
    return _KV_INSTANCE


def _client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient()
    return _HTTP_CLIENT


_KV_NAMESPACE_ID = os.environ.get("KV_NAMESPACE_ID", "")

SAFE_DEFAULTS: dict[str, str] = {
    "trace_id": "",
    "is_known_caller": "false",
    "patient_first_name": "",
    "greeting_suffix": "",
    "call_count": "0",
    "last_intent": "",
    "account_locked": "false",
    "attempts_left": "3",
    "refills_enabled": "true",
    "after_hours_mode": "false",
    "open_refill_count": "0",
    "pharmacy_hours": "8am to 8pm, Monday to Saturday",
}


class App:
    async def handle(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        timer = _Timer()
        trace_id = _new_trace_id()

        if method != "POST":
            await self._send_json(send, 405, {"error": "method not allowed"})
            return

        # Read body
        body_parts: list[bytes] = []
        while True:
            message = await receive()
            if message.get("type") == "http.request":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            else:
                break
        raw_body = b"".join(body_parts)

        try:
            payload = json.loads(raw_body.decode("utf-8-sig"))
        except Exception:
            payload = {}

        event_data = payload.get("data", {})
        event_type = event_data.get("event_type", "")
        call_payload = event_data.get("payload", {})
        end_user = call_payload.get("telnyx_end_user_target", "")
        call_control_id = call_payload.get("call_control_id", "")

        if not end_user:
            _log("webhook", trace_id=trace_id, outcome="missing_caller", total_ms=timer.ms())
            await self._send_dynamic_vars(send, SAFE_DEFAULTS, trace_id)
            return

        caller = _caller_key(end_user)
        kv = _get_kv()
        duplicate = _is_duplicate_call(call_control_id)

        # Resolve patient name immediately (instant, no RPC)
        patient_name = _find_patient_name(end_user)

        # Partial defaults that always include the name and greeting, even on timeout
        PARTIAL_DEFAULTS = dict(SAFE_DEFAULTS)
        PARTIAL_DEFAULTS["patient_first_name"] = patient_name
        if patient_name:
            PARTIAL_DEFAULTS["greeting_suffix"] = f" Hi {patient_name}, how can I help you today?"
        else:
            PARTIAL_DEFAULTS["greeting_suffix"] = " How can I help you today?"

        try:
            result = await asyncio.wait_for(
                self._fetch_all(kv, caller, trace_id, call_control_id, skip_record_call=duplicate),
                timeout=1.0,
            )
            flags, gateway_result = result
        except asyncio.TimeoutError:
            _log(
                "webhook",
                trace_id=trace_id,
                caller_key=caller,
                outcome="fallback",
                patient_name=patient_name,
                error="overall_timeout",
                total_ms=timer.ms(),
            )
            await self._send_dynamic_vars(send, PARTIAL_DEFAULTS, trace_id)
            return
        except Exception as exc:
            _log(
                "webhook",
                trace_id=trace_id,
                caller_key=caller,
                outcome="fallback",
                patient_name=patient_name,
                error_type=type(exc).__name__,
                error=str(exc),
                total_ms=timer.ms(),
            )
            await self._send_dynamic_vars(send, PARTIAL_DEFAULTS, trace_id)
            return

        vars_out = dict(PARTIAL_DEFAULTS)
        vars_out["trace_id"] = trace_id
        vars_out["is_known_caller"] = "true"
        vars_out["call_count"] = str(gateway_result.get("callCount", 0))
        vars_out["account_locked"] = "true" if gateway_result.get("locked") else "false"
        failed = gateway_result.get("failedAttempts", 0)
        vars_out["attempts_left"] = str(max(0, 3 - failed))
        vars_out["open_refill_count"] = str(gateway_result.get("openRefills", 0))
        if gateway_result.get("lastIntent"):
            vars_out["last_intent"] = str(gateway_result["lastIntent"])

        # Flags from KV
        vars_out["refills_enabled"] = flags.get("refills_enabled", "true")
        vars_out["after_hours_mode"] = flags.get("after_hours_mode", "false")

        _log(
            "webhook",
            trace_id=trace_id,
            caller_key=caller,
            known=True,
            locked=gateway_result.get("locked"),
            flags=flags,
            kv_ms=gateway_result.get("_kv_ms", 0),
            gateway_ms=gateway_result.get("_gateway_ms", 0),
            total_ms=timer.ms(),
            outcome="ok",
        )
        await self._send_dynamic_vars(send, vars_out, trace_id)

    async def _fetch_all(
        self,
        kv: _KV,
        caller: str,
        trace_id: str,
        call_control_id: str,
        skip_record_call: bool = False,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        kv_timer = _Timer()
        gw_timer = _Timer()

        async def _flags() -> dict[str, str]:
            refills, after_hours = await asyncio.gather(
                asyncio.wait_for(kv.get_flag("refills_enabled", "true"), timeout=0.4),
                asyncio.wait_for(kv.get_flag("after_hours_mode", "false"), timeout=0.4),
            )
            return {
                "refills_enabled": refills or "true",
                "after_hours_mode": after_hours or "false",
            }

        async def _gateway() -> dict[str, Any]:
            if skip_record_call:
                # Idempotency: return a safe fallback so the rest of the handler works
                return {
                    "callCount": 0,
                    "locked": False,
                    "openRefills": 0,
                    "_gateway_ms": gw_timer.ms(),
                }
            client = _client()
            result = await asyncio.wait_for(
                _session_call(
                    client,
                    "recordCall",
                    caller,
                    {"traceId": trace_id, "callControlId": call_control_id},
                    trace_id,
                    timeout=0.7,
                ),
                timeout=0.7,
            )
            return {
                **(result or {}),
                "_gateway_ms": gw_timer.ms(),
            }

        flags_task = asyncio.create_task(_flags())
        gateway_task = asyncio.create_task(_gateway())

        flags: dict[str, str] = {}
        gateway_result: dict[str, Any] = {}

        done, pending = await asyncio.wait(
            [flags_task, gateway_task],
            return_when=asyncio.ALL_COMPLETED,
        )
        for task in pending:
            task.cancel()

        excs = []
        for task in done:
            try:
                val = task.result()
                if task is flags_task:
                    flags = val
                else:
                    gateway_result = val
            except Exception as exc:
                excs.append(exc)

        gateway_result["_kv_ms"] = kv_timer.ms()

        if gateway_result.get("callCount") is None:
            raise excs[0] if excs else Exception("gateway_missing")

        return flags, gateway_result

    async def _send_dynamic_vars(
        self, send: Any, variables: dict[str, str], trace_id: str
    ) -> None:
        body = json.dumps({"dynamic_variables": {**variables, "trace_id": trace_id}})
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": body.encode(),
        })

    async def _send_json(self, send: Any, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


def new():
    return App()
