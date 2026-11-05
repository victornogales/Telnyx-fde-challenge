# Day 2 Progress Snapshot

Taken: 2026-11-05 12:05 UTC

## Current overall progress

| Day | Status | Blockers |
|---|---|---|
| Day 1 (Tooling + walking skeleton) | ✅ Complete | None |
| Day 2 (Actor + KV + webhook) | ✅ Complete | None |
| Day 3 (MCP server) | Not started | None |
| Day 4 (Full workflow) | Not started | Number still pending approval |

## Day 2 is complete — evidence

### 1. `caller-session` (TypeScript actor gateway) — DEPLOYED
- URL: `https://caller-session-51645523-7.telnyxcompute.com`
- Endpoints: `POST /rpc`, `GET /health`
- Actor: `CallerSession` with 7 methods + alarm
- Status: `deployed` (active)

### 2. `refill-webhook` (Python ASGI) — DEPLOYED
- URL: `https://refill-webhook-8d5c4fc7-b.telnyxcompute.com`
- Reads KV flags (`refills_enabled`, `after_hours_mode`)
- Calls gateway `recordCall` in parallel
- Returns `{"dynamic_variables": {...}}` with all strings
- Status: `deployed` (active)

### 3. Secrets (shared)
- `KV_NAMESPACE_ID` = `3208b4c8-7ac1-4f42-a73d-ab9bfd4fc8ee`
- `INTERNAL_TOKEN` = set
- `CALLER_SESSION_URL` = set
- `MCP_TOKEN` = set

### 4. KV namespace `refillline-kv` — seeded
- `flag/refills_enabled` = `"true"`
- `flag/after_hours_mode` = `"false"`
- `flag/max_verify_attempts` = `"3"`

### 5. Concurrency proof
- File: `scripts/concurrency_test.py` — uses `INTERNAL_TOKEN` as-is
- Result: 20 parallel recordCalls, zero lost updates
- Output saved: `docs/concurrency-test.md`

## Key discoveries documented

1. **Python flat-module constraint** — BUGLOG.md, AGENTS.md, DOGFOOD.md
2. **Actor placement bug on first deploy** — BUGLOG.md
3. **TypeScript secrets via `process.env`** (not `env`) — BUGLOG.md, DOGFOOD.md
4. **Windows `curl.exe` POST bodies unreliable** against TS fetch — BUGLOG.md, DOGFOOD.md

## What's ready for Day 3

- `_shared/` Python helpers exist (source-of-truth for copy-paste)
- `scripts/sync-shared.sh` exists
- KV and secrets already in place
- `MCP_TOKEN` already generated

## Day 3 known plan

Per PLAN.md §8:

1. Scaffold: `telnyx-edge new-func -l python -n refill-mcp`
2. Spike S2: minimal hand-rolled MCP (`POST /mcp`, `initialize`, `tools/list`, echo tool)
3. Ship + test with Portal play button
4. Build 6 tools with actor integration, KV caching, openFDA lookup
5. Write `function/data/patients.py` with synthetic data (~5 patients, keyed by real test phone numbers)
6. `pytest` + ship + smoke test

## Phone number status

Assistant created and number assigned, but **pending carrier approval** (max 24h). Do not test real calls until approved.

## How to resume next time

OpenCode agent should:
1. Read `PLAN.md` §8 Day 3
2. Read `AGENTS.md` for current rules
3. Check `progress.md`
4. Start with Step 1: scaffold `refill-mcp`
5. **Use the actual prompts from PLAN.md** for major code generation
