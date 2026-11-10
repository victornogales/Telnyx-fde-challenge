"""pytest for refill-mcp function.py"""
import sys
from pathlib import Path

# Add parent directory to path so we can import function
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import function as fn


class TestPatientData:
    def test_find_patient_known(self):
        p = fn._find_patient("+15550000001")
        assert p is not None
        assert p["first_name"] == "Maria"
        assert p["dob"] == "1962-03-15"
        assert len(p["prescriptions"]) == 3

    def test_find_patient_unknown(self):
        p = fn._find_patient("+999999999999")
        assert p is None

    def test_prescriptions_structure(self):
        p = fn._find_patient("+15550000001")
        rx = p["prescriptions"][0]
        assert "id" in rx
        assert "name" in rx
        assert "strength" in rx
        assert "refills_left" in rx
        assert "controlled" in rx


class TestCallerKey:
    def test_caller_key_is_hex(self):
        key = fn._caller_key("+15551234567")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_caller_key_deterministic(self):
        assert fn._caller_key("+15551234567") == fn._caller_key("+15551234567")

    def test_caller_key_different_numbers(self):
        assert fn._caller_key("+15551234567") != fn._caller_key("+15559876543")


class TestTraceId:
    def test_trace_id_format(self):
        tid = fn._new_trace_id()
        assert tid.startswith("tr_")
        assert len(tid) == 15  # tr_ + 12 hex chars


class TestTimer:
    def test_timer_returns_positive(self):
        t = fn._Timer()
        import time
        time.sleep(0.01)
        ms = t.ms()
        assert ms >= 10


class TestJSONRPCHelpers:
    def test_jsonrpc_error(self):
        err = fn._jsonrpc_error("req-1", -32601, "Method not found")
        assert err["jsonrpc"] == "2.0"
        assert err["id"] == "req-1"
        assert err["error"]["code"] == -32601

    def test_jsonrpc_result(self):
        res = fn._jsonrpc_result("req-1", {"tools": []})
        assert res["jsonrpc"] == "2.0"
        assert res["id"] == "req-1"
        assert res["result"]["tools"] == []


class TestMCPHandlerInitialize:
    @pytest.mark.asyncio
    async def test_initialize(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        result = await handler._handle_initialize({"protocolVersion": "2024-11-05"})
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "refill-mcp"

    @pytest.mark.asyncio
    async def test_tools_list(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        status, body = await handler.handle(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
            [],
            "tr_test"
        )
        assert status == 200
        assert len(body["result"]["tools"]) == 6


class TestMCPHandlerToolCall:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "nonexistent", "arguments": {}}
        }).encode()
        status, result = await handler.handle(body, [], "tr_test")
        assert status == 200
        assert result["result"]["isError"] is True


class TestPharmacyInfo:
    @pytest.mark.asyncio
    async def test_get_pharmacy_info(self):
        mock_kv = MagicMock()
        mock_kv.get = AsyncMock(return_value=None)
        info = await fn._get_pharmacy_info(mock_kv)
        assert info["name"] == "Maple Pharmacy"
        assert "hours" in info


class TestOpenFDANormalization:
    def test_first_empty(self):
        assert fn._first([]) == ""
        assert fn._first(["a", "b"]) == "a"


class TestMCPHandlerHardening:
    @pytest.mark.asyncio
    async def test_notification_no_id(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        body = json.dumps({"jsonrpc": "2.0", "method": "initialize", "params": {}}).encode()
        status, result = await handler.handle(body, [], "tr_test")
        assert status == 202
        assert result is None

    @pytest.mark.asyncio
    async def test_batch_invalid_request(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        body = json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}]).encode()
        status, result = await handler.handle(body, [], "tr_test")
        assert status == 200
        assert result["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_non_dict_body(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        body = json.dumps("just a string").encode()
        status, result = await handler.handle(body, [], "tr_test")
        assert status == 200
        assert result["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_initialize_unknown_protocol_version(self):
        mock_kv = MagicMock()
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        result = await handler._handle_initialize({"protocolVersion": "1999-01-01"})
        assert result["protocolVersion"] == fn._SUPPORTED_PROTOCOL_VERSIONS[0]

    @pytest.mark.asyncio
    async def test_tool_call_without_trace_id(self):
        mock_kv = MagicMock()
        mock_kv.get = AsyncMock(return_value=None)
        mock_client = MagicMock()
        handler = fn.MCPHandler(mock_kv, mock_client)
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_pharmacy_info",
                "arguments": {},
            }
        }).encode()
        status, result = await handler.handle(body, [], "tr_test")
        assert status == 200
        assert result["result"]["isError"] is False
        content = result["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        data = json.loads(content[0]["text"])
        assert data["name"] == "Maple Pharmacy"


class TestAppHardening:
    @pytest.mark.asyncio
    async def test_get_mcp(self):
        app = fn.App()
        send_mock = AsyncMock()
        await app._handle(
            {"method": "GET", "path": "/mcp", "headers": []},
            _mock_receive(b""),
            send_mock,
            "tr_test"
        )
        assert _status(send_mock) == 405

    @pytest.mark.asyncio
    async def test_delete_mcp(self):
        app = fn.App()
        send_mock = AsyncMock()
        await app._handle(
            {"method": "DELETE", "path": "/mcp", "headers": []},
            _mock_receive(b""),
            send_mock,
            "tr_test"
        )
        assert _status(send_mock) == 405

    @pytest.mark.asyncio
    async def test_path_normalization(self):
        app = fn.App()
        send_mock = AsyncMock()
        await app._handle(
            {"method": "GET", "path": "/mcp/", "headers": []},
            _mock_receive(b""),
            send_mock,
            "tr_test"
        )
        assert _status(send_mock) == 405

    @pytest.mark.asyncio
    async def test_unauthorized_post(self):
        with patch.object(fn, "_MCP_TOKEN", "valid_token"):
            app = fn.App()
            send_mock = AsyncMock()
            await app._handle(
                {"method": "POST", "path": "/mcp", "headers": [[b"authorization", b"Bearer bad"]]},
                _mock_receive(b""),
                send_mock,
                "tr_test"
            )
            assert _status(send_mock) == 401

    @pytest.mark.asyncio
    async def test_unauthorized_no_token(self):
        with patch.dict("os.environ", {"MCP_TOKEN": ""}):
            app = fn.App()
            send_mock = AsyncMock()
            await app._handle(
                {"method": "POST", "path": "/mcp", "headers": []},
                _mock_receive(b""),
                send_mock,
                "tr_test"
            )
            assert _status(send_mock) == 200  # no token configured → open

    @pytest.mark.asyncio
    async def test_unhandled_error_returns_json(self):
        app = fn.App()
        send_mock = AsyncMock()
        # Force _handle to raise by using a broken scope
        with patch.object(app, "_handle", side_effect=RuntimeError("boom")):
            await app.handle(
                {"method": "GET", "path": "/health", "headers": []},
                _mock_receive(b""),
                send_mock
            )
        assert _status(send_mock) == 500
        assert _json_body(send_mock)["error"] == "internal"


def _mock_receive(body: bytes):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return receive


def _status(send_mock):
    for call in send_mock.call_args_list:
        args = call.args or call[0]
        if args and isinstance(args[0], dict):
            if args[0].get("type") == "http.response.start":
                return args[0].get("status")
    return None


def _json_body(send_mock):
    for call in send_mock.call_args_list:
        args = call.args or call[0]
        if args and isinstance(args[0], dict):
            if args[0].get("type") == "http.response.body":
                body = args[0].get("body", b"")
                return json.loads(body.decode())
    return {}
