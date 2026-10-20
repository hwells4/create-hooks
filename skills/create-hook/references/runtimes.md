# Claude Code and Codex

Codex adopted Claude Code's hook contract: the same config shape (`{"hooks": {Event: [{matcher, hooks: [...]}]}}`), the same stdin fields, the same exit-2 rule, the same `hookSpecificOutput` names. A hook built on `lib/hook-io.sh` and tested against both fixture sets runs in both. This file is the list of places where they part.

## Where hooks live

| | Claude Code | Codex |
|---|---|---|
| user | `~/.claude/settings.json` | `~/.codex/hooks.json` or `[hooks]` in `~/.codex/config.toml` |
| project | `.claude/settings.json` (committed), `.claude/settings.local.json` (personal) | `.codex/hooks.json` or `.codex/config.toml`; loads only when the project's `.codex/` layer is trusted |
| plugin | `hooks/hooks.json` in the plugin root | the same file, or a `hooks` entry in `.codex-plugin/plugin.json` |
| skill / agent frontmatter | `hooks:` in SKILL.md or an agent file | none |
| project path in a command | `"$CLAUDE_PROJECT_DIR"/...` | `"$(git rev-parse --show-toplevel)"/...` (the session may start in a subdirectory) |
| plugin path in a command | `"${CLAUDE_PLUGIN_ROOT}"/...` | the same; Codex also sets `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `PLUGIN_ROOT`, `PLUGIN_DATA` |

A plugin can ship one `hooks/hooks.json` for both runtimes. A project needs one config per runtime, both pointing at the same script.

## Activation

- Claude reads settings edits live; `/hooks` shows what loaded and from where.
- Codex runs a new or edited non-managed hook only after the user reviews and trusts it in `/hooks`. For settings-file hooks, trust covers the declaration (event, matcher, handler fields), so editing the script it calls keeps the trust while any edit to the config entry needs a fresh review: keep logic in the script and the entry stable. Plugin hooks are also fingerprinted by the plugin's contents, so every plugin update needs a fresh trust.
- `[features].hooks` is on by default in current Codex.

## Tools

| Claude | Codex stdin `tool_name` | Codex matcher accepts | Input shape |
|---|---|---|---|
| `Bash` | `Bash` (shell and `exec_command`) | `Bash` | `{"command": "..."}` in both |
| `Write`, `Edit` | `apply_patch` | `apply_patch`, `Write`, `Edit` | Claude: `file_path` + content fields. Codex: `{"command": "<patch text>"}` with `*** Add File:`, `*** Update File:`, `*** Delete File:`, `*** Move to:` lines, paths relative to `cwd`. `hook_paths` handles both. |
| `Agent` | `spawn_agent` | `spawn_agent`, `Agent` | different fields |
| `mcp__server__tool` | same | same | same |

Codex cannot hook its hosted tools (web search), and `write_stdin` to a running command does not re-run PreToolUse. Codex PostToolUse also fires after a Bash command exits non-zero, which covers part of what Claude's PostToolUseFailure does.

## Config fields

Codex ignores fields it doesn't know, silently. In a Codex config:

- `if` is ignored, so the script must filter for itself. The templates already do.
- `args` is ignored, so an exec-form hook runs `command` with no arguments. Use shell form.
- `onFailure`, `asyncRewake`, `shell`, and `once` are ignored. A Codex guardrail that crashes fails open.
- `prompt` and `agent` handlers are parsed and skipped; `http` is unsupported. Judgment hooks are Claude only.
- Events Codex lacks (see `events.md`) never fire.

## Output

| Output | Claude | Codex |
|---|---|---|
| PreToolUse `deny` | yes | yes |
| PreToolUse `ask` | prompts the human | unsupported: the hook fails and the call goes ahead. `hook_ask` sends a deny instead. |
| PreToolUse `allow` | skips the prompt | parsed; prefer PermissionRequest to approve |
| PreToolUse `defer` | headless only | no |
| `updatedInput` | object replacing the input | Bash and `apply_patch`: `{"command": "<string>"}` only |
| PermissionRequest `updatedInput`, `updatedPermissions`, `interrupt` | yes | fail closed (the request is denied) |
| `continue: false` on PreToolUse / PermissionRequest | halts | hook fails, call goes ahead |
| `updatedToolOutput` (PostToolUse) | yes | no |
| `terminalSequence` | yes | no |
| plain text on Stop | ignored | invalid |
| `CLAUDE_ENV_FILE`, `CLAUDE_PROJECT_DIR` | set | absent: use payload `cwd` and the git root |

## Detecting the runtime in a script

`hook_read` sets `HOOK_RUNTIME`: `codex` when the payload has `turn_id` or a Codex tool name (`apply_patch`, `spawn_agent`), else `claude`. SessionStart in Codex has no `turn_id`; when a SessionStart script must know, set it in the command: `HOOK_RUNTIME=codex "$(git rev-parse --show-toplevel)"/.agents/hooks/x.sh`.
