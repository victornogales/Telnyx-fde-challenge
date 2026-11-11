import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# First, get current assistant
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    cur = resp.json().get("data", {})

# Keep inline tools, drop any old transfer
tools = [t for t in (cur.get("tools") or []) if t.get("type") != "transfer"]

# Add transfer tool - for demo, route back to the user's own phone number
# In production this would be the pharmacy's staffed line
transfer_to = "+15550000001"   # TODO: change to real pharmacist number if available

tools.append({
    "type": "transfer",
    "transfer": {
        "targets": [
            {
                "to": transfer_to,
                "name": "Pharmacist",
                "message": "A Maple Pharmacy caller needs to speak with a pharmacist."
            }
        ],
        "from": "+442045202115",
        "warm_transfer_instructions": "Tell the pharmacist the caller needs to speak with a person about a prescription.",
        "warm_transfer_acceptance": {
            "enabled": False
        }
    }
})

payload = {"tools": tools}

print("PATCH payload:", json.dumps(payload, indent=2))

with httpx.Client() as client:
    resp = client.patch(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    print("Status:", resp.status_code)
    print(resp.text)
