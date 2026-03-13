# Hook Manager

Build Claude Code hooks without the guesswork.

Hooks let you run arbitrary code at specific points in Claude Code's lifecycle — before a tool runs, after a file is written, when a session starts, when Claude stops. They're the extension point for enforcing rules, injecting context, automating approvals, and wiring Claude into your workflow.

This plugin handles the tedious parts: boilerplate, JSON schemas, settings configuration, conflict detection, validation, and debugging. You describe what you want, it builds a working hook.

## Installation

```
/plugin marketplace add https://github.com/hwells4/hwells4-marketplace.git
/plugin install create-hooks@hwells4-plugins
```

## What Are Hooks?

Hooks are shell commands or scripts that Claude Code executes at defined points in its lifecycle. They receive JSON on stdin with context about what's happening, and they respond with exit codes and optional output.

```
You type a prompt
  → UserPromptSubmit hooks fire (can modify or block the prompt)

Claude decides to run a tool
  → PreToolUse hooks fire (can block the tool or inject context)

The tool executes
  → PostToolUse hooks fire (can give Claude feedback on what it just did)

Claude finishes
  → Stop hooks fire (can tell Claude to keep going)
```

Hooks are configured in your settings file and can be scoped to specific tools using matchers:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/validate-code.sh"
          }
        ]
      }
    ]
  }
}
```

That's it. Every time Claude writes or edits a file, your script runs.

## Why Use This Plugin?

Writing a hook from scratch means getting the JSON schema right, setting the correct exit codes, configuring settings with the right matcher syntax, making the script executable, and hoping it doesn't conflict with your other hooks. Most people get at least one of those wrong.

This plugin:

- **Analyzes your existing hooks first** so new ones don't conflict
- **Generates correct boilerplate** for any event type, in any language
- **Validates everything** — syntax, permissions, settings config, exit codes
- **Adds telemetry by default** so you can see exactly when hooks fire
- **Scales with you** — from a single hook to a full dispatcher routing to dozens of checks

## Usage

Describe what you want in plain language:

```
"Block any bash command that runs rm -rf"
"Auto-approve all file reads in my project"
"Inject my coding standards at session start"
"Validate that every React component has a testID"
"Log all tool usage to a file"
```

Or invoke directly:

```
/create-hooks:create-hook
```

## Hook Events

| Event | When It Fires | What It Can Do |
|-------|---------------|----------------|
| **PreToolUse** | Before a tool runs | Block it, modify it, or inject context |
| **PostToolUse** | After a tool succeeds | Give Claude feedback on what it just did |
| **UserPromptSubmit** | You send a prompt | Rewrite it, block it, or add context |
| **PermissionRequest** | Permission dialog appears | Auto-approve or auto-deny |
| **Stop** | Claude finishes a task | Tell it to keep going |
| **SubagentStop** | A subagent finishes | Tell it to keep going |
| **SessionStart** | Session begins | Set env vars, inject context |
| **SessionEnd** | Session ends | Clean up resources |
| **PreCompact** | Before context compaction | Add notes to preserve |
| **Notification** | System notification | Forward to Slack, email, etc. |

## Examples

### Block dangerous commands

A `PreToolUse` hook that prevents Claude from running destructive shell commands:

```bash
#!/bin/bash
# Reads JSON from stdin, checks the command
JSON=$(cat)
command=$(echo "$JSON" | jq -r '.tool_input.command // empty')

if echo "$command" | grep -qE 'rm\s+-rf|DROP\s+TABLE|:(){ :|:& };:'; then
    echo "Blocked dangerous command: $command" >&2
    exit 2
fi
exit 0
```

### Auto-approve safe operations

A `PreToolUse` hook that auto-approves reads and searches:

```python
#!/usr/bin/env python3
import json, sys

data = json.load(sys.stdin)
safe_tools = ["Read", "Glob", "Grep", "WebSearch"]

if data.get("tool_name") in safe_tools:
    json.dump({"decision": "approve"}, sys.stdout)
    sys.exit(0)

sys.exit(0)
```

### Inject context at session start

A `SessionStart` hook that loads project-specific instructions:

```bash
#!/bin/bash
if [ -f ".claude/project-context.md" ]; then
    context=$(cat .claude/project-context.md)
    echo "$context"
fi
exit 0
```

### Enforce coding standards on every file write

A `PostToolUse` hook that checks files after Claude writes them:

```bash
#!/bin/bash
JSON=$(cat)
file_path=$(echo "$JSON" | jq -r '.tool_input.file_path // empty')

# Only check code files
case "$file_path" in
    *.ts|*.tsx|*.js|*.jsx) ;;
    *) exit 0 ;;
esac

# Check for console.log
violations=$(grep -n 'console\.log' "$file_path" 2>/dev/null || true)
if [ -n "$violations" ]; then
    echo "Found console.log statements — remove before committing:"
    echo "$violations"
    exit 2
fi
exit 0
```

## Structuring Hooks for Scale

A single hook is simple. But as your project grows, you'll want hooks that are fast, easy to add, and don't step on each other.

### Keep hooks focused

One hook, one job. A hook that validates bash commands shouldn't also check file permissions. Smaller hooks are easier to test, debug, and reuse.

### Use matchers to limit scope

Don't run a file validation hook on every tool call. Use matchers to target specific tools:

```json
{
  "matcher": "Write|Edit|MultiEdit",
  "hooks": [{ "type": "command", "command": ".claude/hooks/validate-code.sh" }]
}
```

### Bail early

Hooks run on every matching event. The fastest hook is one that exits immediately when it doesn't apply:

```bash
# Skip non-code files in the first 5 lines
case "$file_path" in
    *.ts|*.tsx|*.js|*.jsx) ;;
    *) exit 0 ;;
esac
```

### Consolidate when it gets crowded

When you have several hooks on the same event all doing similar work — parsing the same JSON, resolving the same file path — consider a dispatcher: one entry point that does the shared work once and routes to individual check scripts. The plugin includes templates for this and will recommend it automatically when it detects the opportunity.

### Use the debug wrapper

Every hook this plugin creates includes a telemetry wrapper by default. It logs when hooks fire, what they return, and how long they take — with less than 1ms overhead:

```bash
tail -f .claude/hooks/.debug.log
```

## Templates Included

| Template | What It Does |
|----------|--------------|
| `bash-validator.sh` | Blocks dangerous shell commands |
| `python-validator.py` | Complex validation with JSON output |
| `auto-approve.py` | Auto-approves safe operations |
| `context-injection.py` | Injects context at session start or per-prompt |
| `stop-gate.py` | Ensures work completion before stopping |
| `permission-handler.py` | Handles permission dialogs programmatically |
| `notification-forwarder.sh` | Forwards notifications to external services |
| `dispatcher.sh` | Routes multiple checks through one entry point |
| `dispatcher.py` | Python equivalent for complex routing logic |

## Quick Reference

**Exit codes:**
- `0` — Success (hook passes, no action taken)
- `2` — Block the action (stderr shown to Claude as feedback)
- `1` — Error (logged, doesn't block)

**Input:** JSON on stdin with `tool_name`, `tool_input`, `tool_result`, `session_id`

**Settings locations:**
- Project: `.claude/settings.json` (version controlled)
- User: `~/.claude/settings.json` (all projects)
- Local: `.claude/settings.local.json` (gitignored)

**Hooks run in parallel.** All matching hooks fire simultaneously with a 60-second timeout.

## License

MIT
