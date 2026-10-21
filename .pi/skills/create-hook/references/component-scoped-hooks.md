# Component-Scoped Hooks

Hooks can be defined in the frontmatter of Skills, subagents, and slash commands instead of global settings. This scopes hooks to specific components and enables encapsulated, reusable hook definitions.

## Where Component Hooks Can Be Defined

| Component | File | Supported |
|-----------|------|-----------|
| Skills | `SKILL.md` frontmatter | Yes |
| Slash commands | Command `.md` frontmatter | Yes |
| Subagents | Subagent definition | Yes |

## Frontmatter Syntax

```yaml
---
name: my-skill
description: A skill with scoped hooks
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-bash.sh"
        - once: true
  SessionStart:
    - hooks:
        - type: command
          command: "./scripts/setup-env.sh"
        - once: true
---
```

## The `once` Option

The `once: true` option ensures a hook runs only once per session, even if the component is invoked multiple times.

```yaml
hooks:
  SessionStart:
    - hooks:
        - type: command
          command: "./setup.sh"
        - once: true  # Won't re-run on resume/compact/clear
```

**Use cases:**
- Environment setup that shouldn't repeat
- One-time context injection
- Initialization scripts
- Resource allocation

**Without `once`:** Hook runs every time the event fires and component is active.

## CLAUDE_PLUGIN_ROOT Environment Variable

Component hooks have access to `CLAUDE_PLUGIN_ROOT`, which contains the absolute path to the plugin/skill directory.

```bash
#!/bin/bash
# In a skill's hook script

# Access files relative to the skill
CONFIG_FILE="$CLAUDE_PLUGIN_ROOT/config/settings.json"
HELPER_SCRIPT="$CLAUDE_PLUGIN_ROOT/scripts/helper.py"

python3 "$HELPER_SCRIPT" --config "$CONFIG_FILE"
```

| Variable | Scope | Value |
|----------|-------|-------|
| `CLAUDE_PLUGIN_ROOT` | Component hooks only | Absolute path to skill/plugin directory |
| `CLAUDE_PROJECT_DIR` | All hooks | Absolute path to project root |

## Component vs Global Hooks

### When to Use Component-Scoped Hooks

| Scenario | Recommendation |
|----------|----------------|
| Hook only relevant to one skill | Component-scoped |
| Hook uses skill-specific scripts | Component-scoped |
| Hook should be portable with skill | Component-scoped |
| Hook applies to all tool usage | Global (settings.json) |
| Hook enforces project-wide policy | Global |
| Hook needs to run regardless of skill | Global |

### Execution Order

1. Global hooks from settings run first
2. Component hooks run when component is active
3. All matching hooks run in parallel

## Examples

### Skill with Bash Validation

```yaml
---
name: secure-deployment
description: Deployment skill with command validation
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python3 \"$CLAUDE_PLUGIN_ROOT\"/scripts/validate-deploy-commands.sh"
---

# Secure Deployment Skill

This skill validates all bash commands against deployment safety rules.
```

### Command with One-Time Setup

```yaml
---
name: database-migrate
description: Run database migrations
hooks:
  SessionStart:
    - matcher: "startup"
      hooks:
        - type: command
          command: "bash \"$CLAUDE_PLUGIN_ROOT\"/scripts/check-db-connection.sh"
        - once: true
---

# Database Migration Command

Runs database migrations with connection verification.
```

### Skill with Prompt-Based Stop Hook

```yaml
---
name: code-review
description: Code review workflow
hooks:
  Stop:
    - hooks:
        - type: prompt
          prompt: "Check if the code review is complete. Were all files reviewed? Were issues documented?\n$ARGUMENTS"
          timeout: 30
---

# Code Review Skill

Ensures thorough code review before completion.
```

### Skill with Multiple Hook Types

```yaml
---
name: test-runner
description: Test execution with validation
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python3 \"$CLAUDE_PLUGIN_ROOT\"/scripts/validate-test-command.py"
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python3 \"$CLAUDE_PLUGIN_ROOT\"/scripts/check-test-results.py"
  SessionStart:
    - hooks:
        - type: command
          command: "bash \"$CLAUDE_PLUGIN_ROOT\"/scripts/setup-test-env.sh"
        - once: true
---
```

## Script Organization

Recommended structure for skills with hooks:

```
.claude/skills/my-skill/
├── SKILL.md           # Skill definition with hooks in frontmatter
├── scripts/
│   ├── validate.py    # Hook scripts
│   ├── setup.sh
│   └── cleanup.sh
├── config/
│   └── rules.json     # Hook configuration
└── references/
    └── docs.md        # Skill documentation
```

Access scripts using `CLAUDE_PLUGIN_ROOT`:

```yaml
hooks:
  PreToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "python3 \"$CLAUDE_PLUGIN_ROOT\"/scripts/validate.py"
```

## Debugging Component Hooks

1. **Check registration**: Run `/hooks` to see which hooks are active
2. **Verify paths**: Ensure `CLAUDE_PLUGIN_ROOT` resolves correctly
3. **Test scripts**: Run hook scripts manually with test input
4. **Check `once` state**: Restart session to reset `once` hooks

## Limitations

- Component hooks only active when component is in use
- Cannot override global hooks (both run)
- `once` resets on session restart (not just resume)
- `CLAUDE_PLUGIN_ROOT` not available in global hooks
