import asyncio
import hashlib
import hmac
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
# KV API key: try explicit KV_API_KEY secret first, fall back to TELNYX_API_KEY from [telnyx] binding
_KV_API_KEY = os.environ.get("KV_API_KEY") or os.environ.get("TELNYX_API_KEY", "")
_INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN", "")
_CALLER_SESSION_URL = os.environ.get("CALLER_SESSION_URL", "")
_MCP_TOKEN = os.environ.get("MCP_TOKEN", "")


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


async def _retry_async(coro_factory, *, attempts: int = 3, base_delay_ms: int = 100):
    """Retry an async callable with exponential backoff."""
    for i in range(attempts):
        try:
            return await coro_factory()
        except Exception:
            if i == attempts - 1:
                raise
            await asyncio.sleep((2 ** i * base_delay_ms) / 1000.0)


def _caller_key(e164: str) -> str:
    digest = hashlib.sha256(e164.encode("utf-8")).hexdigest()
    return digest[:16]


def _new_trace_id() -> str:
    return "tr_" + secrets.token_hex(6)


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
            "Authorization": f"Bearer {_KV_API_KEY}",
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
            return resp.text

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
            content = value if isinstance(value, bytes) else value.encode("utf-8")
            resp = await self._client.put(
                url,
                headers=self._headers(),
                content=content,
                timeout=timeout,
            )
            resp.raise_for_status()
            return True

        try:
            return await _retry_async(_do_put, attempts=3, base_delay_ms=100)
        except Exception as exc:
            _log("kv_put_error", key=key, error_type=type(exc).__name__, error=str(exc))
            return False


# ---------------------------------------------------------------------------
# Patient data (inline — flat module constraint)
# ---------------------------------------------------------------------------

_PATIENTS: dict[str, dict] = {
    "+15550000001": {
        "first_name": "Maria",
        "dob": "1962-03-15",
        "prescriptions": [
            {
                "id": "rx-mar-001",
                "name": "Lisinopril",
                "strength": "10 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-mar-002",
                "name": "Oxycodone",
                "strength": "5 mg",
                "refills_left": 0,
                "controlled": True,
            },
            {
                "id": "rx-mar-003",
                "name": "Metformin",
                "strength": "500 mg",
                "refills_left": 1,
                "controlled": False,
            },
        ],
    },
    "+442045202115": {
        "first_name": "James",
        "dob": "1985-07-22",
        "prescriptions": [
            {
                "id": "rx-jam-001",
                "name": "Atorvastatin",
                "strength": "20 mg",
                "refills_left": 3,
                "controlled": False,
            },
            {
                "id": "rx-jam-002",
                "name": "Amoxicillin",
                "strength": "500 mg",
                "refills_left": 0,
                "controlled": False,
            },
        ],
    },
    "+15551112222": {
        "first_name": "David",
        "dob": "1978-11-03",
        "prescriptions": [
            {
                "id": "rx-dav-001",
                "name": "Sertraline",
                "strength": "50 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-dav-002",
                "name": "Albuterol",
                "strength": "90 mcg inhaler",
                "refills_left": 1,
                "controlled": False,
            },
        ],
    },
    "+15552223333": {
        "first_name": "Sarah",
        "dob": "1991-06-08",
        "prescriptions": [
            {
                "id": "rx-sar-001",
                "name": "Levothyroxine",
                "strength": "75 mcg",
                "refills_left": 5,
                "controlled": False,
            },
            {
                "id": "rx-sar-002",
                "name": "Ibuprofen",
                "strength": "400 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-sar-003",
                "name": "Lorazepam",
                "strength": "1 mg",
                "refills_left": 1,
                "controlled": True,
            },
        ],
    },
    "+15553334444": {
        "first_name": "Robert",
        "dob": "1955-09-19",
        "prescriptions": [
            {
                "id": "rx-rob-001",
                "name": "Warfarin",
                "strength": "5 mg",
                "refills_left": 0,
                "controlled": False,
            },
            {
                "id": "rx-rob-002",
                "name": "Furosemide",
                "strength": "40 mg",
                "refills_left": 3,
                "controlled": False,
            },
        ],
    },
}


