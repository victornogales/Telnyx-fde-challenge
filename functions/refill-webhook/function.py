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
_TELNYX_API_KEY = os.environ.get("KV_API_KEY") or os.environ.get("TELNYX_API_KEY", "")
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
    def __init__(self, client: httpx.AsyncClient, namespace_id: str, cache_ttl_secs: float = 3.0) -> None:
        self._client = client
        self._namespace_id = namespace_id
        self._cache_ttl_secs = cache_ttl_secs
        self._flag_cache: dict[str, tuple[str, float]] = {}

    def _url(self, key: str) -> str:
        encoded = urllib.parse.quote(key, safe="")
        return f"{_API_BASE}/{self._namespace_id}/keys/{encoded}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_TELNYX_API_KEY}",
            "Content-Type": "application/json",
        }

    async def get(self, key: str, timeout: float = 5.0) -> tuple[str | None, str]:
        """Returns (value, source) where source is one of ok, 404, timeout, error."""
        kv_timer = _Timer()
        attempt = 0

        async def _do_get():
            nonlocal attempt
            attempt += 1
            resp = await self._client.get(
                self._url(key),
                headers=self._headers(),
                timeout=timeout,
            )
            if resp.status_code == 404:
                _log(
                    "kv_get",
                    key=key,
                    attempt=attempt,
                    status=404,
                    ms=kv_timer.ms(),
                    source="404",
                )
                return None, "404"
            resp.raise_for_status()
            data = resp.json()
            if "value" in data:
                return str(data["value"]), "ok"
            return data.get("data", {}).get("value"), "ok"

        try:
            return await _retry_async(_do_get, attempts=3, base_delay_ms=100)
        except asyncio.TimeoutError:
            _log(
                "kv_get",
                key=key,
                attempt=attempt,
                status=-1,
                ms=kv_timer.ms(),
                source="timeout",
            )
            return None, "timeout"
        except Exception as exc:
            _log(
                "kv_get",
                key=key,
                attempt=attempt,
                status=-1,
                ms=kv_timer.ms(),
                source="error",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None, "error"

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

    async def get_flag(
        self, name: str, default: str = "false", flag_sources: dict[str, str] | None = None
    ) -> str:
        now = time.monotonic()
        cached = self._flag_cache.get(name)
        if cached is not None:
            value, cached_at = cached
            if now - cached_at < self._cache_ttl_secs:
                if flag_sources is not None:
                    flag_sources[name] = "cache"
                return value
        value, source = await self.get(f"flag/{name}")
        if value is None:
            if flag_sources is not None:
                flag_sources[name] = f"default_{source}"
            return default
        self._flag_cache[name] = (value, now)
        if flag_sources is not None:
            flag_sources[name] = source
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


_DEPLOY_TS = "2026-11-11T20:00Z"

_KV_NAMESPACE_ID = os.environ.get("KV_NAMESPACE_ID", "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee")

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
    "closing_message": "Thanks for calling Maple Pharmacy. We appreciate your call. Take care, and have a great day.",
    "pharmacy_hours": "8am to 8pm, Monday to Saturday",
    "transfer_fail_message": "I couldn't reach a pharmacist right now. Thanks for your call, goodbye.",
}


