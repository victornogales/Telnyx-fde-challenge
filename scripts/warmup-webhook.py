import json, httpx, os

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"

for i in range(5):
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {
                "telnyx_end_user_target": "+15550000001",
                "call_control_id": f"warmup-call-{i}-{os.urandom(2).hex()}",
                "from": "+15550000001",
                "to": "+442045202115",
            }
        }
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        body = resp.json()
        dv = body.get("dynamic_variables", {})
        ts = dv.get("_deploy_ts", "OLD")
        flags_raw = dv.get("_debug_flags_raw", "N/A")
        print(f"Req {i}: deploy_ts={ts}, flags_raw={flags_raw}")
    except Exception as exc:
        print(f"Req {i}: ERROR {exc}")
