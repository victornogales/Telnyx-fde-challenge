#!/usr/bin/env python3
"""
Update MCP tool name prefixes in assistant/workflow.json.

Recommends using after you register an MCP server so the tool names inside
node instructions always match the name Telnyx expects (<name>__tool>).

Usage examples
--------------
# 1. Tell the script your MCP server name directly
python scripts/update-workflow-prefix.py --name refill

# 2. Let the script discover the name from the Telnyx API
#    (requires TELNYX_API_KEY in env)
python scripts/update-workflow-prefix.py --fetch

# 3. Preview changes without writing
python scripts/update-workflow-prefix.py --name refill --dry-run

# 4. Update file AND push to assistant via API
python scripts/update-workflow-prefix.py --name refill --assistant-id <id>
"""
import argparse
import json
import os
import re
import sys
import textwrap
import urllib.request

WORKFLOW_PATH = os.path.join(os.path.dirname(__file__), "..", "assistant", "workflow.json")

TOOLS = [
    "verify_identity",
    "list_prescriptions",
    "request_refill",
    "get_refill_status",
    "get_medication_info",
    "get_pharmacy_info",
]

# Regex: optional existing prefix (word chars + __) followed by a known tool name
_TOOL_RE = re.compile(r"(\w*__)" + "(" + "|".join(TOOLS) + r")\b")


def _fetch_mcp_server_names(api_key: str) -> list[dict]:
    """GET /ai/mcp_servers and return [{name, url, id}, ...]."""
    req = urllib.request.Request(
        "https://api.telnyx.com/v2/ai/mcp_servers",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    items = data.get("data", []) if isinstance(data, dict) else []
    return [{"id": i["id"], "name": i["name"], "url": i.get("url", "")} for i in items]


def _update_content(text: str, prefix: str) -> str:
    """Replace every known tool reference with prefix__tool_name."""
    def repl(match: re.Match) -> str:
        return f"{prefix}__{match.group(2)}"

    return _TOOL_RE.sub(repl, text)


def _pretty_diff(old_text: str, new_text: str) -> str:
    """Simple line-based diff for human review."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    out = []
    for i, (o, n) in enumerate(zip(old_lines, new_lines)):
        if o != n:
            out.append(f"- [{i+1}] {o.strip()}")
            out.append(f"+ [{i+1}] {n.strip()}")
    return "\n".join(out) if out else "(no changes)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync MCP tool prefixes in assistant/workflow.json"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="MCP server short name (e.g. refill)")
    group.add_argument("--fetch", action="store_true", help="Discover name from Telnyx API")
    parser.add_argument("--workflow", default=WORKFLOW_PATH, help="Path to workflow.json")
    parser.add_argument("--dry-run", action="store_true", help="Print diff without writing")
    parser.add_argument("--assistant-id", default=os.environ.get("ASSISTANT_ID"), help="Patch assistant via API")
    args = parser.parse_args()

    prefix = args.name
    if args.fetch:
        api_key = os.environ.get("TELNYX_API_KEY", "")
        if not api_key:
            print("Error: TELNYX_API_KEY is required for --fetch", file=sys.stderr)
            return 1
        servers = _fetch_mcp_server_names(api_key)
        if not servers:
            print("Error: No MCP servers found on this account.", file=sys.stderr)
            return 1
        print("Discovered MCP servers:")
        for s in servers:
            print(f"  - name={s['name']!r}  url={s['url']!r}")
        # Heuristic: pick the one whose URL contains 'refill-mcp' or whose name contains 'refill'
        candidates = [s for s in servers if "refill" in s["name"] or "refill-mcp" in s["url"]]
        if not candidates:
            candidates = servers  # fall back to all
        if len(candidates) > 1:
            print(f"\nMultiple candidates found. Using first: {candidates[0]['name']!r}")
            print("Tip: use --name <name> to pick exactly.")
        prefix = candidates[0]["name"]
        print(f"\nSelected prefix: {prefix!r}\n")

    if not prefix:
        print("Error: Could not determine MCP server name.", file=sys.stderr)
        return 1

    workflow_path = args.workflow
    if not os.path.isfile(workflow_path):
        print(f"Error: workflow.json not found at {workflow_path}", file=sys.stderr)
        return 1

    with open(workflow_path, "r", encoding="utf-8") as f:
        old_text = f.read()

    new_text = _update_content(old_text, prefix)

    # Validate the result is good JSON
    try:
        json.loads(new_text)
    except json.JSONDecodeError as exc:
        print(f"Error: Update produced invalid JSON: {exc}", file=sys.stderr)
        return 1

    # Show diff
    diff = _pretty_diff(old_text, new_text)
    print("Changes to be made:")
    print(textwrap.indent(diff, "  "))
    print()

    if args.dry_run:
        print("--dry-run: not writing changes.")
        return 0

    # Write
    with open(workflow_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"Updated {workflow_path}")

    # Optional: push to assistant
    if args.assistant_id:
        api_key = os.environ.get("TELNYX_API_KEY", "")
        if not api_key:
            print("Error: TELNYX_API_KEY is required to push to assistant", file=sys.stderr)
            return 1
        payload = json.dumps({"conversation_flow": json.loads(new_text)["conversation_flow"]})
        req = urllib.request.Request(
            f"https://api.telnyx.com/v2/ai/assistants/{args.assistant_id}",
            data=payload.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"Assistant updated: HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"Assistant update failed: HTTP {exc.code}\n{body}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
