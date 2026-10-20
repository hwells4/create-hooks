# Hook Events

Which event to hook, what it can control, and what its matcher filters. Output shapes are in `io.md`; full per-event schemas are in the official docs.

## Event table

Control legend: **block** stops the action (exit 2 or a JSON decision); **feedback** reaches the agent but the action already happened; **context** adds text to the agent's context; **side effect** means output is ignored.

| Event | Fires | Matcher filters | Control | Codex |
|---|---|---|---|---|
| SessionStart | session begins, resumes, clears, compacts, forks | `startup` `resume` `clear` `compact` `fork` | context; title, watch paths, env file | yes |
| Setup | `--init-only`, or `-p` with `--init` / `--maintenance` | `init` `maintenance` | side effect | no |
| InstructionsLoaded | a CLAUDE.md or rules file loads | load reason | side effect | no |
| UserPromptSubmit | a prompt is submitted | none | block, context | yes |
| UserPromptExpansion | a slash command expands | command name | block, context | no |
| MessageDisplay | assistant text is displayed | none | replace displayed text only | no |
| PreToolUse | before a tool call | tool name | allow, deny, ask, defer; rewrite input; context | yes (no ask, no defer) |
| PermissionRequest | a permission prompt is about to show | tool name | approve or deny for the human | yes |
| PermissionDenied | auto mode denied a call | tool name | `retry: true` only | no |
| PostToolUse | after a tool succeeds | tool name | feedback, context, replace output | yes |
| PostToolUseFailure | after a tool fails | tool name | feedback, context | no |
| PostToolBatch | after a batch of parallel calls resolves | none | block the next model call, context | no |
| Notification | the runtime notifies the human | notification type | side effect | no |
| SubagentStart | a subagent spawns | agent type | context | yes |
| SubagentStop | a subagent finishes | agent type | block (keep it working) | yes |
| TaskCreated / TaskCompleted | a task is created / completed | none | block | no |
| TeammateIdle | an agent-team teammate goes idle | none | block (keep it working) | no |
| Stop | the main agent finishes its turn | none | block (keep it working), context | yes |
| StopFailure | the turn ended on an API error | error type | side effect | no |
| Interrupt | the user interrupts the turn | none | side effect, 1s budget | Codex only |
| ConfigChange | a settings file changes mid-session | config source | block the change | no |
| CwdChanged / DirectoryAdded | working directory changes / is added | none / how added | side effect, env file | no |
| FileChanged | a watched file changes on disk | literal filenames | side effect, env file | no |
| WorktreeCreate / WorktreeRemove | a worktree is created / removed | none | replaces default git behavior | no |
| PreCompact / PostCompact | around context compaction | `manual` `auto` | Pre: block; Post: side effect | yes |
| PreModelSwitch / PostModelSwitch | around a model switch | target model name | Pre: block; Post: context | no |
| Elicitation / ElicitationResult | an MCP server asks the user for input | MCP server name | answer or decline | no |
| SessionEnd | session terminates | exit reason | side effect, 1.5s shared budget | yes (1s) |

The Control column describes Claude Code; where Codex controls less, `runtimes.md` says so. "no" in the Codex column means Codex has no such event, so a hook registered for it there never fires.

## Choosing

- **Stop a tool call before it runs**: PreToolUse. It sees the full input and can rewrite it (`updatedInput` replaces the whole input object).
- **Approve on the human's behalf**: PermissionRequest fires only when a prompt would appear, so it costs nothing on calls that are already allowed. PreToolUse `allow` skips the prompt for every matching call.
- **Guard files**: PreToolUse on `Write|Edit` sees the editing tools only. Writes through the shell (`sed -i`, `>`, `tee`) arrive as Bash calls, so a file guard that must hold also checks Bash commands, or relies on permission rules or the sandbox.
- **React to a result**: PostToolUse for success, PostToolUseFailure for failure (Claude). The tool has already run; feedback steers the next step.
- **Context about a whole batch** (several files read in parallel): PostToolBatch fires once; PostToolUse fires per call, concurrently.
- **Keep the agent working**: Stop, which receives `last_assistant_message` (read it instead of the transcript, which can lag) plus `background_tasks` and `session_crons` so a hook can tell "done" from "waiting on background work". Claude caps stop-hook continuations at 8 in a row.
- **Live state at session start**: SessionStart. Its plain stdout becomes context in both runtimes. Static guidance belongs in CLAUDE.md / AGENTS.md instead.
- **Per-prompt context**: UserPromptSubmit runs on every prompt with a 30s default timeout in Claude; it is hot path.
- **Environment variables for later shell commands**: write `export` lines to `$CLAUDE_ENV_FILE` from SessionStart, Setup, CwdChanged, or FileChanged (Claude only).
- **Something already happened and only needs logging**: use an async command hook on the event; nothing should wait on a logger.

## Matchers

- `"*"`, `""`, or omitted matches everything.
- Claude: a value of only letters, digits, `_`, `-`, spaces, `,` and `|` is an exact name or list (`Edit|Write`). Anything else is an unanchored JavaScript regex, so `Edit.*` also matches `NotebookEdit`; anchor with `^...$`.
- Codex: always a regex.
- MCP tools are `mcp__<server>__<tool>` in both; `mcp__github__.*` matches one server.
- Claude tool names: `Bash`, `Write`, `Edit`, `Read`, `Glob`, `Grep`, `WebFetch`, `WebSearch`, `Agent` (subagents), `NotebookEdit`, `AskUserQuestion`, `ExitPlanMode`, `PowerShell`. Codex names and aliases are in `runtimes.md`.
- A matcher on an event with no matcher support is ignored, and the hook fires on every occurrence.
