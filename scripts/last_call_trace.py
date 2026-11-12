#!/usr/bin/env python3
"""Fetch the latest AI conversation for the assistant and show routing details."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import httpx

ASSISTANT_ID = "assistant-9befc905-0e48-42f9-b65f-ae91b269bb65"
BASE_URL = "https://api.telnyx.com/v2"
CLI_CONFIG = Path.home() / ".telnyx-edge" / "config.toml"

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _redact(text: str) -> str:
    text = _ISO_DATE_RE.sub("<date>", text)
    return _PHONE_RE.sub("<redacted>", text)


def _cli_key() -> str:
    try:
        text = CLI_CONFIG.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'(?m)^\s*api_key\s*=\s*"([^"]+)"', text)
    return match.group(1).strip() if match else ""


def _resolve_key() -> tuple[str, str]:
    env_key = os.environ.get("TELNYX_API_KEY", "").strip()
    if env_key:
        return env_key, "TELNYX_API_KEY"
    key = _cli_key()
    if key:
        return key, str(CLI_CONFIG)
    print(
        "ERROR: set TELNYX_API_KEY or configure ~/.telnyx-edge/config.toml",
        file=sys.stderr,
    )
    sys.exit(1)


class Api:
    def __init__(self) -> None:
        self.key, self.source = _resolve_key()
        self.client = httpx.Client(timeout=30.0)

    def __enter__(self) -> "Api":
        return self

    def __exit__(self, *_exc) -> None:
        self.client.close()

    def _request(self, path: str, params: dict | None):
        return self.client.get(
            f"{BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Accept": "application/json",
            },
            params=params,
        )

    def get(self, path: str, params: dict | None = None):
        resp = self._request(path, params)
        if resp.status_code == 401 and self.source == "TELNYX_API_KEY":
            alt_key = _cli_key()
            if alt_key and alt_key != self.key:
                print(
                    "Note: TELNYX_API_KEY was rejected; "
                    f"using {CLI_CONFIG}",
                    file=sys.stderr,
                )
                self.key, self.source = alt_key, str(CLI_CONFIG)
                resp = self._request(path, params)
        if resp.status_code >= 400:
            print(f"ERROR: GET {path} -> HTTP {resp.status_code}", file=sys.stderr)
            print(resp.text[:1000], file=sys.stderr)
            sys.exit(1)
        return resp.json()


def _messages(api: Api, conversation_id: str) -> list[dict]:
    messages: list[dict] = []
    page = 1
    while True:
        body = api.get(
            f"/ai/conversations/{conversation_id}/messages",
            {"page[size]": 100, "page[number]": page},
        )
        messages.extend(body.get("data", []))
        total_pages = max(int((body.get("meta") or {}).get("total_pages", 1)), 1)
        if page >= total_pages:
            return messages
        page += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transcript",
        action="store_true",
        help="print redacted user/assistant text and tool results",
    )
    args = parser.parse_args()

    with Api() as api:
        listing = api.get(
            "/ai/conversations",
            {
                "metadata->assistant_id": f"eq.{ASSISTANT_ID}",
                "order": "created_at.desc",
                "limit": 5,
            },
        )
        conversations = listing.get("data", [])
        if not conversations:
            print("No conversations found for this assistant.")
            return

        conv = conversations[0]
        cid = conv["id"]
        print(f"Latest conversation: {cid} (created {conv.get('created_at', '?')})")
        meta = conv.get("metadata") or {}

        print()
        print("=== Workflow routing ===")
        transitions = meta.get("flow_transitions") or []
        if transitions:
            for transition in transitions:
                print(f"  {transition}")
        else:
            print("  (none recorded)")

        print()
        print("=== Tool calls ===")
        tools = meta.get("called_tools") or []
        if tools:
            for tool in tools:
                print(f"  {tool}")
        else:
            print("  (none recorded)")

        messages = _messages(api, cid)
        print()
        print(f"=== Messages ({len(messages)}) ===")
        for message in messages:
            role = message.get("role", "?")
            node = (message.get("metadata") or {}).get("flow_node_id", "?")
            tool_calls = [
                (call.get("function") or {}).get("name")
                for call in (message.get("tool_calls") or [])
            ]
            if role == "tool":
                print(f"  [{node}] tool result", end="")
                if args.transcript:
                    text = _redact(message.get("text") or "")
                    print(f": {text[:300]}")
                else:
                    print()
            elif tool_calls:
                names = ", ".join(str(name) for name in tool_calls)
                print(f"  [{node}] {role} -> tool: {names}")
            else:
                print(f"  [{node}] {role}", end="")
                if args.transcript:
                    text = _redact(message.get("text") or "")
                    print(f": {text}")
                else:
                    print()

        print()
        print("=== Conversation metadata ===")
        for key in (
            "assistant_id",
            "assistant_version_id",
            "telnyx_conversation_channel",
            "telnyx_end_user_target_verified",
        ):
            if key in meta:
                print(f"  {key}: {meta[key]}")


if __name__ == "__main__":
    main()
