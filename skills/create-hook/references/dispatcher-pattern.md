# The Dispatcher Pattern

A single hook that acts as a router, replacing multiple independent hooks on the same event with one fast coordinator that delegates work based on context.

## The Problem

Claude Code hooks run in parallel per event. When you register five hooks on `PostToolUse`, all five fire simultaneously on every tool call. This creates real problems:

1. **Redundant work** — Each hook independently parses the same JSON stdin, resolves the same file path, classifies the same file type, and most exit immediately because they don't apply
2. **Conflict risk** — Two hooks both return `exit 2` with different stderr messages. Two hooks both emit JSON with conflicting `permissionDecision` values. The outcome is unpredictable.
3. **Latency stacking** — While hooks run in parallel, each still has process startup overhead (~5-15ms for Python, ~2-5ms for Bash). Five hooks means five processes spawned for every single tool call.
4. **Settings sprawl** — Your `settings.json` becomes a wall of hook configurations. Hard to understand what fires when, hard to debug conflicts.
5. **No shared state** — Hook A resolves a file path to absolute. Hook B also needs to resolve the same file path. Each hook is isolated and duplicates the work.

### What parallel execution actually looks like

```
PostToolUse "Write" fires → 9 separate hooks:
  ├── testids.sh          (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~12ms
  ├── accessibility.sh    (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~14ms
  ├── sentry-catch.sh     (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~11ms
  ├── sentry-screen.sh    (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~10ms
  ├── theme-tokens.sh     (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~13ms
  ├── security.sh         (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~12ms
  ├── fetch-guard.sh      (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~10ms
  ├── no-forwardref.sh    (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~10ms
  └── reanimated-guard.sh (spawn bash, parse JSON, resolve path, classify file, check, exit 0) ~10ms
  Total processes spawned: 9
  Total JSON parses: 9 (same data)
  Total file classifications: 9 (same file)
  Settings entries needed: 9
```

## The Solution: One Hook, One Decision

Replace N hooks per event with a single dispatcher that:

1. Parses input once
2. Does shared work once (resolve path, classify file, filter non-applicable files)
3. Routes to the right handler(s)
4. Collects and merges output
5. Returns one coherent response

```
PostToolUse "Write" fires → 1 dispatcher:
  └── post-tool-dispatcher.sh  (spawn bash ONCE, parse JSON ONCE, classify ONCE)  ~18ms
      ├── testids.sh          → receives pre-parsed args, runs check
      ├── accessibility.sh    → receives pre-parsed args, runs check
      ├── sentry-catch.sh     → receives pre-parsed args, runs check
      ├── sentry-screen.sh    → receives pre-parsed args, runs check
      ├── theme-tokens.sh     → receives pre-parsed args, runs check
      ├── security.sh         → receives pre-parsed args, runs check
      ├── fetch-guard.sh      → receives pre-parsed args, runs check
      ├── no-forwardref.sh    → receives pre-parsed args, runs check
      └── reanimated-guard.sh → receives pre-parsed args, runs check
  Total processes: 1 dispatcher + only applicable checks
  Total JSON parses: 1
  Total file classifications: 1
  Settings entries: 1
```

## Reference Implementation

The canonical example is the `post-tool-dispatcher.sh` from the React Native Boilerplate project. It consolidates 9 code quality checks into a single `PostToolUse` hook.

### The dispatcher (`post-tool-dispatcher.sh`)

```bash
#!/bin/bash
# PostToolUse dispatcher: runs all code quality checks in a single process.
#
# Replaces 9 individual hooks with one entry point that:
#   1. Parses the JSON input once
#   2. Resolves the file path once
#   3. Skips non-code/test files once (for all checks)
#   4. Runs each check in .claude/hooks/checks/
#
# Each check script receives: $1=file_path $2=rel_path $3=is_test $4=is_config
# and exits 0 (pass) or 2 (warning with stdout).
#
# To add a new check: drop a .sh script in .claude/hooks/checks/
#
# Exit codes:
#   0 = all checks pass
#   2 = one or more non-blocking warnings

set -euo pipefail

CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checks"

# --- Common boilerplate (done ONCE for all checks) ---

JSON_INPUT=$(cat)
file_path=$(echo "${JSON_INPUT}" | jq -r '.tool_input.file_path // empty')

# Skip if no file path or file doesn't exist
if [ -z "${file_path}" ] || [ ! -f "${file_path}" ]; then
    exit 0
fi

# Resolve to absolute path
if [[ "${file_path}" != /* ]]; then
    file_path="${CLAUDE_PROJECT_DIR}/${file_path}"
fi

# Only check code files — bail immediately for .json, .md, .yml, etc.
case "${file_path}" in
    *.ts|*.tsx|*.js|*.jsx) ;;
    *) exit 0 ;;
esac

# Classify the file once
is_test="false"
case "${file_path}" in
    *__tests__*|*.test.*|*.spec.*|*/mocks/*|*/test/*|*mock*|*jest*) is_test="true" ;;
esac

is_config="false"
case "${file_path}" in
    *.config.*) is_config="true" ;;
esac

rel_path="${file_path#${CLAUDE_PROJECT_DIR}/}"

# --- Run all checks ---

output=""
had_warning=false

for check in "${CHECKS_DIR}"/*.sh; do
    [ -x "${check}" ] || continue

    result=""
    exit_code=0
    result=$("${check}" "${file_path}" "${rel_path}" "${is_test}" "${is_config}" 2>&1) || exit_code=$?

    if [ -n "${result}" ]; then
        if [ -n "${output}" ]; then
            output="${output}
---
"
        fi
        output="${output}${result}"
        if [ "${exit_code}" = "2" ]; then
            had_warning=true
        fi
    fi
done

# --- Output ---

if [ -n "${output}" ]; then
    echo "${output}"
    if ${had_warning}; then
        exit 2
    fi
fi

exit 0
```

