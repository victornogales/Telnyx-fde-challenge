import httpx, os, sys

api_key = os.environ.get("TELNYX_API_KEY", "")
kv_id  = "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee"

if not api_key:
    print("ERROR: set TELNYX_API_KEY", file=sys.stderr)
    sys.exit(1)

headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Write a test value with current timestamp
ts = __import__('datetime').datetime.now().isoformat()
uri = f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/test%2Fping"
resp = httpx.put(uri, headers=headers, json={"value": ts}, timeout=10.0)
print(f"PUT test/ping = {ts}: {resp.status_code}")

# Read it back
resp2 = httpx.get(uri, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}, timeout=10.0)
print(f"GET test/ping: {resp2.status_code} -> {resp2.json().get('value')}")

# Read after_hours again
resp3 = httpx.get(f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/flag%2Fafter_hours_mode",
    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}, timeout=10.0)
print(f"GET after_hours_mode: {resp3.status_code} -> {resp3.json().get('value')}")
