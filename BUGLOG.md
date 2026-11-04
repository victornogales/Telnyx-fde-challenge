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

  
