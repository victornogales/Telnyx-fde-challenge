import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Get current assistant
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    cur = resp.json().get("data", {})

# Patch dynamic_variables to have safe string defaults instead of null
dv = cur.get("dynamic_variables", {})
dv["greeting_suffix"] = ""
dv["patient_first_name"] = ""
dv["attempts_left"] = "3"
dv["pharmacy_hours"] = "8am to 8pm, Monday to Saturday"
dv["account_locked"] = "false"
dv["after_hours_mode"] = "false"
dv["refills_enabled"] = "true"
dv["open_refill_count"] = "0"

payload = {"dynamic_variables": dv}

with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    print("Status:", resp.status_code)
    data = resp.json().get("data", {})
    print("Updated defaults:", {k: data.get("dynamic_variables", {}).get(k) for k in [
        "greeting_suffix", "patient_first_name", "attempts_left", "account_locked",
        "after_hours_mode", "refills_enabled", "open_refill_count"
    ]})