class App:
    def start(self, env: dict[str, str] | None = None) -> None:
        """Warm-up: schedule background KV read to warm up HTTPS connection pool.
        The framework calls start() synchronously, so we fire-and-forget a task."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._warmup())
        except Exception:
            pass

    async def _warmup(self) -> None:
        try:
            kv = _get_kv()
            await kv.get("flag/after_hours_mode", timeout=5.0)
        except Exception:
            pass

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

        # After-hours notice will be appended after flags are fetched
        _after_hours_notice: str = ""

        # Fetch flags and gateway state concurrently WITHOUT outer timeout
        # Each inner task has its own timeout; partial success is acceptable
        try:
            flags, gateway_result = await self._fetch_all(
                kv, caller, trace_id, call_control_id, skip_record_call=duplicate
            )
        except Exception as exc:
            _log(
                "webhook",
                trace_id=trace_id,
                caller_key=caller,
                outcome="fetch_error",
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

        # After-hours: prepend closed notice to greeting so caller hears it immediately
        if vars_out.get("after_hours_mode") == "true":
            hours = vars_out.get("pharmacy_hours", "8am to 8pm, Monday to Saturday")
            vars_out["greeting_suffix"] += (
                f" Please note, Maple Pharmacy is currently closed. Our hours are {hours}."
            )

        # DEBUG: expose raw KV read results and build version
        vars_out["_deploy_ts"] = _DEPLOY_TS
        vars_out["_debug_flags_raw"] = json.dumps(flags)
        vars_out["_debug_kv_ns"] = _KV_NAMESPACE_ID
        vars_out["_debug_call_control"] = call_control_id
        vars_out["_debug_flags_error"] = gateway_result.get("_flags_error", "")

        # Transfer failure message contextual on after-hours
        _pharmacy_hours = vars_out.get("pharmacy_hours", "8am to 8pm, Monday to Saturday")
        if vars_out.get("after_hours_mode") == "true":
            vars_out["transfer_fail_message"] = (
                f"I couldn't reach a pharmacist right now, as we're currently closed. "
                f"Please call back during opening hours: {_pharmacy_hours}. "
                "Thanks for your call, goodbye."
            )
        else:
            vars_out["transfer_fail_message"] = (
                "I couldn't reach a pharmacist right now. "
                "Please call back during business hours. "
                "Thanks for your call, goodbye."
            )

        # Closing message contextual on after-hours
        if vars_out.get("after_hours_mode") == "true":
            vars_out["closing_message"] = (
                f"Thanks for calling Maple Pharmacy. We're currently closed. "
                f"Please call back during business hours: {_pharmacy_hours}. "
                "Take care, and have a great day."
            )
        else:
            vars_out["closing_message"] = (
                "Thanks for calling Maple Pharmacy. We appreciate your call. "
                "Take care, and have a great day."
            )

        # Determine degraded / over-budget
        degraded = (
            gateway_result.get("_flags_error", "")
            or vars_out["after_hours_mode"] != flags.get("after_hours_mode", "true")
        )
        _log(
            "webhook",
            trace_id=trace_id,
            caller_key=caller,
            known=True,
            event_type=event_type,
            call_control_id=call_control_id,
            synthetic=call_control_id.startswith(("raw-test", "poll", "debug", "test")) if call_control_id else False,
            locked=gateway_result.get("locked"),
            flag_sources=gateway_result.get("_flag_sources", {}),
            dv_after_hours_mode=vars_out["after_hours_mode"],
            degraded=degraded,
            over_budget=timer.ms() > 1300,
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
        flag_sources: dict[str, str] = {}

        async def _flags() -> dict[str, str]:
            refills, after_hours = await asyncio.gather(
                asyncio.wait_for(
                    kv.get_flag("refills_enabled", "true", flag_sources=flag_sources),
                    timeout=1.5,
                ),
                asyncio.wait_for(
                    kv.get_flag("after_hours_mode", "false", flag_sources=flag_sources),
                    timeout=1.5,
                ),
                return_exceptions=True,
            )
            out: dict[str, str] = {}
            if isinstance(refills, Exception):
                out["refills_enabled"] = "true"
            else:
                out["refills_enabled"] = refills or "true"
            if isinstance(after_hours, Exception):
                out["after_hours_mode"] = "false"
            else:
                out["after_hours_mode"] = after_hours or "false"
            return out

        async def _gateway() -> dict[str, Any]:
            if skip_record_call:
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
                    timeout=0.5,
                ),
                timeout=0.5,
            )
            return {
                **(result or {}),
                "_gateway_ms": gw_timer.ms(),
            }

        flags_task = asyncio.create_task(_flags())
        gateway_task = asyncio.create_task(_gateway())

        done, pending = await asyncio.wait(
            [flags_task, gateway_task],
            return_when=asyncio.ALL_COMPLETED,
        )
        for task in pending:
            task.cancel()

        flags: dict[str, str] = {}
        gateway_result: dict[str, Any] = {}
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
        gateway_result["_flag_sources"] = flag_sources
        flags_error = ""
        if excs:
            flags_error = f"{type(excs[0]).__name__}: {excs[0]}"
        gateway_result["_flags_error"] = flags_error

        _log(
            "fetch_all_result",
            flags=flags,
            flag_sources=flag_sources,
            gateway_keys=list(gateway_result.keys()),
            exc_count=len(excs),
        )

        return flags, gateway_result
        for task in pending:
            task.cancel()

        _log("fetch_all_done", flags_task_done=flags_task in done, gateway_task_done=gateway_task in done)

        excs = []
        flags_error = ""
        for task in done:
            try:
                val = task.result()
                if task is flags_task:
                    flags = val
                else:
                    gateway_result = val
            except Exception as exc:
                excs.append(exc)
                if task is flags_task:
                    flags_error = f"{type(exc).__name__}: {exc}"

        gateway_result["_kv_ms"] = kv_timer.ms()
        gateway_result["_flags_error"] = flags_error

        if gateway_result.get("callCount") is None:
            raise excs[0] if excs else Exception("gateway_missing")

        _log("fetch_all_result", flags=flags, gateway_keys=list(gateway_result.keys()), exc_count=len(excs))

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
