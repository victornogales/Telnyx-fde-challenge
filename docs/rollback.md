# Rollback Guide

> Quick reference for reverting to known-good commits.

## Current Working Commit

```
100ec1b  mcp: tools invoke end-to-end via API workflow upload
```

This commit represents the state where:
- MCP server connects and lists 6 tools
- Workflow JSON is valid API-compatible format
- Expression edges use nested structure
- `tools_mode: append` on all prompt nodes
- `allowed_tools` populated via API (Portal UI bug workaround)
- Custom pharmacist transfer tool wired
- All 6 MCP tools pass `scripts/smoke.ps1`

---

## How to Rollback

### Option A: Soft reset (keep changes unstaged)

```bash
git log --oneline -5
git reset --soft 100ec1b
```

### Option B: Hard reset (discard all changes after commit)

```bash
git log --oneline -5
git reset --hard 100ec1b
```

⚠️ **Warning:** `--hard` discards all uncommitted changes. Save any WIP first with `git stash` or commit to a branch.

### Option C: Revert (keep history, undo changes safely)

```bash
git revert HEAD --no-edit    # undo last commit
# or revert a range
git revert <bad-commit>..HEAD --no-edit
```

### Option D: Checkout specific files from the good commit

```bash
git checkout 100ec1b -- assistant/workflow.json functions/refill-mcp/function.py scripts/smoke.ps1
```

---

## Re-deploy After Rollback

If you rolled back function code, re-ship:

```bash
cd functions/refill-mcp && telnyx-edge ship
cd functions/refill-webhook && telnyx-edge ship
cd functions/caller-session && telnyx-edge ship
```

If you rolled back workflow JSON, re-upload:

```bash
curl.exe -X PATCH "https://api.telnyx.com/v2/ai/assistants/assistant-9befc905-0e48-42f9-b65f-ae91b269bb65" `
  -H "Authorization: Bearer $TELNYX_API_KEY" `
  -H "Content-Type: application/json" `
  -d "@assistant/workflow.json"
```

---

## Tag the Working Commit (Recommended)

Create a lightweight tag so you never have to memorise the hash:

```bash
git tag working-mcp 100ec1b
git log --oneline --decorate | head -5
```

Then rollback is simply:

```bash
git reset --hard working-mcp
```
