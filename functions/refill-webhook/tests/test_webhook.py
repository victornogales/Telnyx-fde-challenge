import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("TELNYX_API_KEY", "test-key")
os.environ.setdefault("KV_NAMESPACE_ID", "test-ns")
os.environ.setdefault("INTERNAL_TOKEN", "test-token")
os.environ.setdefault("CALLER_SESSION_URL", "https://gateway.test")

import httpx
import pytest

from function import App, SAFE_DEFAULTS


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, httpx.Response]):
        self._responses = responses

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for pattern, resp in self._responses.items():
            if pattern in url:
                return resp
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def app():
    return App()


@pytest.mark.asyncio
async def test_malformed_body_returns_defaults(app):
    send_calls = []

    async def receive():
        return {"type": "http.request", "body": b"not-json", "more_body": False}

    async def send(message):
        send_calls.append(message)

    await app.handle({"method": "POST", "path": "/", "headers": []}, receive, send)

    assert send_calls[0]["status"] == 200
    body = json.loads(send_calls[1]["body"])
    assert "dynamic_variables" in body
    assert body["dynamic_variables"]["is_known_caller"] == "false"


@pytest.mark.asyncio
async def test_missing_caller_returns_defaults(app):
    send_calls = []
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {"call_control_id": "v3:test"},
        }
    }

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps(payload).encode(),
            "more_body": False,
        }

    async def send(message):
        send_calls.append(message)

    await app.handle({"method": "POST", "path": "/", "headers": []}, receive, send)

    assert send_calls[0]["status"] == 200
    body = json.loads(send_calls[1]["body"])
    assert body["dynamic_variables"]["is_known_caller"] == "false"


@pytest.mark.asyncio
async def test_happy_path(app, monkeypatch):
    import function as func_module

    responses = {
        "storage/kvs/test-ns/keys/flag%2Frefills_enabled": httpx.Response(
            200,
            json={"data": {"value": "true"}},
        ),
        "storage/kvs/test-ns/keys/flag%2Fafter_hours_mode": httpx.Response(
            200,
            json={"data": {"value": "false"}},
        ),
        "gateway.test/rpc": httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "callCount": 3,
                    "locked": False,
                    "openRefills": 1,
                    "lastIntent": "refill",
                },
            },
        ),
    }

    mock_transport = _MockTransport(responses)
    mock_client = httpx.AsyncClient(transport=mock_transport)

    original_client = func_module._HTTP_CLIENT
    func_module._HTTP_CLIENT = mock_client

    send_calls = []
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {
                "telnyx_end_user_target": "+15551234567",
                "call_control_id": "v3:test",
            },
        }
    }

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps(payload).encode(),
            "more_body": False,
        }

    async def send(message):
        send_calls.append(message)

    try:
        await app.handle(
            {"method": "POST", "path": "/", "headers": []}, receive, send
        )
    finally:
        func_module._HTTP_CLIENT = original_client
        await mock_client.aclose()

    assert send_calls[0]["status"] == 200
    body = json.loads(send_calls[1]["body"])
    dv = body["dynamic_variables"]
    assert dv["is_known_caller"] == "true"
    assert dv["call_count"] == "3"
    assert dv["account_locked"] == "false"
    assert dv["open_refill_count"] == "1"
    assert dv["last_intent"] == "refill"
    assert dv["refills_enabled"] == "true"
    assert dv["after_hours_mode"] == "false"
    assert dv["trace_id"].startswith("tr_")
