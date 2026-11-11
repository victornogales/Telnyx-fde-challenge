# Rollback Reference — RefillLine

> **This file is part of commit `be0dab6`.** To rollback to this exact state: `git checkout be0dab6`

## Current Stable Commit

```
be0dab6
```

**Message:** `docs: add ROLLBACK.md and SESSION.md rollback reference — current stable c7eac3f`

**Date:** 2026-11-11

**Contains:** `ROLLBACK.md`, `SESSION.md` rollback section, all working code (scenarios 1–6 verified)

**Verified scenarios:** 1–6
- 1. Happy path refill
- 2. Callback (verify again)
- 3. Transfer (routing verified)
- 4. Wrong DOB retry
- 5. Lockout after 3 failures
- 6. After-hours (deterministic expression edge)

**Dynamic variables driving routing:**
- `after_hours_mode` → expression edge → `n_after_hours`
- `account_locked` → expression edge → `n_locked`

## How to Rollback

```bash
# Reset to this exact commit (includes rollback reference)
git checkout be0dab6

# Or to the commit just before this docs commit (same code, no ROLLBACK.md)
git checkout c7eac3f

# To go back to non-deterministic after-hours (LLM steering):
git checkout 72efe25
```

## Commit History (Recent)

| Commit | Message | Date |
|---|---|---|
| `be0dab6` | docs: add ROLLBACK.md and SESSION.md rollback ref | 2026-11-11 |
| `c7eac3f` | docs: deterministic routing confirmed | 2026-11-11 |
| `a7b7945` | feat: deterministic after-hours routing | 2026-11-11 |
| `72efe25` | docs: update TEST_GUIDE with after-hours | 2026-11-11 |
| `51fe449` | feat: polite hangup message | 2026-11-11 |
| `6f75d8d` | fix: increase KV timeout | 2026-11-11 |
