# MCP Tool Hooks

MCP (Model Context Protocol) servers expose tools that can be hooked just like built-in tools.

## Naming Pattern

```
mcp__<server-name>__<tool-name>
```

**Examples:**
| Tool | Description |
|------|-------------|
| `mcp__memory__create_entities` | Memory server's create entities |
| `mcp__filesystem__read_file` | Filesystem server's read file |
| `mcp__github__search_repositories` | GitHub server's search |
| `mcp__gmail-autoauth__search_emails` | Gmail server's email search |
| `mcp__playwright__browser_navigate` | Playwright browser navigation |

## Matcher Patterns

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [{ "type": "command", "command": "echo 'Memory operation'" }]
      },
      {
        "matcher": "mcp__.*__write.*",
        "hooks": [{ "type": "command", "command": "./validate-mcp-write.py" }]
      },
      {
        "matcher": "mcp__github__.*",
        "hooks": [{ "type": "command", "command": "./log-github-ops.sh" }]
      }
    ]
  }
}
```

## Common Use Cases

### 1. Log All MCP Operations

```python
#!/usr/bin/env python3
import json
import sys
from datetime import datetime

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")

if tool_name.startswith("mcp__"):
    with open("mcp-operations.log", "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {tool_name}\n")

sys.exit(0)
```

### 2. Rate Limit MCP Calls

```python
#!/usr/bin/env python3
import json
import os
import sys
import time

RATE_LIMIT_FILE = "/tmp/mcp-rate-limit.json"
MAX_CALLS_PER_MINUTE = 30

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")

if not tool_name.startswith("mcp__"):
    sys.exit(0)

# Load call history
try:
    with open(RATE_LIMIT_FILE) as f:
        history = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    history = []

# Clean old entries (older than 60 seconds)
now = time.time()
history = [t for t in history if now - t < 60]

if len(history) >= MAX_CALLS_PER_MINUTE:
    print(f"Rate limit exceeded: {MAX_CALLS_PER_MINUTE} MCP calls/minute", file=sys.stderr)
    sys.exit(2)

# Record this call
history.append(now)
with open(RATE_LIMIT_FILE, "w") as f:
    json.dump(history, f)

sys.exit(0)
```

### 3. Validate MCP Tool Inputs

```python
#!/usr/bin/env python3
import json
import sys

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# Block dangerous GitHub operations
if tool_name == "mcp__github__delete_repository":
    print("Repository deletion requires manual confirmation", file=sys.stderr)
    sys.exit(2)

# Validate email recipients
if tool_name == "mcp__gmail-autoauth__send_email":
    to = tool_input.get("to", "")
    if "@competitor.com" in to:
        print("Cannot send emails to competitor domains", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
```

### 4. Block Specific MCP Servers

```python
#!/usr/bin/env python3
import json
import sys

BLOCKED_SERVERS = ["filesystem", "shell"]  # Block risky servers

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")

if tool_name.startswith("mcp__"):
    parts = tool_name.split("__")
    if len(parts) >= 2:
        server = parts[1]
        if server in BLOCKED_SERVERS:
            print(f"MCP server '{server}' is blocked by policy", file=sys.stderr)
            sys.exit(2)

sys.exit(0)
```

## Discovering MCP Tools

To see what MCP tools are available in your session:

1. Check your MCP server configurations
2. Look for tools matching `mcp__*` in Claude Code's tool list
3. Run with `claude --debug` to see MCP tool invocations

## Settings Example

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/mcp-logger.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__github__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/github-audit.py"
          }
        ]
      }
    ]
  }
}
```