def _find_patient(e164: str) -> dict | None:
    return _PATIENTS.get(e164)


# ---------------------------------------------------------------------------
# openFDA helper
# ---------------------------------------------------------------------------

async def _fetch_openfda(
    client: httpx.AsyncClient,
    drug_name: str,
    trace_id: str,
) -> dict[str, str] | None:
    """Query openFDA for drug label info. Returns {brand_name, generic_name, purpose}."""
    timer = _Timer()
    search = drug_name.replace(" ", "+")
    url = (
        f"https://api.fda.gov/drug/label.json"
        f"?search=openfda.generic_name:\"{search}\"+openfda.brand_name:\"{search}\""
        f"&limit=1"
    )
    try:
        resp = await client.get(url, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        result = results[0]
        openfda = result.get("openfda", {})
        brand = _first(openfda.get("brand_name", []))
        generic = _first(openfda.get("generic_name", []))
        purpose = result.get("purpose") or result.get("indications_and_usage") or ""
        if isinstance(purpose, list):
            purpose = " ".join(purpose)
        purpose = purpose[:300].strip()
        _log("openfda_lookup", trace_id=trace_id, drug=drug_name, upstream_ms=timer.ms(), found=True)
        return {"brand_name": brand or drug_name, "generic_name": generic or drug_name, "purpose": purpose or "No description available."}
    except Exception as exc:
        _log("openfda_lookup", trace_id=trace_id, drug=drug_name, upstream_ms=timer.ms(), found=False, error=str(exc))
        return None


def _first(seq: list[str]) -> str:
    return seq[0] if seq else ""


# ---------------------------------------------------------------------------
# Pharmacy info helper
# ---------------------------------------------------------------------------

_PHARMACY_INFO = {
    "name": "Maple Pharmacy",
    "address": "123 Maple Street, London",
    "phone": "+44 20 4520 2115",
    "hours": "8am to 8pm, Monday to Saturday. Closed Sunday.",
}


async def _get_pharmacy_info(kv: _KV) -> dict[str, str]:
    """Return pharmacy info, preferring KV cache."""
    cached = await kv.get("cache/pharmacy_info", timeout=2.0)
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    return _PHARMACY_INFO


# ---------------------------------------------------------------------------
# MCP JSON-RPC handler
# ---------------------------------------------------------------------------

_MCP_VERSION = "0.1.0"


TOOLS = [
    {
        "name": "verify_identity",
        "description": (
            "Verify the caller's identity by checking their date of birth. "
            "Call this right after the caller provides their DOB. "
            "Returns whether verification succeeded, how many attempts remain, "
            "and whether the account is locked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caller": {"type": "string", "description": "The caller's E.164 phone number"},
                "dob": {"type": "string", "description": "Date of birth in YYYY-MM-DD format (extracted from what the caller said)"},
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": ["caller", "dob"],
        },
    },
    {
        "name": "list_prescriptions",
        "description": (
            "List the caller's refill-eligible prescriptions. "
            "Only works after the caller has been verified. "
            "Returns medication names, strengths, and how many refills are left. "
            "Controlled substances with zero refills are excluded."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caller": {"type": "string", "description": "The caller's E.164 phone number"},
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": ["caller"],
        },
    },
    {
        "name": "request_refill",
        "description": (
            "Submit a refill request for one prescription. "
            "Only works after the caller has been verified. "
            "Returns a refill confirmation ID and estimated ready time. "
            "Call this only after the caller has explicitly confirmed which prescription they want."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caller": {"type": "string", "description": "The caller's E.164 phone number"},
                "rx_id": {"type": "string", "description": "The prescription ID to refill (e.g. rx-mar-001)"},
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": ["caller", "rx_id"],
        },
    },
    {
        "name": "get_refill_status",
        "description": (
            "Check the status of the caller's open refill requests. "
            "Only works after the caller has been verified. "
            "Returns a list of refills with statuses like submitted or ready."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caller": {"type": "string", "description": "The caller's E.164 phone number"},
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": ["caller"],
        },
    },
    {
        "name": "get_medication_info",
        "description": (
            "Look up general information about a medication by name. "
            "Returns the brand name, generic name, and what it's used for. "
            "Use this when the caller asks what a medication is for or what it does. "
            "Do NOT use this for medical advice — keep answers to label text only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Medication name (e.g. Lisinopril)"},
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_pharmacy_info",
        "description": (
            "Get pharmacy hours, address, and phone number. "
            "Use this when the caller asks about opening times, location, or how to reach a pharmacist."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "trace_id": {"type": "string", "description": "Optional trace ID for logging; omit if unknown."},
            },
            "required": [],
        },
    },
]


