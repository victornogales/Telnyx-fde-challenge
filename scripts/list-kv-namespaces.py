import httpx, os, sys

api_key = os.environ.get("TELNYX_API_KEY", "")
if not api_key:
    print("ERROR: set TELNYX_API_KEY", file=sys.stderr)
    sys.exit(1)

headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

# List all KV namespaces
resp = httpx.get("https://api.telnyx.com/v2/storage/kvs", headers=headers, timeout=10.0)
print("Status:", resp.status_code)
data = resp.json().get("data", [])
for ns in data:
    print(f"  {ns.get('id')}: {ns.get('name', 'unnamed')}")
