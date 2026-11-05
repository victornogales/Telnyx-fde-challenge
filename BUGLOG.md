# Bug log

One entry per real bug, written when it happens.

<!--
## YYYY-MM-DD HH:MM — <symptom in one line>
Symptom:
Evidence: (log lines / metrics / trace_id)
Root cause:
Fix:
Proof: (before/after)
-->

## 2026-11-05 11:00 — Python build rejects package directories; only flat modules work
Symptom: `telnyx-edge ship` fails during wheel build with:
  `error: package directory 'shared' does not exist`
Evidence: 
  - Build logs show setuptools `egg_info` executed, then fails writing `top_level.txt`.
  - Reproduced with `packages = ["function", "shared"]`, `packages = ["shared"]`, and nested `function/shared/`.
  - Flat module `py-modules = ["function"]` with a single `function.py` ships successfully.
Root cause: The platform's Python build pipeline only supports a **single flat module** (`py-modules`),
  not package directories (`packages`), even when setuptools is used. This is a platform packaging
  limitation (the wheel build step inside the container can't discover sub-packages).
Fix: Inlined all shared helpers (`log`, `ids`, `kv`, `session_client`) directly into `function.py`.
  Kept `functions/_shared/` as the source-of-truth for copy-paste into `refill-mcp` on Day 3.
  - `refill-webhook` is now one file: `function.py` (~370 lines).
Proof: Revision `ecba8961aaf7` deployed successfully; curl returns dynamic variables and logs show
  JSON event lines with `outcome: ok` and `total_ms < 200`.
Lessons -> design: Do not attempt package directories in Python Edge Functions. Keep each function
  to one flat module. For shared code, copy-paste from `functions/_shared/` before shipping.

## 2026-11-05 12:00 — TypeScript secret access and Windows curl body behavior
Symptom: `caller-session` gateway returned `401 unauthorized` on every RPC call, then after fixing that, `{"ok":false,"error":"invalid json"}`.
Evidence:
  - `telnyx-edge secrets list` confirmed `INTERNAL_TOKEN` existed and was correct.
  - Gateway code read `env.INTERNAL_TOKEN` (via `env as Record<string, string>` cast). It was always `undefined`.
  - After switching to `process.env.INTERNAL_TOKEN`, auth passed but `req.json()` threw on a body that `curl.exe` had sent.
  - PowerShell `Invoke-RestMethod` with the exact same JSON body succeeded immediately.
  - Platform logs showed `outcome: "bad_json"` with `latency_ms: 0` — body was empty/unreadable.
Root cause #1 (secrets): TypeScript Edge Functions expose **bindings** (actors, KV, etc.) on `env`, but **secrets** are injected as plain environment variables and must be read via `process.env`.
Root cause #2 (curl): Windows `curl.exe` does not reliably deliver POST body bytes to the Edge Compute TypeScript `fetch` handler. The `Request` object has no body when read via `req.text()` or `req.json()`.
Fix:
  - Changed `env.INTERNAL_TOKEN` → `process.env.INTERNAL_TOKEN` in `src/index.ts`.
  - Diagnostic/testing: use PowerShell `Invoke-RestMethod` instead of `curl.exe` for POSTs to TS functions.
  - `caller-session` now ships with `process.env` for secrets and `env` for actor bindings only.
Proof: Concurrency test (`scripts/concurrency_test.py`) fires 20 parallel `recordCall`s via `httpx` and succeeds with `callCount` incrementing from 45 → 66.
Lessons → design:
  - In TypeScript Edge Functions: `env` = typed bindings; `process.env` = secrets and plain env vars.
  - On Windows, avoid `curl.exe` for POST smoke tests against TS functions; use `Invoke-RestMethod` or Python `httpx`.

## 2026-11-04 10:15 — New actor type unreachable after first deploy
Symptom: every request → HTTP 500 after ~5.2 s:
  "failed to lookup actor … FailedPrecondition … did not find address for actor '<acct>__Counter/demo'"
Evidence: 11 identical errors 10:15:40–10:37:11 (telnyx-edge logs env-check);
  `actors inspect Counter` = ready, 0 instances; no actor logs (call never reached the actor);
  ship status = succeeded, deployment active.
Fix: re-ship. New revision rolled out 11:02–11:03 (SIGTERM burst), first 200 at 11:04:39.
Root cause: platform-side — new actor type was registered but not placed on first deploy (not our code; unmodified scaffold).
Lessons → design: try/catch + safe defaults (never bare 500); internal timeout < 1.5 s webhook budget
  (failed lookup costs ~5 s); log success too; post-ship smoke test must exercise the actor, not just deploy status.

## 2026-11-05 09:15 — Python function build succeeds but runtime can't import 'function' module
Symptom: every request → HTTP 404 after deploy; logs show repeated `ModuleNotFoundError: No module named 'function'`.
Evidence: 
  - Build succeeds with hatchling (wheel contains `function/__init__.py` and `function/func.py`).
  - Runtime wrapper `/opt/app-root/src/.func/build/service/main.py` does `from function import new` → fails.
  - Reproduced with unmodified Python scaffold (`telnyx-edge new-func -l python`) after fixing BOM in pyproject.toml.
  - Local `python -m build` produces a valid wheel; `python -c "from function import new"` works locally.
Root cause: platform-side — the runtime's PYTHONPATH or installation step doesn't find the hatchling-built wheel. 
Fix: switched from `function/` package directory (scaffold default) to single-file `function.py` at root with setuptools `py-modules = ["function"]`.
  - Root cause: the platform's Python runtime wrapper (`main.py`) does `from function import new`, but the hatchling/setuptools-built wheel with a `function/` package isn't on PYTHONPATH at runtime. This is a platform-side packaging bug.
  - Workaround: a single-file module `function.py` installs correctly and is importable by the wrapper.
  - Also fixed: BOM in pyproject.toml caused `tomllib.TOMLDecodeError` on first build attempt.
Proof: deployed at https://refill-webhook-8d5c4fc7-b.telnyxcompute.com; curl returns `{"dynamic_variables": ...}` and logs show `httpx_import_ok: true` on Python 3.11.13.
Lessons → design: Python Edge Compute packaging is undocumented; test the simplest possible scaffold first before adding code; watch for Windows BOM in generated TOML files.

  
