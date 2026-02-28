# Create Dispatcher Workflow

Consolidate multiple hooks on the same event into a single dispatcher hook with a `checks/` directory.

## When to Use

The user has (or is about to have) 3+ hooks on the same event, hooks are doing redundant work (all parsing the same JSON, resolving the same file path), or they're experiencing conflicts between hooks.

## Input Required

- **Event type**: Which event to consolidate (e.g., PostToolUse, PreToolUse, UserPromptSubmit)
- **Existing hooks**: The hooks currently registered on that event (or checks to enforce)
- **Shared context**: What pre-computed data all checks need (file path, tool name, classifications)

## Step 1: Audit Current Hooks

Read the settings file and identify all hooks on the target event:

```bash
python3 -c "
import json, sys
settings = json.load(open('.claude/settings.json'))
event = sys.argv[1]
matchers = settings.get('hooks', {}).get(event, [])
for m in matchers:
    matcher = m.get('matcher', '*')
    for h in m.get('hooks', []):
        print(f'  matcher={matcher}  command={h.get(\"command\", \"\")}')
" "EVENT_NAME"
```

For each hook script, read it and extract:
- What it checks
- What shared work it does (JSON parsing, path resolution, etc.)
- What exit codes it returns

## Step 2: Design the Shared Interface

Identify what every check needs from the dispatcher. This is what the dispatcher pre-computes once:

**For PostToolUse file checks** (the most common pattern):
```
$1 = file_path    (absolute)
$2 = rel_path     (relative, for display)
$3 = is_test      ("true" or "false")
$4 = is_config    ("true" or "false")
```

**For PreToolUse command validation:**
```
$1 = tool_name
$2 = command       (for Bash hooks)
$3 = file_path     (for Write/Edit hooks)
```

**For UserPromptSubmit routing:**
```
stdin = full JSON (for complex routing)
$1 = prompt text
```

## Step 3: Create the Directory Structure

```bash
mkdir -p .claude/hooks/checks
```

The structure will be:
```
.claude/hooks/
  {event}-dispatcher.sh     # the dispatcher (registered in settings)
  checks/                   # handler scripts (auto-discovered)
    check-name.sh           # individual checks
```

## Step 4: Write the Dispatcher

Use the shell dispatcher template. The pattern is:

1. Read JSON from stdin (once)
2. Extract and validate shared fields
3. Bail early for non-applicable inputs (wrong file type, missing data)
4. Classify the input (test file? config file? which language?)
5. Loop over `checks/*.sh`, passing pre-computed args
6. Collect output, merge results, return single exit code

**PostToolUse dispatcher for file checks:**

```bash
#!/bin/bash
set -euo pipefail

CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checks"

# --- Parse once ---
JSON_INPUT=$(cat)
file_path=$(echo "${JSON_INPUT}" | jq -r '.tool_input.file_path // empty')

[ -z "${file_path}" ] || [ ! -f "${file_path}" ] && exit 0

# Resolve absolute path
[[ "${file_path}" != /* ]] && file_path="${CLAUDE_PROJECT_DIR}/${file_path}"

# Filter: only code files
case "${file_path}" in
    *.ts|*.tsx|*.js|*.jsx|*.py|*.rb) ;;
    *) exit 0 ;;
esac

# Classify once
is_test="false"
case "${file_path}" in
    *test*|*spec*|*mock*|*__tests__*) is_test="true" ;;
esac

is_config="false"
case "${file_path}" in
    *.config.*) is_config="true" ;;
esac

rel_path="${file_path#${CLAUDE_PROJECT_DIR}/}"

# --- Run checks ---
output="" had_warning=false

for check in "${CHECKS_DIR}"/*.sh; do
    [ -x "${check}" ] || continue
    result="" exit_code=0
    result=$("${check}" "${file_path}" "${rel_path}" "${is_test}" "${is_config}" 2>&1) || exit_code=$?
    if [ -n "${result}" ]; then
        [ -n "${output}" ] && output="${output}
---
"
        output="${output}${result}"
        [ "${exit_code}" = "2" ] && had_warning=true
    fi
done

if [ -n "${output}" ]; then
    echo "${output}"
    ${had_warning} && exit 2
fi
exit 0
```

