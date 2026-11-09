import json
import urllib.request

url = "https://api.telnyx.com/v2/ai/assistants/assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"
headers = {
    "Authorization": "Bearer REPLACE_WITH_ENV_TELNYX_API_KEY",
    "Content-Type": "application/json",
}

payload = {
    "mcp_servers": [
        {
            "id": "741d636a-22d6-4723-99d9-34815b857ed5",
            "allowed_tools": [
                "verify_identity",
                "list_prescriptions",
                "request_refill",
                "get_refill_status",
                "get_medication_info",
                "get_pharmacy_info",
            ],
        }
    ]
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.status)
        print(json.dumps(json.loads(resp.read().decode()), indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode())
