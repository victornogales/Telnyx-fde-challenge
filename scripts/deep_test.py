import json, httpx, os

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"
out_file = "webhook_deep_log.jsonl"

with open(out_file, "w") as f:
    pass

for i in range(10):
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {
                "telnyx_end_user_target": "+15550000001",
                "call_control_id": f"deep-{i}-{os.urandom(2).hex()}",
                "from": "+15550000001",
                "to": "+442045202115",
            }
        }
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        j = resp.json()
        dv = j.get("dynamic_variables", {})
        
        # Print detailed info
        print(f"Req {i}:")
        print(f"  status={resp.status_code}")
        print(f"  deploy_ts   = {dv.get('_deploy_ts', 'OLD')}")
        print(f"  after_hours = {dv.get('after_hours_mode', 'MISSING')}")
        print(f"  refills     = {dv.get('refills_enabled', 'MISSING')}")
        print(f"  greeting    = {dv.get('greeting_suffix', 'MISSING')!r}")
        print(f"  flags_error = {dv.get('_debug_flags_error', 'MISSING')}")
        print(f"  flags_raw   = {dv.get('_debug_flags_raw', 'MISSING')}")
        print(f"  is_known    = {dv.get('is_known_caller', 'MISSING')}")
        print()
        
        with open(out_file, "a") as f:
            f.write(json.dumps({k: str(v)[:100] for k, v in dv.items()}) + "\n")
    except Exception as exc:
        print(f"Req {i}: ERROR {exc}\n")
