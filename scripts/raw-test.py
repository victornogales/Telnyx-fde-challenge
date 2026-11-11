import json, httpx, os

# Directly test the KV read via the Edge Function URL
# We'll add a new field to the response that does the raw API call

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"
payload = {
    "data": {
        "event_type": "assistant.initialization",
        "payload": {
            "telnyx_end_user_target": "+15550000001",
            "call_control_id": "raw-test-" + os.urandom(2).hex(),
            "from": "+15550000001",
            "to": "+442045202115",
        }
    }
}
resp = httpx.post(url, json=payload, timeout=15.0)
dv = resp.json().get("dynamic_variables", {})

# Print everything
for k, v in sorted(dv.items()):
    if k.startswith("_"):
        print(f"{k}: {v}")
