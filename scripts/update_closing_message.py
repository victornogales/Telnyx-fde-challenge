import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Update assistant defaults to include closing_message
payload = {
    "dynamic_variables": {
        "greeting_suffix": "",
        "patient_first_name": "",
        "attempts_left": "3",
        "pharmacy_hours": "8am to 8pm, Monday to Saturday",
        "account_locked": "false",
        "after_hours_mode": "true",
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
    print(f"closing_message: {body.get('dynamic_variables', {}).get('closing_message')}")
