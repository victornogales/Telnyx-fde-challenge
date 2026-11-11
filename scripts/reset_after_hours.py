import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
kv_id = os.environ.get("KV_NAMESPACE_ID", "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee")

resp = httpx.put(
    f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/flag%2Fafter_hours_mode",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={"value": "false"},
    timeout=30.0,
)
print(f"Set after_hours_mode=false: {resp.status_code}")

resp2 = httpx.get(
    f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/flag%2Fafter_hours_mode",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30.0,
)
print(f"KV value: {resp2.json().get('value')}")
