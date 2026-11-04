# Dogfooding Telnyx Inference via OpenCode

Notes on which Telnyx-hosted models I used, for what, and what worked or didn't.

## Setup

- OpenCode 1.19.5 (`npm i -g opencode-ai --allow-scripts=opencode-ai`), Windows 11, PowerShell
- Plugin `@telnyx/opencode` 0.1.5, project-scoped in `.opencode/` (`opencode.json` + `tui.json`)
- Auth: `opencode auth login --provider telnyx --method "API Key"`
- Default coding model: `telnyx/moonshotai/Kimi-K2.6`
- Telnyx docs MCP (`https://developers.telnyx.com/mcp`) attached so the model can look up real Edge/Assistant APIs instead of guessing

## Log

| Date | Model | Task | What worked | What didn't / how I corrected it |
|---|---|---|---|---|
| 2026-11-04 | Kimi-K3 (from the brief) | First `opencode run` hello test | Nothing | `UnknownError` with only an `err_…` ref. The model ID isn't offered on my account. `opencode models telnyx` listed what is: Kimi-K2.6, GLM-5.2, GLM-5.1-FP8, MiniMax-M3-MXFP8, MiniMax-M2.7. Switched to Kimi-K2.6. Lesson: an unknown model gives a generic error rather than "model not found". |
| 2026-11-04 | Kimi-K2.6 | Hello test | Responded; OpenCode log confirms `llm.provider=telnyx llm.model=moonshotai/Kimi-K2.6` | n/a |
| 2026-11-04 | n/a | Plugin install | Provider and models worked right away | `opencode plugin @telnyx/opencode` without `-g` installs for the **current folder**. I first ran it from my home dir, so the config landed in `~\.opencode\`. Reinstalled from the repo root so the project carries its own config. |
| 2026-11-04 | n/a | `/telnyx` TUI model manager | Plugin source registers `/telnyx`, `/telnyx-models` and a "Manage Telnyx models" palette entry | Never appears on Windows (plugin 0.1.5, OpenCode 1.19.5). The logs show `tui.json` loaded, but OpenCode logs nothing about TUI plugin loading, even with `--log-level DEBUG --print-logs`. Suspect: the TUI part ships as raw `src/tui.tsx` and relies on OpenCode providing `@opentui/solid`/`solid-js`. Workaround: manage models in `~/.config/opencode/telnyx-models.json`; switch with `/models`. |

## Observations about Telnyx Inference

- The plugin exists partly to work around an API constraint: Telnyx rejects requests that include both function tools and `max_completion_tokens`/`max_tokens`. OpenCode normally sends both, so the plugin removes the output-token cap for the `telnyx` provider.
- The plugin fetches `GET /v2/ai/models` at startup and registers only models in the local allowlist (`telnyx-models.json`). The available list differed from the brief's examples, so check it rather than assuming.

## Edge Compute tooling notes (found while dogfooding)

- `telnyx-edge new-func` does not run `npm install`; `ship` bundles locally with esbuild and fails until `node_modules` exists. The scaffold's README does say so: read it first.
- `telnyx-edge types` must run inside a function folder (one containing `telnyx.toml`/`func.toml`), not the repo root.
- First deploy of a new actor type: unreachable for 22+ minutes ("did not find address for actor"); a re-ship fixed it. See BUGLOG.md.
