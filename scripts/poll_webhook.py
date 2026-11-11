import json, httpx, os, time

url = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"
out_file = "webhook_poll_log.jsonl"

print(f"Polling webhook and writing to {out_file}...")
print("Call +442045202115 now. I will log every webhook response.\n")

count = 0
while count < 30:  # up to 30 calls
    payload = {
        "data": {
            "event_type": "assistant.initialization",
            "payload": {
                "telnyx_end_user_target": "+15550000001",
                "call_control_id": f"poll-{count}-{os.urandom(2).hex()}",
                "from": "+15550000001",
                "to": "+442045202115",
            }
        }
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        timestamp = time.strftime("%H:%M:%S")
        dv = resp.json().get("dynamic_variables", {})
        log_entry = {
            "timestamp": timestamp,
            "seq": count,
            "status": resp.status_code,
            "after_hours_mode": dv.get("after_hours_mode"),
            "refills_enabled": dv.get("refills_enabled"),
            "greeting_suffix": dv.get("greeting_suffix"),
            "deploy_ts": dv.get("_deploy_ts"),
            "flags_raw": dv.get("_debug_flags_raw"),
            "flags_error": dv.get("_debug_flags_error"),
        }
        with open(out_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"[{timestamp}] #{count:2d} after_hours={log_entry['after_hours_mode']!s:6s} deploy={log_entry['deploy_ts']} closed={'closed' in log_entry.get('greeting_suffix','').lower()}")
    except Exception as exc:
        print(f"[{time.strftime('%H:%M:%S')}] #{count:2d} ERROR: {exc}")
    count += 1
    time.sleep(5)  # wait 5 seconds between polls

print(f"\nDone. Log written to {out_file}")
