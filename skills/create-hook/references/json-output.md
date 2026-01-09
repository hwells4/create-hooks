# JSON Output Reference

Structured JSON responses for fine-grained hook control.

## When JSON is Processed

- **Exit code 0 only** - JSON in stdout is parsed for structured control
- **Exit code 2** - Only stderr used, stdout JSON ignored
- **Other exit codes** - stderr shown in verbose mode, execution continues

## Common Fields (All Events)

```json
{
  "continue": true,           // false stops Claude entirely
  "stopReason": "message",    // Shown to user when continue=false
  "suppressOutput": true,     // Hide stdout from transcript mode
  "systemMessage": "warning"  // Warning message shown to user
}
```

## PreToolUse Output

Control whether a tool call proceeds.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Explanation",
    "updatedInput": {
      "file_path": "/modified/path.txt"
    }
  }
}
```

| Decision | Effect |
|----------|--------|
| `allow` | Bypass permission system, tool runs immediately |
| `deny` | Block tool, reason shown to Claude |
| `ask` | Show confirmation dialog to user |

**Input Modification:**
- `updatedInput` modifies tool parameters before execution
- Can combine with `allow` (auto-approve modified input)
- Can combine with `ask` (show modified input for confirmation)

## PermissionRequest Output

Handle permission dialogs programmatically.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow|deny",
      "updatedInput": { "command": "safe-command" },
      "message": "Deny reason for Claude",
      "interrupt": false
    }
  }
}
```

| Field | Purpose |
|-------|---------|
| `behavior` | `allow` approves, `deny` rejects |
| `updatedInput` | Modify tool input (allow only) |
| `message` | Feedback to Claude (deny only) |
| `interrupt` | true stops Claude (deny only) |

## PostToolUse Output

Provide feedback after tool execution.

```json
{
  "decision": "block",
  "reason": "Error found in output",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Lint errors detected: 3 issues"
  }
}
```

| Field | Purpose |
|-------|---------|
| `decision` | `"block"` prompts Claude with reason |
| `reason` | Shown to Claude when blocking |
| `additionalContext` | Extra info for Claude to consider |

## UserPromptSubmit Output

Validate prompts and inject context.

```json
{
  "decision": "block",
  "reason": "Shown to user (not Claude)",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Injected context for Claude"
  }
}
```

**Context Injection Methods:**
1. **Plain stdout** - Simple text output becomes context
2. **additionalContext** - More discrete injection via JSON

| Field | Purpose |
|-------|---------|
| `decision` | `"block"` prevents prompt processing |
| `reason` | Shown to user (prompt erased) |
| `additionalContext` | Added to conversation context |

## Stop/SubagentStop Output

Control whether Claude should continue working.

```json
{
  "decision": "block",
  "reason": "You haven't run the tests yet. Run: npm test"
}
```

| Field | Purpose |
|-------|---------|
| `decision` | `"block"` forces Claude to continue |
| `reason` | **REQUIRED** - Instructions for Claude |

**Prevent Infinite Loops:**
Check `stop_hook_active` in input - if true, Claude is already continuing from a previous stop hook.

## SessionStart Output

Inject context at session start.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Recent git commits:\n- abc123 Fix bug\n- def456 Add feature"
  }
}
```

## Example: Auto-Approve Safe Files

```python
#!/usr/bin/env python3
import json
import sys

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

if tool_name == "Read":
    file_path = tool_input.get("file_path", "")
    if file_path.endswith((".md", ".txt", ".json")):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Safe file type auto-approved"
            }
        }))
        sys.exit(0)

sys.exit(0)
```

## Example: Block Dangerous Commands

```python
#!/usr/bin/env python3
import json
import sys

BLOCKED_PATTERNS = ["rm -rf", "sudo", "> /dev/"]

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

command = data.get("tool_input", {}).get("command", "")
for pattern in BLOCKED_PATTERNS:
    if pattern in command:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked: command contains '{pattern}'"
            }
        }))
        sys.exit(0)

sys.exit(0)
```
