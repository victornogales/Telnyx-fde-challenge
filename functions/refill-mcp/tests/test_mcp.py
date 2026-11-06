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