### The checks directory

Each check is a self-contained script with a uniform interface:

```
.claude/hooks/
  post-tool-dispatcher.sh         # the dispatcher (registered in settings)
  checks/                         # handler plugins (auto-discovered)
    accessibility.sh              # Pressable/TouchableOpacity must have accessibilityLabel
    fetch-guard.sh                # use apiClient() instead of raw fetch()
    no-forwardref.sh              # React 19: ref as regular prop
    reanimated-guard.sh           # use react-native-reanimated, not legacy Animated
    security.sh                   # no sensitive data in logs, no hardcoded keys
    sentry-catch.sh               # catch blocks must call Sentry.captureException
    sentry-screen.sh              # screen files must import @sentry/react-native
    testids.sh                    # interactive elements must have testID
    theme-tokens.sh               # use theme tokens, not hardcoded hex/borderRadius
```

### The settings entry (just one)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post-tool-dispatcher.sh"
          }
        ]
      }
    ]
  }
}
```

### What each check looks like

Every check follows the same contract:

```bash
#!/bin/bash
# Check: {what it enforces}
# Args: $1=file_path $2=rel_path $3=is_test $4=is_config

file_path="$1" rel_path="$2" is_test="$3" is_config="$4"

# Scope: which files this check applies to
if [[ "$is_test" == "true" ]]; then exit 0; fi
case "${file_path}" in
    *.tsx) ;;
    *) exit 0 ;;
esac

# Logic: the actual check
violations=$(grep -n 'bad_pattern' "${file_path}" 2>/dev/null || true)

# Output: human-readable feedback + exit code
if [ -n "${violations}" ]; then
    echo "Check name: ${rel_path}"
    echo ""
    echo "${violations}"
    echo ""
    echo "How to fix this."
    exit 2
fi
exit 0
```

## Architecture

### Why this design works

| Concern | 9 separate hooks | 1 dispatcher + 9 checks |
|---------|-----------------|------------------------|
| Process spawns per write | 9 | 1 (+ sub-checks via function call) |
| JSON parsing | 9 times (same data) | 1 time |
| File path resolution | 9 times (same path) | 1 time |
| File classification | 9 times (same file) | 1 time |
| Non-code file rejection | 9 checks, 9 exits | 1 check, 1 exit (saves 8 processes) |
| Settings entries | 9 entries | 1 entry |
| Adding a new check | Edit settings.json + new file | Drop a `.sh` in `checks/` |
| Conflict resolution | Undefined (race) | Explicit (dispatcher merges output) |
| Debugging | Check 9 scripts | Check 1 dispatcher + relevant check |

### The key insight: shared pre-computation

The dispatcher does expensive shared work **once**:

1. **Parse JSON** — `jq -r '.tool_input.file_path // empty'`
2. **Validate file exists** — bail early if not
3. **Resolve absolute path** — handle relative paths
4. **Filter by extension** — `.ts`, `.tsx`, `.js`, `.jsx` only
5. **Classify** — is it a test file? a config file?
6. **Compute relative path** — for display in output

Each check receives all of this as **pre-computed arguments** (`$1` through `$4`). No check needs to parse JSON or classify files — that's the dispatcher's job.

### Output merging

The dispatcher collects all check output and joins it with `---` separators. If any check exits 2, the dispatcher exits 2. This gives Claude one coherent feedback message instead of 9 separate ones.

## When to Use a Dispatcher

**Use a dispatcher when:**
- You have 3+ hooks on the same event
- Hooks share expensive setup work (JSON parsing, path resolution, file I/O)
- Hooks check the same file from different angles (lint, security, conventions)
- You want "drop a file to add a check" extensibility
- You need deterministic, merged output

**Keep separate hooks when:**
- Hooks are on different events (can't conflict)
- You have only 1-2 hooks per event
- Hooks do fundamentally different things (one blocks, one injects context)
- The hook is user-level and checks are project-level

## Dispatcher Variants

### 1. Shell Dispatcher with Plugin Checks (recommended)

The reference implementation above. Best when:
- Checks are simple pattern matching (grep, awk)
- All checks need the same pre-computed context
- You want zero-config extensibility (drop a file)

### 2. Python Function Dispatcher

All handlers are functions in one file. Best when:
- Logic is complex (AST parsing, API calls)
- You need shared data structures between handlers
- 2-5 handlers that are tightly related

```python
#!/usr/bin/env python3
import json, sys

