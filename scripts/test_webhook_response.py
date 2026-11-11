import json, httpx, os, hashlib, time

WEBHOOK_URL = "https://refill-webhook-8d5c4fc7-b.telnyxcompute.com"
end_user = "+15550000001"
call_control_id = "debug-" + str(int(time.time()))

payload = {
    "data": {
        "event_type": "assistant.initialization",
        "payload": {
            "call_control_id": call_control_id,
            "telnyx_end_user_target": end_user,
            "telnyx_agent_target": "+442045202115",
        }
    }
}

resp = httpx.post(WEBHOOK_URL, json=payload, timeout=5.0)
print(f"Status: {resp.status_code}")
print(f"Body: {resp.text}")

# Verify hash
ckey = hashlib.sha256(end_user.encode()).hexdigest()[:16]
print(f"\ncaller_key for {end_user}: {ckey}")
print(f"Expected caller_key from logs: 8e89f1d43d07b82d")
print(f"Match: {ckey == '8e89f1d43d07b82d'}")

# Check patient name
_PATIENTS = {
    "+15550000001": "Maria",
    "+442045202115": "James",
    "+15551112222": "David",
    "+15552223333": "Sarah",
    "+15553334444": "Robert",
}
name = _PATIENTS.get(end_user, "")
print(f"Patient name lookup: '{name}'")
print(f"Greeting would be: ' Hi {name}, how can I help you today?'" if name else "Greeting would be: ' How can I help you today?'")
