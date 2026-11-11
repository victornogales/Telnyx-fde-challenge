import json, httpx, os

api_key = os.environ.get("TELNYX_API_KEY", "")
assistant_id = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"

# Get current main version
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    main = resp.json()

print(f"Main version_id: {main.get('version_id')}")
print(f"Main version_created_at: {main.get('version_created_at')}")

# Get all versions
with httpx.Client() as client:
    resp = client.get(
        f"https://api.telnyx.com/v2/ai/assistants/{assistant_id}/versions",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=30.0,
    )
    versions = resp.json()

print(f"\nAll versions:")
vlist = versions.get("data", [])
for v in vlist:
    print(f"  {v.get('version_id')} @ {v.get('version_created_at')}")

# Is there a promotion setting?
print(f"\nMain version in list: {any(v.get('version_id') == main.get('version_id') for v in vlist)}")
