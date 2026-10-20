# Hook Handlers

Each entry in a matcher group's `hooks` array is a handler. All matching handlers for an event run in parallel; an identical handler defined in several Claude settings files runs once.

## Types

| Type | Runs | Claude events | Codex |
|---|---|---|---|
| `command` | a shell command or executable; payload on stdin | all | yes |
| `http` | POST of the payload to `url`; response body is the JSON answer | all but SessionStart, Setup | no |
| `mcp_tool` | a tool on an already-connected MCP server; its text output is read like stdout | all | yes |
| `prompt` | one model call that returns `{ok, reason}` | tool events, Stop, SubagentStop, UserPromptSubmit, UserPromptExpansion, Task*, TeammateIdle, PermissionRequest | parsed, skipped |
| `agent` | a subagent with Read/Grep/Glob, up to 50 turns; experimental | the prompt events minus PermissionRequest | parsed, skipped |

## Fields

Common to all types:

| Field | Meaning |
|---|---|
| `timeout` | seconds. Claude defaults: 600 for command/http/mcp_tool (30 on UserPromptSubmit and model-switch events, 10 on MessageDisplay), 30 for prompt, 60 for agent; SessionEnd hooks share 1.5s. Codex: 600, SessionEnd and Interrupt 1s (max 3). Set it explicitly on every blocking hook: a hung hook stalls the agent for the full default. |
| `statusMessage` | spinner text while the hook runs (both runtimes) |
| `if` | Claude only. One permission rule, such as `"Bash(git *)"` or `"Edit(*.ts)"`. The process starts only when the call matches. Evaluated on PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest, PermissionDenied; on any other event a hook with `if` never runs. No `&&` or lists: one rule per handler. `Edit(...)` covers every file-editing tool, Write included. For Bash it checks each subcommand and `$()` contents, but `Bash(git *)` misses `/usr/bin/git` and `sh -c '...'`; when the command can't be parsed, the hook runs anyway. Treat `if` as a prefilter for speed: the script still makes the decision. |
| `once` | Claude only, skill frontmatter only: remove the hook after its first successful run. |

Command handlers:

| Field | Meaning |
|---|---|
| `command` | the command string (shell form), or the executable when `args` is set |
| `args` | Claude only. Exec form: spawn `command` directly with this argument vector, no shell. Placeholders such as `${CLAUDE_PLUGIN_ROOT}` substitute safely. Codex ignores `args`, so a Codex hook gets the bare command. |
| `async` | run in the background; nothing waits. It cannot block or decide; its `additionalContext` / `systemMessage` arrive on the next turn (both runtimes; Codex runs up to 8 per session). |
| `asyncRewake` | Claude only. Background run that wakes the agent if it exits 2. |
| `onFailure` | Claude only (v2.1.295+; check `claude --version`). `"block"` makes a crash, timeout, bad JSON, or missing script block the action like exit 2. No effect on Stop, SubagentStop, TaskCompleted, TeammateIdle, or async hooks. The way to make a guardrail fail closed. |
| `shell` | Claude only. `"bash"` (default) or `"powershell"`. |
| `commandWindows` | Codex only. Windows override for `command`. |
| `additionalContextLimit` | Codex only. Tokens of `additionalContext` before Codex spills it to a file (default about 2,500). |

Prompt and agent handlers take `prompt` (with `$ARGUMENTS` replaced by the payload JSON; appended if absent), optional `model`, and `timeout`. Prompt handlers also take `continueOnBlock`.

## Exec form vs shell form

Shell form (no `args`) passes `command` to `sh -c`: variables expand, pipes work, and every path placeholder needs double quotes: `"\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/x.sh"`. Exec form (`args` set) has no shell, so quoting is unnecessary. A config shared with Codex uses shell form, because Codex has no `args`.

## Prompt and agent answers

The model answers `{"ok": true}` to allow or `{"ok": false, "reason": "..."}` to refuse; a prompt hook may add `"impossible": true` on Stop/SubagentStop to let the turn end when the condition can never be met. What `ok: false` does depends on the event:

- Stop, SubagentStop: the reason becomes the agent's next instruction and the turn continues.
- PreToolUse, PostToolUse: the turn ends with a warning by default; `continueOnBlock: true` hands the reason to the agent instead. Agent hooks always behave as if `continueOnBlock` were true.
- PostToolUseFailure, TaskCreated: the reason returns to the agent as a tool error.
- PermissionRequest, PermissionDenied: no effect. Use a command hook for those.

Write the prompt as a checkable condition ("every file named in last_assistant_message contains the change"), and keep it to what the payload or a quick file read can settle.
