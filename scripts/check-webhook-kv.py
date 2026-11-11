import asyncio, json, sys, os
sys.path.insert(0, 'functions/refill-webhook')
import function

async def main():
    # Create a fresh KV client without cache to verify the fix
    client = function._client()
    kv = function._KV(client, os.environ.get("KV_NAMESPACE_ID", "3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee"))
    val = await kv.get("flag/after_hours_mode")
    print(f"after_hours_mode raw from KV: {val!r}")

asyncio.run(main())
