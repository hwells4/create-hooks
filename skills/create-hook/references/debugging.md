# Hook Debugging & Execution Details

## Execution Details

### Timeout
- **Default**: 60 seconds per hook command
- **Configurable**: Per command via `timeout` field (in seconds)
- **Independent**: Timeout on one command doesn't affect others

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "python3 slow-validation.py",
      "timeout": 120
    }
  ]
}
```

### Parallelization
- All matching hooks run **in parallel**
- Multiple hooks for same event/matcher execute simultaneously
- Order is not guaranteed

### Deduplication
- Identical hook commands are automatically deduplicated
- Same command from multiple sources runs only once

### Environment
- **Working directory**: Current directory when Claude Code started
- **CLAUDE_PROJECT_DIR**: Absolute path to project root
- **CLAUDE_CODE_REMOTE**: `"true"` if running in web/remote environment, empty/unset for local CLI

```bash
#!/bin/bash
# Use CLAUDE_PROJECT_DIR for portable scripts
python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/my-hook.py"

# Check if running remotely
if [ "$CLAUDE_CODE_REMOTE" = "true" ]; then
  # Skip desktop notifications in remote environment
  exit 0
fi
```

### Input/Output by Event

| Event | Input | Output |
|-------|-------|--------|
| PreToolUse | JSON via stdin | Verbose mode (ctrl+o) |
| PostToolUse | JSON via stdin | Verbose mode (ctrl+o) |
| PermissionRequest | JSON via stdin | Verbose mode (ctrl+o) |
| Stop/SubagentStop | JSON via stdin | Verbose mode (ctrl+o) |
| UserPromptSubmit | JSON via stdin | **stdout added to context** |
| SessionStart | JSON via stdin | **stdout added to context** |
| SessionEnd | JSON via stdin | Debug only (`--debug`) |
| Notification | JSON via stdin | Debug only (`--debug`) |
| PreCompact | JSON via stdin | Debug only (`--debug`) |

---

## Configuration Safety

Direct edits to hooks in settings files don't take effect immediately:

1. **Snapshot at startup** - Hooks captured when session starts
2. **Session-locked** - Uses snapshot throughout session
3. **External modification warning** - Alerts if hooks.json changes
4. **Manual review required** - Use `/hooks` menu to apply changes

This prevents malicious runtime injection of hooks.

---

## Basic Troubleshooting

### Hook not running?

1. **Check registration**: Run `/hooks` in Claude Code
2. **Verify JSON syntax**:
   ```bash
   python3 -m json.tool .claude/settings.json > /dev/null && echo "Valid"
   ```
3. **Check matcher**: Tool names are case-sensitive (`Write` not `write`)
4. **Check permissions**: `chmod +x .claude/hooks/your-script.py`
5. **Test manually**:
   ```bash
   echo '{"tool_name":"Write","tool_input":{"file_path":"/test"}}' | \
     python3 .claude/hooks/your-script.py
   echo "Exit code: $?"
   ```

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Hook not found | Wrong path | Use `$CLAUDE_PROJECT_DIR` for relative paths |
| JSON parse error | Unescaped quotes | Use `\"` inside JSON strings |
| Matcher not matching | Case mismatch | `Write` not `write` |
| Permission denied | Not executable | `chmod +x script.py` |
| Python not found | Wrong interpreter | Use `python3` not `python` |
| Timeout | Slow operation | Increase `timeout` or optimize |

---

## Advanced Debugging

### Enable Debug Mode

```bash
claude --debug
```

Shows detailed hook execution:
```
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: python3 .claude/hooks/validate.py with timeout 60000ms
[DEBUG] Hook command completed with status 0: <stdout output>
```

### Verbose Mode (Ctrl+O)

Toggle verbose mode to see hook progress:
- Which hook is running
- Command being executed
- Success/failure status
- Output or error messages

### Add Logging to Your Hooks

```python
#!/usr/bin/env python3
import json
import sys
from datetime import datetime

LOG_FILE = "/tmp/claude-hooks.log"

def log(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {message}\n")

try:
    data = json.load(sys.stdin)
    log(f"Received: {json.dumps(data)[:200]}...")
except Exception as e:
    log(f"Error: {e}")
    sys.exit(0)

# Your logic here
tool_name = data.get("tool_name", "")
log(f"Processing tool: {tool_name}")

sys.exit(0)
```

### Test Hook Input/Output

```bash
# Create test input
cat > /tmp/test-input.json << 'EOF'
{
  "session_id": "test123",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/tmp/test.txt",
    "content": "hello world"
  }
}
EOF

# Run hook with test input
cat /tmp/test-input.json | python3 .claude/hooks/your-hook.py
echo "Exit code: $?"

# Check stderr
cat /tmp/test-input.json | python3 .claude/hooks/your-hook.py 2>&1
```

### Validate JSON Output

```bash
# Check if hook returns valid JSON
cat /tmp/test-input.json | python3 .claude/hooks/your-hook.py | python3 -m json.tool
```

### Monitor Hook Performance

```python
#!/usr/bin/env python3
import json
import sys
import time

start = time.time()

# Your hook logic here
data = json.load(sys.stdin)
# ... processing ...

elapsed = time.time() - start
if elapsed > 5:  # Log slow hooks
    with open("/tmp/slow-hooks.log", "a") as f:
        f.write(f"Hook took {elapsed:.2f}s for {data.get('tool_name')}\n")

sys.exit(0)
```

---

## Healing a Broken Hook

### 1. Identify the Problem

```bash
# Check if hook file exists
ls -la .claude/hooks/

# Check if executable
file .claude/hooks/your-hook.py

# Check syntax (Python)
python3 -m py_compile .claude/hooks/your-hook.py

# Check syntax (Bash)
bash -n .claude/hooks/your-hook.sh
```

### 2. Test in Isolation

```bash
# Create minimal test case
echo '{"tool_name":"Test"}' | python3 .claude/hooks/your-hook.py
```

### 3. Check for Missing Dependencies

```python
#!/usr/bin/env python3
# Add at top of hook to check dependencies
try:
    import yaml  # or whatever you need
except ImportError as e:
    import sys
    print(f"Missing dependency: {e}", file=sys.stderr)
    sys.exit(0)  # Exit gracefully, don't block
```

### 4. Add Fallback Error Handling

```python
#!/usr/bin/env python3
import json
import sys

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)  # Can't parse, allow through

try:
    # Your logic here
    pass
except Exception as e:
    # Log error but don't block
    with open("/tmp/hook-errors.log", "a") as f:
        f.write(f"Error: {e}\n")
    sys.exit(0)

sys.exit(0)
```

### 5. Temporarily Disable

Edit settings to comment out the broken hook, restart session:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          // Temporarily disabled
          // { "type": "command", "command": "broken-hook.py" }
        ]
      }
    ]
  }
}
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `/hooks` | View registered hooks in Claude Code |
| `claude --debug` | Detailed hook execution logs |
| `Ctrl+O` | Toggle verbose mode for hook output |
| `python3 -m json.tool file.json` | Validate JSON |
| `chmod +x script.py` | Make script executable |
| `echo '{}' \| python3 hook.py` | Test hook manually |
