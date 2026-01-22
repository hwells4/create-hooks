---
name: create-hook
description: Quickly scaffold Claude Code hooks with templates, validation, and conflict analysis. Analyzes existing hooks to prevent conflicts and takes care of boilerplate so you can focus on logic.
---

<objective>
Hook Manager helps you build Claude Code hooks properly. It handles the tedious parts—boilerplate, JSON schemas, settings configuration—so you can focus on what your hook actually does. Before creating anything, it checks what hooks you already have running to make sure nothing steps on each other.
</objective>

<intake>
**If user provides arguments, route directly:**
- `/create-hook new PreToolUse validate-bash` → Create workflow
- `/create-hook debug my-hook.py` → Debug workflow
- `/create-hook template auto-approve` → Show template
- `/create-hook analyze` → Run inventory agent
- `/create-hook validate` → Run hook validator
- `/create-hook validate my-hook.py` → Validate specific hook

**If bare `/create-hook` with no arguments, ask:**

What do you need?

1. **Create a new hook** - I'll check your existing hooks first, then build something that plays nice with them
2. **Edit an existing hook** - Modify a hook in .claude/hooks/
3. **Debug a hook** - Something's not working? Let's figure out why
4. **Validate hooks** - Check that hooks are correctly configured and ready for use
5. **Analyze hooks** - See what hooks you have running and find gaps
6. **Something else** - Templates, settings, MCP tools, security, env vars

**When creating a new hook, ALWAYS ask about installation level:**

Where should this hook be installed?

1. **Project level** (`.claude/settings.json`) - Runs only in THIS project, checked into git
2. **User level** (`~/.claude/settings.json`) - Runs in ALL your projects
3. **Local only** (`.claude/settings.local.json`) - Project-level but gitignored (for personal/sensitive hooks)
</intake>

<routing>
**Load references based on user intent:**

| Intent | References to Load | Workflow |
|--------|-------------------|----------|
| Create new hook | hook-events.md, json-output.md, security.md, sub-agents.md | Spawn inventory agent → analyzer agent → create → tester agent |
| Create prompt-based hook | prompt-based-hooks.md, hook-events.md | Determine event → configure prompt → test |
| Create component-scoped hook | component-scoped-hooks.md, hook-events.md | Define in frontmatter → test |
| Edit existing hook | hook-events.md, json-output.md, debugging.md | Read existing hook → modify → test |
| Debug hook | debugging.md, hook-events.md | Diagnose → fix → test |
| **Validate hooks** | debugging.md | Run `scripts/validate-hook.py --project` |
| Analyze hooks | sub-agents.md | Spawn inventory agent |
| MCP tools | mcp-tools.md, hook-events.md | Show patterns |
| SessionStart/env vars | session-env-vars.md, hook-events.md | Show patterns |
| Security review | security.md | Show checklist |
| Templates | (load template file directly) | Show template |
| Add to settings | workflows/add-to-settings.md | Configure |
</routing>

<essential_principles>
1. **Analyze first** - Before creating, understand existing hooks to prevent conflicts
2. **Ask installation level** - ALWAYS ask user: project, user, or local level
   - **Project** (`.claude/settings.json`) - This project only, version controlled
   - **User** (`~/.claude/settings.json`) - ALL projects for this user
   - **Local** (`.claude/settings.local.json`) - This project only, gitignored
3. **Input via stdin** - Hooks receive JSON with session_id, tool_name, tool_input, etc.
4. **Output via exit codes** - 0=success, 2=blocking error (stderr shown to Claude)
5. **Parallel execution** - All matching hooks run simultaneously (60s timeout default)
6. **Validate after creation** - Run `scripts/validate-hook.py` to confirm proper installation
</essential_principles>

<quick_reference>
**Hook Types:**
| Type | When to Use | Supported Events |
|------|-------------|------------------|
| `command` | Deterministic checks (regex, file ops, external APIs) | All events |
| `prompt` | Judgment calls (task completeness, quality evaluation) | Stop, SubagentStop, UserPromptSubmit, PreToolUse, PermissionRequest |

**Hook Events:**
| Event | When | Matcher? | Can Block? |
|-------|------|----------|------------|
| PreToolUse | Before tool runs | Yes | Yes |
| PostToolUse | After tool succeeds | Yes | Feedback only |
| PermissionRequest | Permission dialog | Yes | Yes |
| UserPromptSubmit | User sends prompt | No | Yes |
| Stop | Claude finishes | No | Yes (continue) |
| SubagentStop | Subagent finishes | No | Yes (continue) |
| SessionStart | Session begins | Yes | Context + env vars |
| SessionEnd | Session ends | No | Cleanup only |
| PreCompact | Before compaction | Yes | No |
| Notification | System notification | Yes | No |

**Common Matchers:**
- `Write|Edit|MultiEdit` - File modifications
- `Bash` - Shell commands
- `Task` - Subagent creation
- `mcp__<server>__<tool>` - MCP tools (e.g., `mcp__github__.*`)
- `*` or empty - All tools

**Exit Codes:**
- `exit 0` - Success (stdout in verbose mode, or context for SessionStart/UserPromptSubmit)
- `exit 2` - Block action (stderr shown to Claude)
- `exit 1` - Non-blocking error (logged only)
</quick_reference>

<references_index>
**Core (load for most tasks):**
| Reference | Purpose |
|-----------|---------|
| references/hook-events.md | Input/output schemas per event |
| references/json-output.md | JSON response format details |

**Task-specific:**
| Reference | When to Load |
|-----------|--------------|
| references/prompt-based-hooks.md | Creating LLM-evaluated hooks (type: prompt) |
| references/component-scoped-hooks.md | Defining hooks in SKILL.md/command frontmatter |
| references/security.md | Creating new hooks, security review |
| references/debugging.md | Debugging, testing, healing hooks |
| references/mcp-tools.md | Hooking MCP server tools |
| references/session-env-vars.md | SessionStart hooks with env vars |
| references/sub-agents.md | Creating hooks (analysis phase) |
</references_index>

<templates_index>
| Template | Use Case |
|----------|----------|
| templates/bash-validator.sh | Block dangerous shell commands |
| templates/python-validator.py | Complex validation with JSON |
| templates/auto-approve.py | Auto-approve safe operations |
| templates/context-injection.py | SessionStart/UserPromptSubmit context |
| templates/stop-gate.py | Ensure work completion before stop (command-based) |
| templates/intelligent-stop-prompt.json | LLM-evaluated task completion (prompt-based) |
| templates/permission-handler.py | Handle permission dialogs programmatically |
| templates/notification-forwarder.sh | Forward notifications externally |
</templates_index>

<subagent_usage>
**When creating hooks, spawn agents in order:**

1. **hook_inventory_agent** - Scans existing hooks, identifies gaps
2. **interaction_analyzer_agent** - Identifies conflicts with proposed hook
3. **hook_tester_agent** - Tests hook before deployment

See `references/sub-agents.md` for full prompt templates.
</subagent_usage>

<success_criteria>
- [ ] Existing hooks analyzed (no surprise conflicts)
- [ ] Hook script created with proper shebang and permissions
- [ ] User asked about installation level (project/user/local)
- [ ] Settings.json updated at correct level per user choice
- [ ] Input parsing handles JSON from stdin
- [ ] Output uses correct exit codes/JSON format
- [ ] Script tested with multiple inputs before deployment
- [ ] **Validator run** to confirm hook is properly installed (`scripts/validate-hook.py`)
- [ ] Security: inputs validated, paths sanitized, sensitive files protected
</success_criteria>
