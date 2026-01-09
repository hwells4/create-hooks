# Hook Manager

Your hooks, handled. A Claude Code plugin that takes the pain out of building, debugging, and organizing Claude Code hooks.

## Installation

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

## What It Does

- **Scaffolds hooks** - Generates proper boilerplate for any event type so you can focus on logic
- **Analyzes conflicts** - Checks your existing hooks before creating new ones to prevent chaos
- **Provides templates** - Ready-to-use patterns for common tasks (auto-approve, stop gates, context injection)
- **Tests before deploy** - Validates hooks actually work before they touch your workflow
- **Debugs the weird stuff** - When your hook does something inexplicable, it helps you figure out why

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
| `intelligent-stop-prompt.json` | LLM-evaluated task completion |
| `permission-handler.py` | Handles permission dialogs programmatically |
| `notification-forwarder.sh` | Forwards notifications to external services |

## Scaffold Script

Generate hooks from the command line:

```bash
python3 skills/create-hook/scripts/scaffold-hook.py PreToolUse validate-bash
python3 skills/create-hook/scripts/scaffold-hook.py SessionStart load-context --lang=bash
python3 skills/create-hook/scripts/scaffold-hook.py Stop ensure-tests
```

## Quick Reference

**Exit Codes:**
- `exit 0` - Success (stdout shown in verbose mode)
- `exit 2` - Block action (stderr shown to Claude)
- `exit 1` - Non-blocking error (logged only)

**Settings Location:**
- User: `~/.claude/settings.json`
- Project: `.claude/settings.json`
- Local: `.claude/settings.local.json`

## License

MIT
