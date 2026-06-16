# Hook Events Reference

Complete input/output schemas for all Claude Code hook events.

## Common Fields (All Events)

All hooks receive this base structure via stdin:

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../session.jsonl",
  "cwd": "/current/working/directory",
  "permission_mode": "default|plan|acceptEdits|dontAsk|bypassPermissions",
  "hook_event_name": "EventName"
}
```

---

## PreToolUse

**When:** After Claude creates tool parameters, before tool executes.

**Input:**
```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

**Matchers:** Tool names - `Write`, `Edit`, `Bash`, `Task`, `mcp__*`

**Blocking:** Exit code 2 blocks tool, stderr shown to Claude.

**JSON Output (exit 0):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Shown to user (allow/ask) or Claude (deny)",
    "updatedInput": { "modified": "input" }
  }
}
```

---

## PostToolUse

**When:** Immediately after tool completes successfully.

**Input:**
```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." },
  "tool_response": { "filePath": "...", "success": true },
  "tool_use_id": "toolu_01ABC123..."
}
```

**Matchers:** Same as PreToolUse.

**Blocking:** Exit code 2 shows stderr to Claude (tool already ran).

**JSON Output (exit 0):**
```json
{
  "decision": "block",
  "reason": "Feedback for Claude",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Extra info for Claude"
  }
}
```

---

## PermissionRequest

**When:** User is shown a permission dialog.

**Input:** Same as PreToolUse.

**Matchers:** Tool names.

**JSON Output (exit 0):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow|deny",
      "updatedInput": { "command": "npm run lint" },
      "message": "Reason for deny",
      "interrupt": false
    }
  }
}
```

---

## UserPromptSubmit

**When:** User submits a prompt, before Claude processes it.

**Input:**
```json
{
  "hook_event_name": "UserPromptSubmit",
  "prompt": "The user's submitted prompt text"
}
```

**Matchers:** None (no matcher field).

**Blocking:** Exit code 2 blocks prompt, shows stderr to user.

**Context Injection:** Exit code 0 + stdout text adds context for Claude.

**JSON Output (exit 0):**
```json
{
  "decision": "block",
  "reason": "Shown to user (not Claude)",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Context added for Claude"
  }
}
```

---

## Stop

**When:** Main Claude agent finishes responding (not on user interrupt).

**Input:**
```json
{
  "hook_event_name": "Stop",
  "stop_hook_active": true
}
```

`stop_hook_active` is true when Claude is already continuing due to a previous stop hook. Check this to prevent infinite loops.

**Matchers:** None.

**Blocking:** Exit code 2 continues Claude with stderr as instructions.

**JSON Output (exit 0):**
```json
{
  "decision": "block",
  "reason": "REQUIRED: Instructions for Claude to continue"
}
```

---

## SubagentStop

**When:** A subagent (Task tool) finishes responding.

**Input:** Same as Stop.

**Blocking/Output:** Same as Stop.

---

## SessionStart

**When:** Claude Code starts or resumes a session.

**Input:**
```json
{
  "hook_event_name": "SessionStart",
  "source": "startup|resume|clear|compact"
}
```

**Matchers:** `startup`, `resume`, `clear`, `compact`

**Environment:** Has access to `CLAUDE_ENV_FILE` for persisting env vars:
```bash
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export MY_VAR=value' >> "$CLAUDE_ENV_FILE"
fi
```

**Context Injection:** Exit code 0 + stdout adds context for Claude.

**JSON Output (exit 0):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Context for Claude"
  }
}
```

---

## SessionEnd

**When:** Claude Code session ends.

**Input:**
```json
{
  "hook_event_name": "SessionEnd",
  "reason": "clear|logout|prompt_input_exit|other"
}
```

**Matchers:** None.

**Cannot block.** Use for cleanup/logging only.

---

## PreCompact

**When:** Before context compaction (auto or manual).

**Input:**
```json
{
  "hook_event_name": "PreCompact",
  "trigger": "manual|auto",
  "custom_instructions": "User's /compact message if manual"
}
```

**Matchers:** `manual`, `auto`

**Cannot block.** Use for logging or last-minute data saves.

---

## Notification

**When:** Claude Code sends a notification.

**Input:**
```json
{
  "hook_event_name": "Notification",
  "message": "Claude needs your permission to use Bash",
  "notification_type": "permission_prompt|idle_prompt|auth_success|elicitation_dialog"
}
```

**Matchers:** `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog`

**Cannot block.** Use for custom notification forwarding.
