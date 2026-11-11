import httpx, os, sys

api_key = os.environ.get("TELNYX_API_KEY", "")
kv_id  = "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee"

if not api_key:
    print("ERROR: set TELNYX_API_KEY", file=sys.stderr)
    sys.exit(1)

uri = f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/flag%2Fafter_hours_mode"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

with httpx.Client() as client:
    resp = client.put(uri, headers=headers, json={"value": "true"}, timeout=10.0)
    print(f"PUT Status: {resp.status_code}")
    
    resp2 = client.get(uri, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}, timeout=10.0)
    print(f"GET Status: {resp2.status_code}")
    print(f"Value: {resp2.json().get('value')}")
