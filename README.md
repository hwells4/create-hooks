# create-hooks

A Claude Code plugin for scaffolding hooks quickly. Generates bash scripts, Python handlers, and settings.json configuration for all hook events.

## Installation

```bash
claude plugin install github:hwells4/create-hooks
```

## Usage

```
/create-hooks:create-hook
```

Or with arguments:

```
/create-hooks:create-hook new PreToolUse validate-bash
/create-hooks:create-hook debug my-hook.py
/create-hooks:create-hook template auto-approve
/create-hooks:create-hook analyze
```

## What It Does

- **Scaffolds hooks** with proper boilerplate for any event type
- **Provides templates** for common patterns (auto-approve, stop gates, context injection)
- **Analyzes existing hooks** to prevent conflicts before you create new ones
- **Tests hooks** before deployment
- **Documents all hook events** with input/output schemas

## Hook Events

| Event | When | Can Block? |
|-------|------|------------|
| PreToolUse | Before tool runs | Yes |
| PostToolUse | After tool succeeds | Feedback only |
| PermissionRequest | Permission dialog shown | Yes |
| UserPromptSubmit | User sends prompt | Yes |
| Stop | Claude finishes | Yes (continue) |
| SubagentStop | Subagent finishes | Yes (continue) |
| SessionStart | Session begins | Context + env vars |
| SessionEnd | Session ends | Cleanup only |
| PreCompact | Before compaction | No |
| Notification | System notification | No |

## Templates Included

| Template | Use Case |
|----------|----------|
| `bash-validator.sh` | Block dangerous shell commands |
| `python-validator.py` | Complex validation with JSON output |
| `auto-approve.py` | Auto-approve safe operations |
| `context-injection.py` | Inject context at session start or per-prompt |
| `stop-gate.py` | Ensure work completion before stopping |
| `intelligent-stop-prompt.json` | LLM-evaluated task completion |
| `permission-handler.py` | Handle permission dialogs programmatically |
| `notification-forwarder.sh` | Forward notifications externally |

## Scaffold Script

Generate a hook from the command line:

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