def handle_lint(tool_name, tool_input, **ctx):
    file_path = tool_input.get("file_path", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None
    # ... check logic ...
    return {"message": "lint passed"} or None

def handle_security(tool_name, tool_input, **ctx):
    # ... check logic ...
    return None

HANDLERS = [handle_lint, handle_security]

def main():
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    ctx = {"tool_result": data.get("tool_result", {})}

    messages, should_block = [], False
    for handler in HANDLERS:
        try:
            result = handler(tool_name, tool_input, **ctx)
            if result and result.get("block"): should_block = True
            if result and result.get("message"): messages.append(result["message"])
        except Exception:
            pass

    if should_block:
        print("\n".join(messages), file=sys.stderr)
        sys.exit(2)
    if messages:
        print("\n".join(messages))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### 3. Python Plugin Dispatcher

Handlers are separate `.py` files loaded dynamically. Best when:
- You have 5+ handlers and they come from different sources
- Handlers are complex enough to warrant separate files
- You want the Python function interface with plugin extensibility

```python
#!/usr/bin/env python3
import importlib.util, json, sys
from pathlib import Path

HANDLERS_DIR = Path(__file__).parent / "checks"

def load_handlers():
    handlers = []
    for path in sorted(HANDLERS_DIR.glob("*.py")):
        if path.name.startswith("_"): continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "handle"):
            handlers.append((path.stem, mod.handle))
    return handlers
```

## Adding a Dispatcher to Your Project

### Step 1: Identify the event with the most hooks

Look at your settings.json. Which event has 3+ hooks? That's your consolidation target.

### Step 2: Design the shared interface

What do all your checks need? For `PostToolUse` file checks, it's:
- `file_path` (absolute)
- `rel_path` (for display)
- `is_test` (skip test files)
- `is_config` (skip config files)

For `PreToolUse` command validation, it might be:
- `tool_name`
- `command` (for Bash hooks)
- `file_path` (for Write/Edit hooks)

### Step 3: Write the dispatcher

Put the shared work (parse, validate, classify) in the dispatcher. Define the contract for checks (what args they get, what exit codes mean).

### Step 4: Migrate each hook into a check

For each existing hook, strip out the JSON parsing and file resolution (dispatcher handles that now). Keep just the check logic. Save it in `checks/`.

### Step 5: Update settings.json

Replace N hook entries with one dispatcher entry.

### Step 6: Test

```bash
# Test with a code file
echo '{"tool_name":"Write","tool_input":{"file_path":"src/components/Button.tsx"}}' \
  | .claude/hooks/post-tool-dispatcher.sh

# Test with a non-code file (should exit 0 immediately)
echo '{"tool_name":"Write","tool_input":{"file_path":"README.md"}}' \
  | .claude/hooks/post-tool-dispatcher.sh

# Test with a test file (checks should skip)
echo '{"tool_name":"Write","tool_input":{"file_path":"src/__tests__/Button.test.tsx"}}' \
  | .claude/hooks/post-tool-dispatcher.sh
```

## Performance Notes

- The shell dispatcher itself adds ~3-5ms overhead for JSON parsing + classification
- Each sub-check that applies adds ~5-10ms (bash process + grep/awk)
- Checks that don't apply exit in <1ms (the early `case` exits are instant)
- Non-code files are rejected by the dispatcher before any check runs — zero wasted work
- Total for a `.tsx` file with all 9 checks: ~18-25ms vs ~90-120ms for 9 separate hooks

## Relationship to Other Patterns

- **Debug Wrapper** (`debug-wrap.sh`): Wrap the dispatcher itself, not individual checks
- **Skill Router**: Another dispatcher, for `UserPromptSubmit` — evaluates all installed skills in one process
- **Context Injection**: Can be a handler inside a `SessionStart` dispatcher that also sets env vars, checks tools, etc.
