# Project: RefillLine (Telnyx FDE challenge)

Voice assistant for pharmacy refills. A Telnyx AI Assistant (Conversation Workflow) calls three Edge Functions:
- `refill-webhook` (**Python**, ASGI): the dynamic-variables webhook. Reads KV flags over REST; calls the actor gateway.
- `refill-mcp` (**Python**, ASGI): the MCP server over HTTP (6 tools). KV cache over REST, openFDA, and the actor gateway.
- `caller-session` (**TypeScript**, the ONLY TS): the actor gateway. Owns Stateful Actor `CallerSession`; exposes `POST /rpc`.
Design: PLAN.md (local working plan, not committed), docs/architecture.md and the README. Follow them; ask before deviating.

## Hard rules
- Python 3 for refill-webhook and refill-mcp. Dependencies: stdlib + `httpx` only, unless I approve more.
  No requirements.txt: dependencies go in pyproject.toml.
- Python Edge Functions use the scaffold's ASGI contract: `new()` factory → object with
  `async def handle(self, scope, receive, send)`. Keep `function/__init__.py` (`from .func import new`).
  Create HTTP clients once per container (module scope or `start()`), never per request.
- Stateful Actors are TypeScript-only (define AND call; no REST fallback). Never try to use actors from Python —
  go through `caller-session` POST /rpc with headers X-Internal-Token and X-Trace-Id (see shared/session_client.py).
- caller-session: actor bindings go in telnyx.toml `[[actors]]` (NOT func.toml); type == exported class name.
  Never invent `@telnyx/edge-runtime` APIs. Run `telnyx-edge types` and `npm run typecheck` after changes.
- KV from Python = REST: https://api.telnyx.com/v2/storage/kvs/{KV_NAMESPACE_ID}/keys/{key},
  Bearer TELNYX_API_KEY (injected by `[telnyx]` in func.toml), `?ttl_secs=N` on PUT, 404 = missing.
  Keys: no colons; use `/` (e.g. `flag/after_hours_mode`, `cache/fda/<name>`).
- **Platform constraint:** Python Edge Functions only support a single flat module
  (`py-modules = ["function"]` in `pyproject.toml`). Package directories fail at build time.
  Shared Python helpers live in `functions/_shared/` for local editing and pytest, but must be
  **inlined** into `function.py` before `telnyx-edge ship`. Do not create `function/shared/` or
  any sub-package directories in a Python function.
- Dynamic variables webhook response MUST be `{"dynamic_variables": {...}}` and every value a STRING.
- Webhook target: < 1000 ms warm; worst case ≈ 1.5 s (KV read cap 1.5 s, gateway cap 0.5 s, run in parallel;
  assistant webhook timeout is 5 s). Per-dependency timeouts + asyncio.wait_for; on any error return
  SAFE_DEFAULTS with HTTP 200. Never a bare 500 anywhere.
- Every request / actor method / tool call logs exactly one JSON line via `log()` with trace_id.
  Never log DOB, names or raw phone numbers — use caller_key (sha256 prefix).
- MCP: stateless, POST /mcp, JSON responses; tools return speakable errors (isError), never raise.
- Verification is enforced server-side in the actor via time-based gating (`isVerified()` checks a 30-minute window after a successful attempt).
- If unsure about any Telnyx API, search the `telnyx-docs` MCP before writing code.
- Small, reviewable changes, with pytest tests for Python logic. After a change, tell me exactly
  which command to run to verify it.

## Session Logging Rules (persistent)
- `SESSION.md` is the single source-of-truth for our interactive session log. It is **not committed** (in `.gitignore`), so all build evidence stays private.
- `DAY*_LOG.md` files and `SESSION.md` are never committed.
- Each session step must include:
  - What was done (command, code change, prompt used)
  - The exact prompt text when delegating to OpenCode/AI (copy from PLAN.md §8 if available)
  - Evidence (log lines, curl output, pytest results, screenshots)
  - Any bugs: symptom → evidence → root cause → fix → proof (before/after)
  - **Key decision** — why X over Y, with tradeoffs
  - **Interview talking point** — 1-2 sentences summarizing the lesson
- Future sessions: read `SESSION.md` first to know where we are; append new steps under the appropriate Day; never start a new log file.
- Do **NOT** delete or overwrite previous session entries in `SESSION.md`. Append only.
- scripts/sync-shared.sh                      # before shipping a Python function
- pytest                                      # in a Python function folder
- uvicorn app:app --port 8080 --interface asgi3 --lifespan off   # local run (see scaffold README)
- telnyx-edge types && npm run typecheck      # in functions/caller-session
- telnyx-edge ship                            # from the function dir
- telnyx-edge logs <fn> --tail
- telnyx-edge actors logs CallerSession --tail
- scripts/smoke.sh
