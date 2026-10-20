# Hook Input and Output

## Input

Every payload carries `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and on most events `permission_mode` (`default`, `plan`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`). Inside a subagent, `agent_id` and `agent_type` are added.

- Claude adds `prompt_id`, `effort.level`, and `scratchpad_dir`; `model` arrives only on SessionStart, and sometimes not even there.
- Codex adds `model` on every event and `turn_id` on turn-scoped events.
- `cwd` follows the agent (into worktrees, after `cd`). `CLAUDE_PROJECT_DIR` stays at the project root where the session started.
- Tool events add `tool_name`, `tool_input`, `tool_use_id`; PostToolUse adds `tool_response`; PostToolUseFailure adds `error`, `is_interrupt`, `duration_ms`.
- `transcript_path` can lag the live conversation. On Stop and SubagentStop read `last_assistant_message`.

`lib/hook-io.sh` reads the common fields into `HOOK_*` variables with one jq call.

## Exit codes

| Stdout | Exit 0 | Exit 2 | Other exit |
|---|---|---|---|
| one valid JSON object | its fields apply | blocks; JSON can't override the block | Claude applies the fields; print JSON with exit 0 so both runtimes agree |
| invalid JSON | hook error, action goes ahead | blocks, stderr is the reason | hook error, action goes ahead |
| plain text or nothing | success | blocks, stderr is the reason | hook error, action goes ahead |

- Exit 2 shows the agent **stderr**. Stdout from an exit-2 run is discarded.
- On exit 0, stderr is never shown to the agent.
- Plain stdout becomes context only on SessionStart and UserPromptSubmit in both runtimes, plus UserPromptExpansion and PostModelSwitch in Claude and SubagentStart in Codex. Elsewhere it is ignored, and on Codex Stop and SubagentStop it is invalid.
- Exit 2 does nothing on PermissionRequest (answer with the decision object) or on side-effect events.
- WorktreeCreate and WorktreeRemove fail on any non-zero exit.

## JSON output

Print one object, alone on stdout. `hookSpecificOutput` needs `hookEventName` set to the current event.

| Intent | Event | Shape |
|---|---|---|
| refuse a tool call | PreToolUse | `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}` |
| ask the human | PreToolUse | same, `"ask"` (Claude only) |
| skip the permission prompt | PreToolUse | same, `"allow"` |
| rewrite the input | PreToolUse | add `"updatedInput": {...}` beside the decision; it replaces the whole input |
| approve for the human | PermissionRequest | `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}` |
| deny for the human | PermissionRequest | `"behavior": "deny", "message": "..."` |
| keep working / flag a result | Stop, SubagentStop, PostToolUse, UserPromptSubmit, PostToolBatch | `{"decision": "block", "reason": "..."}` |
| add context | most events | `{"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "..."}}` |
| halt the agent entirely | any | `{"continue": false, "stopReason": "..."}` (Codex: unsupported on PreToolUse and PermissionRequest, where the hook counts as failed and the call goes ahead) |
| warn the human | any | `{"systemMessage": "..."}` |

When several PreToolUse hooks disagree, Claude applies `deny` over `defer` over `ask` over `allow`. `defer` pauses a headless `claude -p` run at a single tool call for an outside UI and is ignored interactively.

Text limits: `additionalContext`, `systemMessage`, and plain stdout are capped at 10,000 characters each in Claude (the rest goes to a file the agent is not told to read); Codex spills context past about 2,500 tokens. Put what the agent must see first.

Write context as facts ("This repo uses `bun test`"). Text phrased as system commands can trip prompt-injection defenses and get surfaced to the user instead of used.

Deprecated: top-level `decision: "approve"|"block"` on PreToolUse (use `permissionDecision`), and `updatedMCPToolOutput` (use `updatedToolOutput`).
