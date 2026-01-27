# Create Hook Workflow

Generate a new Claude Code hook with proper structure.

## Input Required

- **Event type**: PreToolUse, PostToolUse, Stop, SessionStart, etc.
- **Hook name**: Descriptive name (e.g., `validate-bash`, `auto-approve-reads`)
- **Purpose**: What the hook should do

## Step 1: Set Up Debug Wrapper (Default)

**Always do this unless user explicitly opts out.**

Copy `templates/debug-wrap.sh` to the project's hooks directory:

```bash
mkdir -p .claude/hooks
cp templates/debug-wrap.sh .claude/hooks/debug-wrap.sh
chmod +x .claude/hooks/debug-wrap.sh
```

This logs every hook invocation (~0.5ms overhead). View logs:
```bash
tail -f .claude/hooks/.debug.log
```

## Step 2: Write the Hook

Write the hook in whatever language makes sense (Python, Bash, etc.)

**Python example:**
```python
#!/usr/bin/env python3
import json
import sys

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")

# Your logic here

sys.exit(0)
```

**Bash example:**
```bash
#!/bin/bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))")

# Your logic here

exit 0
```

Save to `.claude/hooks/{hook_name}.py` (or `.sh`, `.js`, whatever) and make executable:
```bash
chmod +x .claude/hooks/{hook_name}.py
```

## Step 3: Add to Settings

Add to `.claude/settings.json` **with debug wrapper**:

```json
{
  "hooks": {
    "{event_type}": [
      {
        "matcher": "{matcher}",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/debug-wrap.sh {interpreter} \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{hook_name}"
          }
        ]
      }
    ]
  }
}
```

**Without debug wrapper** (only if user explicitly opts out):
```json
{
  "command": "{interpreter} \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{hook_name}"
}
```

### Matcher patterns
- Exact tool: `"Write"`, `"Bash"`, `"Read"`
- Multiple tools: `"Write|Edit|MultiEdit"`
- Regex: `"mcp__.*"` (all MCP tools)
- All tools: `"*"` or `""`

### Events without matchers
For `UserPromptSubmit`, `Stop`, `SubagentStop`, `SessionEnd` - omit the `matcher` field.

## Step 4: Test

1. Test manually first: `echo '{"tool_name":"Test"}' | .claude/hooks/{hook_name}`
2. Restart Claude Code (hooks snapshot at startup)
3. Trigger the event
4. Check debug log: `tail -f .claude/hooks/.debug.log`

## Exit Codes

- `exit 0` - Success
- `exit 1` - Error (logged, doesn't block)
- `exit 2` - Block action (stderr shown to Claude)
