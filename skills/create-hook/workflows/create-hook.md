# Create Hook Workflow

Generate a new Claude Code hook with proper structure. Automatically detects when a dispatcher should be used instead of a standalone hook.

## Input Required

- **Event type**: PreToolUse, PostToolUse, Stop, SessionStart, etc.
- **Hook name**: Descriptive name (e.g., `validate-bash`, `auto-approve-reads`)
- **Purpose**: What the hook should do

## Step 1: Run Inventory and Dispatcher Check

After the inventory agent returns, make the dispatcher decision:

### Path A: Dispatcher already exists for this event

Check if `.claude/hooks/checks/` directory exists and a `*-dispatcher.sh` or `*-dispatcher.py` is registered for the target event.

**If yes → Add a check script to the existing dispatcher.** Skip to Step 2A.

This is the fastest path: write one file, make it executable, done. No settings changes.

### Path B: 2+ hooks already exist on this event

**Recommend consolidating into a dispatcher first:**

> "You have {N} hooks on {event}. I recommend consolidating them into a single dispatcher before adding another hook. This prevents conflicts and makes future checks trivial to add. Want me to set that up?"

If the user agrees → follow `workflows/create-dispatcher.md`, then add the new check to the new dispatcher.

If the user declines → proceed with standalone hook (Step 2B).

### Path C: 0-1 hooks exist

**Create a standalone hook.** Proceed to Step 2B.

---

## Step 2A: Add Check to Existing Dispatcher

Write a check script following the dispatcher's interface convention:

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

# Output: human-readable feedback
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

Save to `.claude/hooks/checks/{check_name}.sh` and make executable:
```bash
chmod +x .claude/hooks/checks/{check_name}.sh
```

**No settings changes needed.** The dispatcher auto-discovers new checks.

Test the check directly:
```bash
.claude/hooks/checks/{check_name}.sh "/path/to/file.tsx" "src/file.tsx" "false" "false"
echo "Exit: $?"
```

Skip to Step 4 (Validate).

---

## Step 2B: Create Standalone Hook

### Set Up Debug Wrapper (Default)

**Always do this unless user explicitly opts out.**

Copy `templates/debug-wrap.sh` to the project's hooks directory:

```bash
mkdir -p .claude/hooks
cp templates/debug-wrap.sh .claude/hooks/debug-wrap.sh
chmod +x .claude/hooks/debug-wrap.sh
```

### Write the Hook

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

## Step 3: Add to Settings (Standalone Hooks Only)

**Skip this step if adding a check to an existing dispatcher (Path A).**

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

## Step 4: Test and Validate

1. Test manually:
   - **Dispatcher check**: `.claude/hooks/checks/{check_name}.sh <args>`
   - **Standalone hook**: `echo '{"tool_name":"Test"}' | .claude/hooks/{hook_name}`
2. Restart Claude Code (hooks snapshot at startup)
3. Trigger the event
4. Check debug log: `tail -f .claude/hooks/.debug.log`
5. Run `scripts/validate-hook.py --project` to confirm installation

## Exit Codes

- `exit 0` - Success
- `exit 1` - Error (logged, doesn't block)
- `exit 2` - Block action (stderr shown to Claude)
