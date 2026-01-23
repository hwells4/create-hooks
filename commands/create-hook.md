---
description: Quickly scaffold Claude Code hooks with templates, validation, and conflict analysis
---

# /create-hook

Create and manage Claude Code hooks with proper templates, validation, and conflict analysis.

## Usage

```
/create-hook                        # Interactive mode
/create-hook new PreToolUse         # Create a new hook for an event
/create-hook new PreToolUse validate-bash  # Create with specific name
/create-hook debug my-hook.py       # Debug an existing hook
/create-hook analyze                # Analyze existing hooks for conflicts
/create-hook validate               # Validate all hook configurations
/create-hook validate my-hook.py    # Validate specific hook
/create-hook template auto-approve  # Show a template
```

## Examples

```bash
# Create a hook that validates bash commands
/create-hook new PreToolUse bash-validator

# Create a hook for auto-approving safe operations
/create-hook new PermissionRequest auto-approve

# Analyze what hooks are already installed
/create-hook analyze

# Debug a hook that isn't working
/create-hook debug hooks/my-validator.py
```

## Hook Events

| Event | When | Can Block? |
|-------|------|------------|
| PreToolUse | Before tool runs | Yes |
| PostToolUse | After tool succeeds | Feedback only |
| PermissionRequest | Permission dialog | Yes |
| UserPromptSubmit | User sends prompt | Yes |
| Stop | Claude finishes | Yes (continue) |
| SessionStart | Session begins | Context + env vars |
| SessionEnd | Session ends | Cleanup only |

---

**Invoke the create-hook skill for:** $ARGUMENTS