def _jsonrpc_error(id_val: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_val,
        "error": {"code": code, "message": message},
    }


def _jsonrpc_result(id_val: Any, result: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_val,
        "result": result,
    }


_SUPPORTED_PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]


class MCPHandler:
    def __init__(self, kv: _KV, http_client: httpx.AsyncClient) -> None:
        self._kv = kv
        self._client = http_client

    async def handle(self, body: bytes, header_names: list[str], trace_id: str) -> tuple[int, dict[str, Any] | None]:
        timer = _Timer()
        try:
            request = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            _log(
                "mcp_request",
                trace_id=trace_id,
                method="parse_error",
                outcome="bad_json",
                latency_ms=timer.ms(),
            )
            return 200, _jsonrpc_error(None, -32700, "Parse error")

        # Batch or non-dict body → Invalid Request
        if not isinstance(request, dict):
            _log(
                "mcp_request",
                trace_id=trace_id,
                method="invalid_request",
                outcome="not_dict",
                latency_ms=timer.ms(),
            )
            return 200, _jsonrpc_error(None, -32600, "Invalid Request")

        method = request.get("method", "")
        rpc_id = request.get("id")
        params = request.get("params", {}) if isinstance(request.get("params"), dict) else {}
        meta = params.get("_meta") if isinstance(params, dict) else None

        _log(
            "mcp_request",
            trace_id=trace_id,
            method=method,
            rpc_id=rpc_id,
            header_names=header_names,
            meta=meta,
            latency_ms=timer.ms(),
        )

        # Notification (no id) → 202 for any method
        if "id" not in request:
            return 202, None

        if method == "initialize":
            result = await self._handle_initialize(params)
            return 200, _jsonrpc_result(rpc_id, result)

        if method == "notifications/initialized":
            return 202, None

        if method == "ping":
            return 200, _jsonrpc_result(rpc_id, {})

        if method == "tools/list":
            return 200, _jsonrpc_result(rpc_id, {"tools": TOOLS})

        if method == "tools/call":
            result = await self._handle_tool_call(params, trace_id)
            return 200, _jsonrpc_result(rpc_id, result)

        return 200, _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        client_version = params.get("protocolVersion", "")
        if client_version in _SUPPORTED_PROTOCOL_VERSIONS:
            reply_version = client_version
        else:
            reply_version = _SUPPORTED_PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": reply_version,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "refill-mcp",
                "version": _MCP_VERSION,
            },
        }

    async def _is_caller_verified(self, caller: str, trace_id: str) -> bool:
        """Check whether the caller has a valid verification in the actor."""
        ckey = _caller_key(caller)
        try:
            result = await _session_call(
                self._client,
                "isVerified",
                ckey,
                {"traceId": trace_id},
                trace_id,
                timeout=3.0,
            )
            return bool(result)
        except Exception:
            return False

    async def _handle_tool_call(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}
        meta = params.get("_meta") if isinstance(params, dict) else None
        conversation_id = meta.get("telnyx_conversation_id") if isinstance(meta, dict) else None

        # Resolve trace_id: use argument if present and real; otherwise fall back to request trace_id
        arg_trace_id = arguments.get("trace_id", "")
        if not arg_trace_id or "{{" in str(arg_trace_id):
            arg_trace_id = trace_id

        timer = _Timer()
        outcome = "ok"
        cache_status = None
        upstream_ms = None

        try:
            if name == "verify_identity":
                result = await self._tool_verify_identity(arguments, arg_trace_id)
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), latency_ms=timer.ms())
                return result["mcp_result"]

            if name == "list_prescriptions":
                result = await self._tool_list_prescriptions(arguments, arg_trace_id)
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), latency_ms=timer.ms())
                return result["mcp_result"]

            if name == "request_refill":
                result = await self._tool_request_refill(arguments, arg_trace_id)
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), latency_ms=timer.ms())
                return result["mcp_result"]

            if name == "get_refill_status":
                result = await self._tool_get_refill_status(arguments, arg_trace_id)
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), latency_ms=timer.ms())
                return result["mcp_result"]

            if name == "get_medication_info":
                result = await self._tool_get_medication_info(arguments, arg_trace_id)
                cache_status = result.get("cache")
                upstream_ms = result.get("upstream_ms")
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), cache=cache_status, upstream_ms=upstream_ms, latency_ms=timer.ms())
                return result["mcp_result"]

            if name == "get_pharmacy_info":
                result = await self._tool_get_pharmacy_info(arguments, arg_trace_id)
                _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome=result.get("outcome", "ok"), latency_ms=timer.ms())
                return result["mcp_result"]

            outcome = "unknown_tool"
            return self._error(f"Unknown tool: {name}")

        except Exception as exc:
            _log("mcp_tool", trace_id=arg_trace_id, tool=name, conversation_id=conversation_id, outcome="error", error=str(exc), latency_ms=timer.ms())
            return self._error(f"Internal error processing {name}. Please try again or ask for a pharmacist.")

    def _success(self, data: Any) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": json.dumps(data, default=str)}],
            "isError": False,
        }

    def _error(self, message: str) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": json.dumps({"error": message})}],
            "isError": True,
        }

    # -------------------------------------------------------------------
    # Tool implementations
    # -------------------------------------------------------------------

    async def _tool_verify_identity(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        caller = arguments.get("caller", "")
        dob = arguments.get("dob", "")
        patient = _find_patient(caller)
        ckey = _caller_key(caller)

        if not patient:
            return {
                "outcome": "not_found",
                "mcp_result": self._error("I don't have a record for this number. Let me connect you with a pharmacist."),
            }

        expected_dob = patient.get("dob", "")
        success = dob == expected_dob

        try:
            max_attempts_str = await self._kv.get("flag/max_verify_attempts", timeout=2.0)
            max_attempts = int(max_attempts_str or "3")
        except Exception:
            max_attempts = 3

        try:
            result = await _session_call(
                self._client,
                "recordVerificationAttempt",
                ckey,
                {"traceId": trace_id, "success": success, "maxAttempts": max_attempts},
                trace_id,
                timeout=3.0,
            )
            verified = result.get("verified", False)
            attempts_left = result.get("attemptsLeft", 0)
            locked = result.get("locked", False)
            return {
                "outcome": "ok",
                "mcp_result": self._success({
                    "verified": verified,
                    "attempts_left": attempts_left,
                    "locked": locked,
                "message": (
                    "Thank you, you're all set." if verified else
                    f"That doesn't match what I have. You have {attempts_left} more tries." if not locked else
                    "For your security, I can't continue this call. I'll connect you with a pharmacist."
                ),
                }),
            }
        except _SessionError:
            return {
                "outcome": "gateway_down",
                "mcp_result": self._error("I can't access your account right now. Please try again or ask for a pharmacist."),
            }

    async def _tool_list_prescriptions(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        caller = arguments.get("caller", "")
        if not await self._is_caller_verified(caller, trace_id):
            return {
                "outcome": "not_verified",
                "mcp_result": self._error("I need to verify your identity first. Please provide your date of birth."),
            }

        patient = _find_patient(caller)
        if not patient:
            return {
                "outcome": "not_found",
                "mcp_result": self._error("I don't have a record for this number."),
            }

        rx_list = []
        for rx in patient.get("prescriptions", []):
            # Exclude controlled substances with 0 refills
            if rx.get("controlled") and rx.get("refills_left", 0) <= 0:
                continue
            rx_list.append({
                "id": rx["id"],
                "name": rx["name"],
                "strength": rx["strength"],
                "refills_left": rx["refills_left"],
            })

        if not rx_list:
            return {
                "outcome": "ok",
                "mcp_result": self._success({
                    "prescriptions": [],
                    "message": "You don't have any prescriptions eligible for refill right now. Let me connect you with a pharmacist.",
                }),
            }

        return {
            "outcome": "ok",
            "mcp_result": self._success({
                "prescriptions": rx_list,
                "message": f"I found {len(rx_list)} prescription(s) available for refill.",
            }),
        }

    async def _tool_request_refill(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        caller = arguments.get("caller", "")
        rx_id = arguments.get("rx_id", "")

        if not await self._is_caller_verified(caller, trace_id):
            return {
                "outcome": "not_verified",
                "mcp_result": self._error("I need to verify your identity first."),
            }

        patient = _find_patient(caller)
        if not patient:
            return {
                "outcome": "not_found",
                "mcp_result": self._error("I don't have a record for this number."),
            }

        rx = None
        for r in patient.get("prescriptions", []):
            if r.get("id") == rx_id:
                rx = r
                break

        if not rx:
            return {
                "outcome": "not_found",
                "mcp_result": self._error(f"I couldn't find prescription {rx_id}."),
            }

        if rx.get("refills_left", 0) <= 0:
            return {
                "outcome": "not_eligible",
                "mcp_result": self._error(f"{rx['name']} has no refills remaining. A pharmacist can help with this."),
            }

        ckey = _caller_key(caller)
        try:
            result = await _session_call(
                self._client,
                "addRefill",
                ckey,
                {"traceId": trace_id, "rxId": rx_id},
                trace_id,
                timeout=3.0,
            )
            refill_id = result.get("refillId", "")
            status = result.get("status", "submitted")
            return {
                "outcome": "ok",
                "mcp_result": self._success({
                    "refill_id": refill_id,
                    "status": status,
                    "message": f"Your refill for {rx['name']} has been submitted. It will be ready in about 10 minutes.",
                }),
            }
        except _SessionError:
            return {
                "outcome": "gateway_down",
                "mcp_result": self._error("I can't access your account right now. Please try again or ask for a pharmacist."),
            }

    async def _tool_get_refill_status(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        caller = arguments.get("caller", "")
        if not await self._is_caller_verified(caller, trace_id):
            return {
                "outcome": "not_verified",
                "mcp_result": self._error("I need to verify your identity first."),
            }

        ckey = _caller_key(caller)
        try:
            result = await _session_call(
                self._client,
                "getRefills",
                ckey,
                {"traceId": trace_id},
                trace_id,
                timeout=3.0,
            )
            refills = result if isinstance(result, list) else []
            if not refills:
                return {
                    "outcome": "ok",
                    "mcp_result": self._success({
                        "refills": [],
                        "message": "You don't have any open refill requests right now.",
                    }),
                }
            return {
                "outcome": "ok",
                "mcp_result": self._success({
                    "refills": refills,
                    "message": f"You have {len(refills)} refill request(s).",
                }),
            }
        except _SessionError:
            return {
                "outcome": "gateway_down",
                "mcp_result": self._error("I can't access your account right now. Please try again or ask for a pharmacist."),
            }

    async def _tool_get_medication_info(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        name = arguments.get("name", "").strip()
        if not name:
            return {
                "outcome": "bad_arg",
                "mcp_result": self._error("Please tell me which medication you'd like to know about."),
            }

        normalized = name.lower().replace(" ", "-")
        cache_key = f"cache/fda/{normalized}"

        # Check KV cache
        cache_timer = _Timer()
        cached = await self._kv.get(cache_key, timeout=2.0)
        if cached:
            try:
                data = json.loads(cached)
                return {
                    "outcome": "ok",
                    "cache": "hit",
                    "mcp_result": self._success({
                        "name": name,
                        "brand_name": data.get("brand_name", name),
                        "generic_name": data.get("generic_name", name),
                        "purpose": data.get("purpose", "No description available."),
                    }),
                }
            except Exception:
                pass

        # Cache miss: call openFDA
        data = await _fetch_openfda(self._client, name, trace_id)
        if data:
            await self._kv.put(cache_key, json.dumps(data), ttl_secs=86400, timeout=3.0)
            return {
                "outcome": "ok",
                "cache": "miss",
                "upstream_ms": cache_timer.ms(),
                "mcp_result": self._success({
                    "name": name,
                    "brand_name": data["brand_name"],
                    "generic_name": data["generic_name"],
                    "purpose": data["purpose"],
                }),
            }

        return {
            "outcome": "not_found",
            "mcp_result": self._error(f"I don't have information about {name}. A pharmacist can tell you more."),
        }

    async def _tool_get_pharmacy_info(self, arguments: dict[str, Any], trace_id: str) -> dict[str, Any]:
        info = await _get_pharmacy_info(self._kv)
        return {
            "outcome": "ok",
            "mcp_result": self._success({
                "name": info.get("name", "Maple Pharmacy"),
                "address": info.get("address", ""),
                "phone": info.get("phone", ""),
                "hours": info.get("hours", ""),
            }),
        }


# ---------------------------------------------------------------------------
# ASGI App
# ---------------------------------------------------------------------------

_HTTP_CLIENT: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient()
    return _HTTP_CLIENT


_KV_NAMESPACE_ID = os.environ.get("KV_NAMESPACE_ID", "")


class App:
    def __init__(self) -> None:
        self._mcp = MCPHandler(_KV(_client(), _KV_NAMESPACE_ID), _client())

    async def handle(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        trace_id = _new_trace_id()
        try:
            await self._handle(scope, receive, send, trace_id)
        except Exception as exc:
            _log("unhandled_error", trace_id=trace_id, error_type=type(exc).__name__, error=str(exc))
            await self._send_json(send, 500, {"error": "internal"})

    async def _handle(self, scope: dict[str, Any], receive: Any, send: Any, trace_id: str) -> None:
        method = scope.get("method", "GET")
        path = scope.get("path", "/").rstrip("/") or "/"

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

        # Extract header names for diagnostics
        headers = scope.get("headers", [])
        header_names = [h[0].decode("latin-1") for h in headers if isinstance(h[0], bytes)]

        # Auth check for MCP endpoint
        if method == "POST" and path == "/mcp":
            auth_ok = False
            for h in headers:
                key = h[0].decode("latin-1").lower() if isinstance(h[0], bytes) else str(h[0]).lower()
                if key == "authorization":
                    val = h[1].decode("latin-1") if isinstance(h[1], bytes) else str(h[1])
                    if val.lower().startswith("bearer "):
                        token = val[7:]
                        if hmac.compare_digest(token, _MCP_TOKEN):
                            auth_ok = True
                            break
            if _MCP_TOKEN and not auth_ok:
                _log("mcp_request", trace_id=trace_id, method="auth", outcome="unauthorized", header_names=header_names)
                await self._send_json(send, 401, {"error": "unauthorized"})
                return

            status, response_body = await self._mcp.handle(raw_body, header_names, trace_id)
            if response_body is None:
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"cache-control", b"no-store"],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": b"",
                })
            else:
                await self._send_json(send, status, response_body)
            return

        if method == "GET" and path == "/health":
            health = await self._health_check()
            await self._send_json(send, 200, health)
            return

        if method == "GET" and path == "/mcp":
            await self._send_json(send, 405, {"error": "method not allowed"})
            return

        if method == "DELETE" and path == "/mcp":
            await self._send_json(send, 405, {"error": "method not allowed"})
            return

        await self._send_json(send, 404, {"error": "not found"})

    async def _health_check(self) -> dict[str, Any]:
        timer = _Timer()
        # Fast health: do not probe dependencies. Health checks verify the process is alive,
        # not that every downstream is reachable. Dependency status is surfaced per-request.
        return {
            "ok": True,
            "version": _MCP_VERSION,
            "latency_ms": timer.ms(),
        }

    async def _send_json(self, send: Any, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"cache-control", b"no-store"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })


def new():
    return App()
