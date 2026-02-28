# Hook Manager

A Claude Code plugin that makes it easy to build, debug, and manage Claude Code hooks.

**Hooks you create just work.** Built-in validation confirms your hooks are configured correctly, and automatic telemetry lets you see exactly when they fire. When you have multiple hooks on the same event, the dispatcher pattern keeps them fast and conflict-free.

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
"I have five PostToolUse hooks and they keep conflicting"
"Help me consolidate my hooks into a dispatcher"
```

Or invoke directly:

```
/create-hooks:create-hook
/create-hooks:create-hook dispatcher PostToolUse
```

## Why This Plugin?

**Hooks that just work.** Every hook you create is:

- **Validated** - Linting confirms syntax, permissions, and settings are correct before you deploy
- **Observable** - Built-in telemetry shows you when hooks fire and what they return
- **Conflict-free** - Analyzes existing hooks to prevent them from stepping on each other
- **Dispatcher-aware** - Automatically detects when multiple hooks should be consolidated

No more guessing if your hook is running. No more silent failures.

## What It Does

- **Creates hooks** - Generates working hooks for any event type in any language
- **Consolidates hooks** - Merges multiple hooks on the same event into a single dispatcher
- **Validates before deploy** - Catches configuration errors before they bite you
- **Tracks execution** - See exactly when hooks fire and what they do
- **Debugs issues** - When something's wrong, helps you figure out why
- **Provides templates** - Ready-to-use patterns for common tasks

## The Dispatcher Pattern

When you have 3+ hooks on the same event, they all fire in parallel — each one parsing the same JSON, resolving the same file path, classifying the same file type. A dispatcher replaces them with **one process** that does the shared work once and routes to individual checks.

**Before** — 9 hooks, 9 processes, 9 JSON parses:

```
PostToolUse "Write" fires → 9 separate hooks:
  ├── testids.sh          (parse JSON, resolve path, classify, check) ~12ms
  ├── accessibility.sh    (parse JSON, resolve path, classify, check) ~14ms
  ├── security.sh         (parse JSON, resolve path, classify, check) ~12ms
  └── ... 6 more doing the same shared work
  Total: 9 processes, 9 JSON parses, 9 settings entries
```

**After** — 1 dispatcher, 1 process, 1 JSON parse:

```
PostToolUse "Write" fires → 1 dispatcher:
  └── post-tool-dispatcher.sh  (parse ONCE, classify ONCE)  ~18ms
      ├── testids.sh          → pre-parsed args, just the check
      ├── accessibility.sh    → pre-parsed args, just the check
      ├── security.sh         → pre-parsed args, just the check
      └── ... 6 more, only the ones that apply
  Total: 1 process, 1 JSON parse, 1 settings entry
```

### How it works

The dispatcher reads JSON from stdin once, resolves the file path, classifies the file type, then loops over scripts in a `checks/` directory. Each check receives pre-computed arguments — no JSON parsing needed.

```
.claude/hooks/
  post-tool-dispatcher.sh     ← registered in settings (one entry)
  checks/                     ← auto-discovered (no settings changes)
    accessibility.sh
    security.sh
    testids.sh
    theme-tokens.sh
```

### Adding a new check

Drop a file in `checks/` and make it executable. That's it. No settings changes. The dispatcher discovers it automatically.

```bash
cat > .claude/hooks/checks/no-console-log.sh << 'EOF'
#!/bin/bash
# Check: no console.log in production code
# Args: $1=file_path $2=rel_path $3=is_test $4=is_config

file_path="$1" rel_path="$2" is_test="$3"

# Skip test files
if [[ "$is_test" == "true" ]]; then exit 0; fi

violations=$(grep -n 'console\.log' "${file_path}" 2>/dev/null || true)

if [ -n "${violations}" ]; then
    echo "console.log found in ${rel_path}:"
    echo ""
    echo "${violations}"
    echo ""
    echo "Remove console.log statements before committing."
    exit 2
fi
exit 0
EOF
chmod +x .claude/hooks/checks/no-console-log.sh
```

### When to use a dispatcher

| Situation | Recommendation |
|-----------|---------------|
| 3+ hooks on the same event | Use a dispatcher |
| Hooks share work (JSON parse, path resolve) | Use a dispatcher |
| You want "drop a file" extensibility | Use a dispatcher |
| Only 1-2 hooks per event | Standalone hooks are fine |
| Hooks do fundamentally different things | Keep them separate |

The plugin detects this automatically — when you create a new hook and there are already 2+ hooks on that event, it recommends consolidating into a dispatcher first.

### Two dispatcher flavors

| Template | Best For |
|----------|----------|
| `dispatcher.sh` | Simple pattern checks (grep, awk). Checks are separate files in `checks/`. Recommended for most use cases. |
| `dispatcher.py` | Complex logic (AST parsing, API calls). Handlers are functions in one file. Better when checks share data structures. |

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
| `dispatcher.sh` | Shell dispatcher — routes to `checks/` directory |
| `dispatcher.py` | Python dispatcher — routes to handler functions |

## Quick Reference

**Exit Codes:**
- `exit 0` - Success
- `exit 2` - Block the action
- `exit 1` - Error (logged, doesn't block)

**Settings Location:**
- User: `~/.claude/settings.json` (all projects)
- Project: `.claude/settings.json` (this project, version controlled)
- Local: `.claude/settings.local.json` (this project, gitignored)

**Dispatcher Check Interface:**
```
$1 = file_path    (absolute)
$2 = rel_path     (relative, for display)
$3 = is_test      ("true" or "false")
$4 = is_config    ("true" or "false")
```

## License

MIT
