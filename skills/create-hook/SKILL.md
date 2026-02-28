---
name: create-hook
description: Quickly scaffold Claude Code hooks with templates, validation, and conflict analysis. Analyzes existing hooks to prevent conflicts and takes care of boilerplate so you can focus on logic.
---

<objective>
Hook Manager helps you build Claude Code hooks properly. It handles the tedious parts—boilerplate, JSON schemas, settings configuration—so you can focus on what your hook actually does. Before creating anything, it checks what hooks you already have running to make sure nothing steps on each other.

**Core principle: prefer dispatchers over standalone hooks.** When multiple hooks exist on the same event, they should be consolidated into a single dispatcher with a `checks/` directory. This eliminates redundant JSON parsing, prevents conflicts, and makes adding new checks trivial (drop a file). The create-hook flow automatically detects when a dispatcher should be used and routes accordingly.
</objective>

<intake>
**If user provides arguments, route directly:**
- `/create-hook new PreToolUse validate-bash` → Create workflow
- `/create-hook debug my-hook.py` → Debug workflow
- `/create-hook template auto-approve` → Show template
- `/create-hook analyze` → Run inventory agent
- `/create-hook dispatcher PostToolUse` → Create dispatcher workflow
- `/create-hook validate` → Run hook validator
- `/create-hook validate my-hook.py` → Validate specific hook

**If bare `/create-hook` with no arguments, ask:**

What do you need?

1. **Create a new hook** - I'll check your existing hooks first. If you already have a dispatcher or multiple hooks on the same event, I'll add a check to the dispatcher instead of creating a standalone hook.
2. **Edit an existing hook** - Modify a hook or dispatcher check in .claude/hooks/
3. **Consolidate hooks** - Migrate multiple standalone hooks into a single dispatcher
4. **Debug a hook** - Something's not working? Let's figure out why
5. **View hook logs** - See which hooks are firing (`scripts/hook-log.py`)
6. **Validate hooks** - Check that hooks are correctly configured and ready for use
7. **Analyze hooks** - See what hooks you have running and find gaps
8. **Something else** - Templates, settings, MCP tools, security, env vars

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
| Create new hook | hook-events.md, json-output.md, security.md, sub-agents.md, dispatcher-pattern.md | Spawn inventory agent → **dispatcher decision** → create (check or standalone) → tester agent |
| Create prompt-based hook | prompt-based-hooks.md, hook-events.md | Determine event → configure prompt → test |
| Create component-scoped hook | component-scoped-hooks.md, hook-events.md | Define in frontmatter → test |
| Edit existing hook | hook-events.md, json-output.md, debugging.md | Read existing hook → modify → test |
| Debug hook | debugging.md, hook-events.md | Diagnose → fix → test |
| **Validate hooks** | debugging.md | Run `scripts/validate-hook.py --project` |
| **View hook logs** | debugging.md | Run `scripts/hook-log.py` or `tail -f .claude/hooks/.debug.log` |
| Analyze hooks | sub-agents.md | Spawn inventory agent |
| **Consolidate hooks (dispatcher)** | dispatcher-pattern.md, hook-events.md | workflows/create-dispatcher.md |
| MCP tools | mcp-tools.md, hook-events.md | Show patterns |
| SessionStart/env vars | session-env-vars.md, hook-events.md | Show patterns |
| Security review | security.md | Show checklist |
| Templates | (load template file directly) | Show template |
| Add to settings | workflows/add-to-settings.md | Configure |
</routing>

<essential_principles>
1. **Analyze first** - Before creating, understand existing hooks to prevent conflicts
2. **Dispatcher by default** - After inventory, check if a dispatcher exists or should be created:
   - **Dispatcher exists for this event** → Add a check script to `checks/`, not a standalone hook
   - **2+ hooks already exist on this event** → Recommend consolidating into a dispatcher first
   - **0-1 hooks exist** → Create standalone hook (but keep it dispatcher-ready)
   See `references/dispatcher-pattern.md` for the full pattern.
3. **Ask installation level** - ALWAYS ask user: project, user, or local level
   - **Project** (`.claude/settings.json`) - This project only, version controlled
   - **User** (`~/.claude/settings.json`) - ALL projects for this user
   - **Local** (`.claude/settings.local.json`) - This project only, gitignored
4. **Debug wrapper by default** - Always include `debug-wrap.sh` and wrap commands with it (user can opt out)
5. **Input via stdin** - Hooks receive JSON with session_id, tool_name, tool_input, etc.
6. **Output via exit codes** - 0=success, 2=blocking error (stderr shown to Claude)
7. **Parallel execution** - All matching hooks run simultaneously (60s timeout default)
8. **Validate after creation** - Run `scripts/validate-hook.py` to confirm proper installation
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
| references/dispatcher-pattern.md | Dispatcher architecture — when and how to consolidate hooks |

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
| templates/debug-wrap.sh | **Debug wrapper** - logs hook invocations (~0.5ms overhead) |
| templates/bash-validator.sh | Block dangerous shell commands |
| templates/python-validator.py | Complex validation with JSON |
| templates/auto-approve.py | Auto-approve safe operations |
| templates/context-injection.py | SessionStart/UserPromptSubmit context |
| templates/stop-gate.py | Ensure work completion before stop (command-based) |
| templates/intelligent-stop-prompt.json | LLM-evaluated task completion (prompt-based) |
| templates/permission-handler.py | Handle permission dialogs programmatically |
| templates/notification-forwarder.sh | Forward notifications externally |
| templates/dispatcher.sh | **Shell dispatcher** (recommended) - routes to checks/ directory |
| templates/dispatcher.py | **Python dispatcher** - routes to handler functions in one file |
</templates_index>

<subagent_usage>
**When creating hooks, spawn agents in order:**

1. **hook_inventory_agent** - Scans existing hooks, identifies gaps
2. **Dispatcher decision** (orchestrator, not an agent):
   - If a `checks/` directory exists for this event → route to "add check" flow
   - If 2+ hooks exist on the target event → recommend dispatcher, load `workflows/create-dispatcher.md`
   - Otherwise → proceed with standalone hook creation
3. **interaction_analyzer_agent** - Identifies conflicts with proposed hook (or checks in dispatcher)
4. **hook_tester_agent** - Tests hook/check before deployment

See `references/sub-agents.md` for full prompt templates.
See `references/dispatcher-pattern.md` for dispatcher architecture.
</subagent_usage>

<success_criteria>
- [ ] Existing hooks analyzed (no surprise conflicts)
- [ ] **Dispatcher check**: if 2+ hooks exist on target event, dispatcher recommended or used
- [ ] **If dispatcher exists**: new check added to `checks/` directory (no settings change needed)
- [ ] **If standalone hook**: script created with proper shebang and permissions
- [ ] **Debug wrapper installed** (`debug-wrap.sh` copied to `.claude/hooks/`) - unless user explicitly opts out
- [ ] **Settings command uses debug wrapper** - unless user explicitly opts out (standalone hooks only)
- [ ] User asked about installation level (project/user/local)
- [ ] Settings.json updated at correct level per user choice (standalone hooks only — dispatchers need no settings change for new checks)
- [ ] Input parsing handles JSON from stdin (standalone) or positional args (dispatcher check)
- [ ] Output uses correct exit codes/JSON format
- [ ] Script tested with multiple inputs before deployment
- [ ] **Validator run** to confirm hook is properly installed (`scripts/validate-hook.py`)
- [ ] Security: inputs validated, paths sanitized, sensitive files protected
</success_criteria>
