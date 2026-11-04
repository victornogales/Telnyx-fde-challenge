# Project: RefillLine (Telnyx FDE challenge)

Voice assistant for pharmacy refills. Telnyx AI Assistant (Conversation Workflow) →
Edge Function `refill-webhook` (dynamic variables; owns Stateful Actor `CallerSession`; KV flags)
and Edge Function `refill-mcp` (MCP server over HTTP, references `CallerSession`, KV cache, openFDA).
Full design: PLAN.md. Follow it; ask before deviating.

## Hard rules
- TypeScript, no heavy dependencies. Web APIs only (fetch, crypto.subtle). No Node http/fs.
- Never invent `@telnyx/edge-runtime` APIs. If unsure, search the `telnyx-docs` MCP or ask me.
- Actor bindings go in telnyx.toml `[[actors]]` (NOT func.toml). KV binding: `[storage.kv.KV] id = "<uuid>"`.
- KV keys: no colons; use `/` (e.g. `flag/after_hours_mode`, `cache/fda/<name>`).
- Dynamic variables webhook response MUST be `{"dynamic_variables": {...}}` and every value a STRING.
- Webhook must answer < 1000 ms; on any error return SAFE_DEFAULTS with HTTP 200.
- Every request/actor method/tool call logs exactly one JSON line via `log()` with trace_id.
  Never log DOB, names or raw phone numbers — use callerKey (sha256 prefix).
- MCP: stateless JSON-RPC 2.0 at POST /mcp; tools return `{content:[{type:"text",text}], isError}`; never throw.
- Verification is enforced server-side via CallerSession.isVerified(conversationId).
- Small, reviewable changes. After a change, tell me exactly which command to run to verify it.

## Commands
- telnyx-edge types        # after binding changes
- telnyx-edge ship         # from the function dir
- telnyx-edge logs <fn> --tail
- telnyx-edge actors logs CallerSession --tail
- scripts/smoke.sh
