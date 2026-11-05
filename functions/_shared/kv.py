import asyncio
import json
import os
import time
import urllib.parse
from typing import Any

import httpx

from .log import log

_API_BASE = "https://api.telnyx.com/v2/storage/kvs"
_TELNYX_API_KEY = os.environ.get("TELNYX_API_KEY", "")


class KV:
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
        try:
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
        except Exception as exc:
            log("kv_get_error", key=key, error_type=type(exc).__name__, error=str(exc))
            return None

    async def put(
        self,
        key: str,
        value: str | bytes,
        ttl_secs: int | None = None,
        timeout: float = 5.0,
    ) -> bool:
        try:
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
        except Exception as exc:
            log("kv_put_error", key=key, error_type=type(exc).__name__, error=str(exc))
            return False

    async def delete(self, key: str, timeout: float = 5.0) -> bool:
        try:
            resp = await self._client.delete(
                self._url(key),
                headers=self._headers(),
                timeout=timeout,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            log("kv_delete_error", key=key, error_type=type(exc).__name__, error=str(exc))
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
