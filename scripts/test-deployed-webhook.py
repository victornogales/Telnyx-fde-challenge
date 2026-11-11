import json, httpx, os

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"

# Build a realistic assistant.initialization event
payload = {
    "data": {
        "event_type": "assistant.initialization",
        "payload": {
            "telnyx_end_user_target": "+15550000001",
            "call_control_id": "test-call-" + os.urandom(4).hex(),
            "from": "+15550000001",
            "to": "+442045202115",
        }
    }
}

try:
    resp = httpx.post(url, json=payload, timeout=15.0)
    print(f"Status: {resp.status_code}")
    body = resp.json()
    print(f"Dynamic variables returned:")
    dv = body.get("dynamic_variables", {})
    for k in sorted(dv.keys()):
        print(f"  {k}: {dv[k]}")
except Exception as exc:
    print(f"ERROR: {exc}")
