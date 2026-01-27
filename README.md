# Hook Manager

A Claude Code plugin that makes it easy to build, debug, and manage Claude Code hooks.

**Hooks you create just work.** Built-in validation confirms your hooks are configured correctly, and automatic telemetry lets you see exactly when they fire.

## Installation

**From inside Claude Code:**

```
/plugin marketplace add dodo-digital/dodo-marketplace
/plugin install create-hooks
```

**From terminal:**

```bash
claude plugin marketplace add dodo-digital/dodo-marketplace
claude plugin install create-hooks
```

**Or install directly from GitHub:**

```bash
claude plugin install github:hwells4/create-hooks
```

## Usage

Just ask:

```
"I need a hook that validates bash commands"
"Help me debug my broken hook"
"What hooks do I have running?"
```

Or invoke directly:

```
/create-hooks:create-hook
```

## Why This Plugin?

**Hooks that just work.** Every hook you create is:

- **Validated** - Linting confirms syntax, permissions, and settings are correct before you deploy
- **Observable** - Built-in telemetry shows you when hooks fire and what they return
- **Conflict-free** - Analyzes existing hooks to prevent them from stepping on each other

No more guessing if your hook is running. No more silent failures.

## What It Does

- **Creates hooks** - Generates working hooks for any event type in any language
- **Validates before deploy** - Catches configuration errors before they bite you
- **Tracks execution** - See exactly when hooks fire and what they do
- **Debugs issues** - When something's wrong, helps you figure out why
- **Provides templates** - Ready-to-use patterns for common tasks

## Hook Events

| Event | When It Fires | Can Block? |
|-------|---------------|------------|
| PreToolUse | Before a tool runs | Yes |
| PostToolUse | After a tool succeeds | Feedback only |
| PermissionRequest | Permission dialog appears | Yes |
| UserPromptSubmit | You send a prompt | Yes |
| Stop | Claude finishes a task | Yes (continue) |
| SubagentStop | Subagent finishes | Yes (continue) |
| SessionStart | Session begins | Context + env vars |
| SessionEnd | Session ends | Cleanup only |
| PreCompact | Before context compaction | No |
| Notification | System notification | No |

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

## Quick Reference

**Exit Codes:**
- `exit 0` - Success
- `exit 2` - Block the action
- `exit 1` - Error (logged, doesn't block)

**Settings Location:**
- User: `~/.claude/settings.json` (all projects)
- Project: `.claude/settings.json` (this project, version controlled)
- Local: `.claude/settings.local.json` (this project, gitignored)

## License

MIT