**PreToolUse dispatcher for command validation:**

```bash
#!/bin/bash
set -euo pipefail

CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checks"

JSON_INPUT=$(cat)
tool_name=$(echo "${JSON_INPUT}" | jq -r '.tool_name // empty')
tool_input=$(echo "${JSON_INPUT}" | jq -r '.tool_input // {}')

# Extract based on tool type
command_str=$(echo "${tool_input}" | jq -r '.command // empty')
file_path=$(echo "${tool_input}" | jq -r '.file_path // empty')

output="" should_block=false

for check in "${CHECKS_DIR}"/*.sh; do
    [ -x "${check}" ] || continue
    result="" exit_code=0
    result=$("${check}" "${tool_name}" "${command_str}" "${file_path}" 2>&1) || exit_code=$?
    if [ -n "${result}" ]; then
        [ -n "${output}" ] && output="${output}
---
"
        output="${output}${result}"
        [ "${exit_code}" = "2" ] && should_block=true
    fi
done

if [ -n "${output}" ]; then
    if ${should_block}; then
        echo "${output}" >&2
        exit 2
    fi
    echo "${output}"
fi
exit 0
```

Make executable:
```bash
chmod +x .claude/hooks/{event}-dispatcher.sh
```

## Step 5: Write the Check Scripts

For each existing hook or new check, create a script in `checks/`:

```bash
#!/bin/bash
# Check: {what it enforces}
# Args: $1=file_path $2=rel_path $3=is_test $4=is_config

file_path="$1" rel_path="$2" is_test="$3" is_config="$4"

# Scope: skip files this check doesn't apply to
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

Make each check executable:
```bash
chmod +x .claude/hooks/checks/*.sh
```

## Step 6: Update Settings

Replace N hook entries with one dispatcher entry:

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

## Step 7: Test

Test the full dispatcher with synthetic input:

```bash
# Code file (should run all checks)
echo '{"tool_name":"Write","tool_input":{"file_path":"src/components/MyComponent.tsx"}}' \
  | .claude/hooks/post-tool-dispatcher.sh
echo "Exit: $?"

# Non-code file (should bail immediately)
echo '{"tool_name":"Write","tool_input":{"file_path":"README.md"}}' \
  | .claude/hooks/post-tool-dispatcher.sh
echo "Exit: $?"

# Test file (checks that skip tests should skip)
echo '{"tool_name":"Write","tool_input":{"file_path":"src/__tests__/Button.test.tsx"}}' \
  | .claude/hooks/post-tool-dispatcher.sh
echo "Exit: $?"
```

Test an individual check:
```bash
.claude/hooks/checks/my-check.sh "/full/path/to/file.tsx" "src/file.tsx" "false" "false"
echo "Exit: $?"
```

## Step 8: Clean Up

Once the dispatcher is working:

1. Delete the original individual hook scripts (if they were standalone)
2. Remove old entries from settings.json
3. Run `validate-hook.py --project` to confirm clean state

## Adding New Checks Later

Drop a new `.sh` file in `checks/` and make it executable. No settings changes needed. The dispatcher discovers it automatically on next run.

```bash
# Add a new check
cat > .claude/hooks/checks/my-new-check.sh << 'EOF'
#!/bin/bash
# Check: {description}
# Args: $1=file_path $2=rel_path $3=is_test $4=is_config
file_path="$1" rel_path="$2" is_test="$3"
if [[ "$is_test" == "true" ]]; then exit 0; fi
# ... your check logic ...
exit 0
EOF
chmod +x .claude/hooks/checks/my-new-check.sh
```

That's it. Next time Claude writes a file, your check runs.
