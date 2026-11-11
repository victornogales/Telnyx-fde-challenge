import json, httpx, os

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"

# Hit it 20 times rapidly
for i in range(20):
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {
                "telnyx_end_user_target": "+15550000001",
                "call_control_id": f"burst-{i}-{os.urandom(2).hex()}",
                "from": "+15550000001",
                "to": "+442045202115",
            }
        }
    }
    resp = httpx.post(url, json=payload, timeout=15.0)
    dv = resp.json().get("dynamic_variables", {})
    ah = dv.get("after_hours_mode", "?")
    ts = dv.get("_deploy_ts", "OLD")
    print(f"{i:2d}: after_hours={ah!r:6s} deploy_ts={ts}")
