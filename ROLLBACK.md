# Rollback Reference — RefillLine

> **Demo day freeze:** `git checkout demo-day` (tag points to `15cb7a6`)

## Demo Day Freeze

```
demo-day  →  15cb7a6
```

**Message:** `docs: finalize README, architecture, demo script, opencode.json for demo day freeze`

**Date:** 2026-11-11

**Contains everything needed for submission:**
- `README.md` — setup, architecture, debugging story, phone number, URLs
- `docs/architecture.md` — component diagrams, primitive choices, data flow
- `DEMO_SCRIPT.md` — 10-minute walkthrough with fallback plans
- `opencode.json` — Telnyx plugin active
- `docs/TEST_GUIDE.md` — full test procedures for all scenarios
- Working code for all 7 challenge requirements

**Tag commands:**
```bash
# Jump to demo-day freeze
git checkout demo-day

# Or use the commit directly
git checkout 15cb7a6
```

---

## Previous Stable Commit

```
be0dab6
```

**Message:** `docs: add ROLLBACK.md and SESSION.md rollback reference`

**Note:** Before README overhaul and demo script creation.

---

## How to Rollback

```bash
# To demo-day freeze (recommended):
git checkout demo-day

# To pre-freeze state:
git checkout be0dab6

# To deterministic routing commit:
git checkout c7eac3f

# To non-deterministic after-hours:
git checkout 72efe25
```

---

## Commit History

| Commit | Message | Tag |
|---|---|---|
| `15cb7a6` | docs: finalize README, architecture, demo script | **demo-day** |
| `be0dab6` | docs: add ROLLBACK.md and SESSION.md rollback ref | — |
| `c7eac3f` | docs: deterministic routing confirmed | — |
| `a7b7945` | feat: deterministic after-hours routing | — |
| `72efe25` | docs: update TEST_GUIDE with after-hours | — |
| `51fe449` | feat: polite hangup message | — |
| `6f75d8d` | fix: increase KV timeout | — |
