import httpx, os, sys, json

api_key = os.environ.get("TELNYX_API_KEY", "")
kv_id  = os.environ.get("KV_NAMESPACE_ID", "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee")

if not api_key:
    print("ERROR: TELNYX_API_KEY not set", file=sys.stderr)
    sys.exit(1)

uri = f"https://api.telnyx.com/v2/storage/kvs/{kv_id}/keys/flag%2Fafter_hours_mode"
headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

with httpx.Client() as client:
    try:
        resp = client.get(uri, headers=headers, timeout=10.0)
        print("Status:", resp.status_code)
        print("Response:", json.dumps(resp.json(), indent=2))
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
