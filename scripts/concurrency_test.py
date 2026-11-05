#!/usr/bin/env python3
"""
Spike S8 / Day-2 concurrency proof.
Fires N parallel recordCall requests at the actor gateway for the same caller_key.
Verifies the actor serializes them correctly (callCount == previous + N).
"""
import asyncio
import sys

import httpx

GATEWAY_URL = "https://caller-session-51645523-7.telnyxcompute.com/rpc"
INTERNAL_TOKEN = "REPLACE_ME"  # <-- paste your real INTERNAL_TOKEN here
CALLER_KEY = "concurrency_test"
CONCURRENCY = 20

headers = {
    "Content-Type": "application/json",
    "X-Internal-Token": INTERNAL_TOKEN,
}


async def fire_one(client: httpx.AsyncClient, trace_id: str) -> dict:
    payload = {
        "method": "recordCall",
        "caller_key": CALLER_KEY,
        "args": {"traceId": trace_id},
    }
    try:
        resp = await client.post(GATEWAY_URL, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("result", {})
    except Exception as exc:
        return {"error": str(exc)}


async def main() -> int:
    async with httpx.AsyncClient() as client:
        # Baseline
        baseline = await fire_one(client, "tr_baseline")
        if "error" in baseline:
            print(f"Baseline failed: {baseline['error']}")
            return 1
        start_count = baseline.get("callCount", 0)
        print(f"Baseline callCount for {CALLER_KEY}: {start_count}")

        # Fire N in parallel
        tasks = [fire_one(client, f"tr_{i:03d}") for i in range(CONCURRENCY)]
        results = await asyncio.gather(*tasks)

        errors = [r for r in results if "error" in r]
        if errors:
            print(f"{len(errors)} requests failed. First error: {errors[0]['error']}")
            return 1

        # Final count
        final = await fire_one(client, "tr_final")
        end_count = final.get("callCount", 0)
        print(f"Final callCount for {CALLER_KEY}:   {end_count}")
        print(f"Expected: {start_count + CONCURRENCY}")

        if end_count == start_count + CONCURRENCY:
            print("SUCCESS: actor serialized all updates correctly.")
            return 0
        else:
            print(f"FAILURE: lost {start_count + CONCURRENCY - end_count} updates.")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
