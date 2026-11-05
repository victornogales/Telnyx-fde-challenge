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

  
