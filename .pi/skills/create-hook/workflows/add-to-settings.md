# Add Hook to Settings Workflow

Add a hook configuration to settings.json.

## Settings File Locations

| File | Scope | Git? |
|------|-------|------|
| `~/.claude/settings.json` | All projects (user) | No |
| `.claude/settings.json` | This project | Yes |
| `.claude/settings.local.json` | This project (local) | No (gitignored) |

## Step 1: Choose Settings File

- **User hooks** (applies everywhere): `~/.claude/settings.json`
- **Project hooks** (shared with team): `.claude/settings.json`
- **Local hooks** (just for you): `.claude/settings.local.json`

## Step 2: Read Current Settings

```bash
cat .claude/settings.json
```

## Step 3: Add Hook Configuration

### If no hooks section exists

Add the entire hooks object:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "hooks": {
    "{EventType}": [
      {
        "matcher": "{pattern}",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{script}.py"
          }
        ]
      }
    ]
  }
}
```

### If hooks section exists

Add a new event or matcher:

**New event:**
```json
{
  "hooks": {
    "ExistingEvent": [...],
    "NewEvent": [
      {
        "matcher": "{pattern}",
        "hooks": [
          {
            "type": "command",
            "command": "..."
          }
        ]
      }
    ]
  }
}
```

**New matcher for existing event:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "ExistingPattern",
        "hooks": [...]
      },
      {
        "matcher": "NewPattern",
        "hooks": [
          {
            "type": "command",
            "command": "..."
          }
        ]
      }
    ]
  }
}
```

**Additional hook for same matcher:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "existing-hook.py"
          },
          {
            "type": "command",
            "command": "new-hook.py"
          }
        ]
      }
    ]
  }
}
```

## Event Types Reference

| Event | Needs Matcher? | Common Matchers |
|-------|----------------|-----------------|
| PreToolUse | Yes | Tool names: `Write`, `Bash`, `Edit\|Write` |
| PostToolUse | Yes | Same as PreToolUse |
| PermissionRequest | Yes | Same as PreToolUse |
| UserPromptSubmit | No | - |
| Stop | No | - |
| SubagentStop | No | - |
| SessionStart | Optional | `startup`, `resume`, `clear`, `compact` |
| SessionEnd | No | - |
| PreCompact | Optional | `manual`, `auto` |
| Notification | Optional | `permission_prompt`, `idle_prompt` |

## Step 4: Validate JSON

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo "Valid JSON"
```

## Step 5: Restart Claude Code

Hooks are snapshotted at startup. Changes require:
1. Exit current session
2. Start new session
3. Check `/hooks` menu to verify registration

## Common Configurations

### Validate all file writes
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate-writes.py"
          }
        ]
      }
    ]
  }
}
```

### Load context on session start
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/session-init.sh"
          }
        ]
      }
    ]
  }
}
```

### Ensure work completion before stopping
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/stop-gate.py"
          }
        ]
      }
    ]
  }
}
```

### Auto-approve safe operations
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/auto-approve.py"
          }
        ]
      }
    ]
  }
}
```
