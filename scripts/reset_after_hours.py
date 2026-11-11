import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Reset after_hours_mode static default to false
payload = {
    "dynamic_variables": {
        "greeting_suffix": "",
        "patient_first_name": "",
        "attempts_left": "3",
        "pharmacy_hours": "8am to 8pm, Monday to Saturday",
        "account_locked": "false",
        "after_hours_mode": "false",
        "refills_enabled": "true",
        "open_refill_count": "0",
        "closing_message": "Thanks for calling Maple Pharmacy. We appreciate your call. Take care, and have a great day.",
        "transfer_fail_message": "I couldn't reach a pharmacist right now. Please call back during business hours. Thanks for your call, goodbye.",
    }
}

with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30.0,
    )
    print(f"Status: {resp.status_code}")
    body = resp.json()
    print(f"after_hours_mode: {body.get('dynamic_variables', {}).get('after_hours_mode')}")
