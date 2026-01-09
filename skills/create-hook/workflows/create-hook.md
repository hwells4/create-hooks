# Create Hook Workflow

Generate a new Claude Code hook with proper structure.

## Input Required

- **Event type**: PreToolUse, PostToolUse, Stop, SessionStart, etc.
- **Hook name**: Descriptive name (e.g., `validate-bash`, `auto-approve-reads`)
- **Purpose**: What the hook should do

## Step 1: Determine Hook Type

Based on the event and purpose, choose the appropriate template:

| Purpose | Template | Event |
|---------|----------|-------|
| Block dangerous operations | `python-validator.py` | PreToolUse |
| Auto-approve safe operations | `auto-approve.py` | PreToolUse |
| Inject context at start | `context-injection.py` | SessionStart |
| Inject context per-prompt | `context-injection.py` | UserPromptSubmit |
| Ensure work completion | `stop-gate.py` | Stop |
| Forward notifications | `notification-forwarder.sh` | Notification |
| Simple pattern blocking | `bash-validator.sh` | PreToolUse |

## Step 2: Generate the Hook Script

### Python hooks (recommended for complex logic)

```python
#!/usr/bin/env python3
"""
{hook_name} - {purpose}
Event: {event_type}
Matcher: {matcher if applicable}
"""

import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Your logic here
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Example: Block or allow based on conditions
    # if should_block:
    #     print("Reason for blocking", file=sys.stderr)
    #     sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Bash hooks (for simple operations)

```bash
#!/bin/bash
# {hook_name} - {purpose}
# Event: {event_type}

set -e

INPUT=$(cat)

# Extract fields (using python for reliable JSON parsing)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))")

# Your logic here

exit 0
```

## Step 3: Save and Make Executable

1. Save to `.claude/hooks/{hook_name}.py` (or `.sh`)
2. Make executable: `chmod +x .claude/hooks/{hook_name}.py`
3. Test manually: `echo '{"tool_name":"Test"}' | python3 .claude/hooks/{hook_name}.py`

## Step 4: Add to Settings

Add hook configuration to `.claude/settings.json`:

```json
{
  "hooks": {
    "{event_type}": [
      {
        "matcher": "{matcher}",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{hook_name}.py"
          }
        ]
      }
    ]
  }
}
```

### Matcher patterns

- Exact tool: `"Write"`, `"Bash"`, `"Read"`
- Multiple tools: `"Write|Edit|MultiEdit"`
- Regex: `"mcp__.*"` (all MCP tools)
- All tools: `"*"` or `""`

### Events without matchers

For `UserPromptSubmit`, `Stop`, `SubagentStop`, `SessionEnd`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{hook_name}.py"
          }
        ]
      }
    ]
  }
}
```

### SessionStart with matcher

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/{hook_name}.sh"
          }
        ]
      }
    ]
  }
}
```

## Step 5: Test the Hook

1. Restart Claude Code session (hooks are snapshotted at startup)
2. Trigger the event (e.g., write a file for PostToolUse)
3. Check verbose mode (Ctrl+O) for hook execution
4. Use `claude --debug` for detailed output

## Common Patterns

### Block with stderr (exit 2)
```python
print("Reason shown to Claude", file=sys.stderr)
sys.exit(2)
```

### Allow with JSON (exit 0)
```python
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Auto-approved"
    }
}))
sys.exit(0)
```

### Continue working (Stop hook)
```python
print(json.dumps({
    "decision": "block",
    "reason": "You forgot to run tests. Run: npm test"
}))
sys.exit(0)
```
