# Validate Hooks Workflow

Validate that Claude Code hooks are correctly configured and ready for use.

## The Validator

The validator script is located at `scripts/validate-hook.py` in the plugin directory.

## What It Checks

### For Hook Scripts
1. **File exists and is executable** - chmod +x applied
2. **Valid shebang** - #!/usr/bin/env python3 or #!/bin/bash
3. **No syntax errors** - Python AST parsing or bash -n
4. **Handles JSON input** - Reads from stdin correctly
5. **Valid exit codes** - Uses 0, 1, or 2 appropriately
6. **Event-specific checks** - e.g., Stop hooks must check stop_hook_active
7. **Runtime test** - Runs with sample input to verify it doesn't crash

### For Settings Configuration
1. **Valid JSON** - settings.json is parseable
2. **Known event types** - No typos in event names
3. **Matcher usage** - Only uses matchers on events that support them
4. **Script references** - Verifies referenced scripts exist
5. **Command syntax** - Checks $CLAUDE_PROJECT_DIR usage

## Usage

### From Command Line

```bash
# Get the plugin directory
PLUGIN_DIR=$(claude plugin list --json | jq -r '.[] | select(.name=="create-hooks") | .path')

# Validate entire project
python3 "$PLUGIN_DIR/skills/create-hook/scripts/validate-hook.py" --project

# Validate specific hook
python3 "$PLUGIN_DIR/skills/create-hook/scripts/validate-hook.py" .claude/hooks/my-hook.py

# Validate only settings
python3 "$PLUGIN_DIR/skills/create-hook/scripts/validate-hook.py" --settings

# Validate all hooks in .claude/hooks/
python3 "$PLUGIN_DIR/skills/create-hook/scripts/validate-hook.py" --all
```

### From Claude Code

When user invokes `/create-hook validate`:

1. Locate the validator script in the plugin directory
2. Run it with `--project` flag for full validation
3. Report results to user
4. If errors found, offer to fix them

## Example Output

```
############################################################
  HOOK VALIDATION: /path/to/project
############################################################

============================================================
  Settings: settings.json
============================================================
  ✓ Settings file valid JSON: settings.json
  ✓ Found 2 event types configured
  ✓ PreToolUse: Script exists: validate-bash.py
  ✓ Stop: Script exists: ensure-tests.py

  ✅ PASSED (4 checks, 0 warnings)

============================================================
  Hook: validate-bash.py
============================================================
  ✓ Script exists: validate-bash.py
  ✓ Script is executable
  ✓ Valid Python shebang
  ✓ Python syntax valid
  ✓ Handles JSON input from stdin
  ✓ Detected event type: PreToolUse
  ✓ Uses exit(2) for blocking
  ✓ Uses exit(0) for success
  ✓ Runtime test passed (exit code: 0)

  ✅ PASSED (9 checks, 0 warnings)

============================================================
  ✅ ALL VALIDATIONS PASSED
============================================================
```

## Common Issues and Fixes

### Script not executable
```bash
chmod +x .claude/hooks/my-hook.py
```

### Missing shebang
Add to first line:
```python
#!/usr/bin/env python3
```

### Stop hook infinite loop risk
Always check `stop_hook_active`:
```python
if input_data.get("stop_hook_active", False):
    sys.exit(0)  # Already continued once, let it stop
```

### Script not found in settings
Check the path uses `$CLAUDE_PROJECT_DIR`:
```json
"command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/my-hook.py"
```

### Invalid JSON input handling
Always wrap in try/except:
```python
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)  # Gracefully handle bad input
```
