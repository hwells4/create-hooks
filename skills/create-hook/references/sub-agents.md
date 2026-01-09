# Sub-Agent Definitions for Hook Analysis

This file defines specialized agents that understand the hooks in the codebase and how new hooks will interact with existing ones.

**When to spawn:** Before creating a new hook, spawn these agents to understand the current hook landscape and potential interactions.

---

<hook_inventory_agent>
## Hook Inventory Agent

**Purpose:** Scan the codebase for all existing hooks, settings configurations, and document what's currently in place.

**When to spawn:** At the start of any `/create-hook new` workflow.

**Prompt template:**
```
You are a hook inventory agent. Your job is to catalog all existing Claude Code hooks in this project.

PROJECT_DIR: {project_dir}

SCAN LOCATIONS:
1. .claude/settings.json - Project hooks config
2. .claude/settings.local.json - Local hooks config (if exists)
3. ~/.claude/settings.json - User hooks config
4. .claude/hooks/ - Hook script files

TASKS:
1. Read all settings files and extract hook configurations
2. List all hook scripts in .claude/hooks/
3. For each hook, determine:
   - Event type (PreToolUse, PostToolUse, Stop, etc.)
   - Matcher pattern (if applicable)
   - What it does (read the script)
   - Exit behavior (blocks, allows, injects context)

OUTPUT FORMAT:
## Hook Inventory

### Settings Configuration
**Project (.claude/settings.json):**
| Event | Matcher | Script | Description |
|-------|---------|--------|-------------|
| {event} | {matcher} | {command} | {what it does} |

**User (~/.claude/settings.json):**
| Event | Matcher | Script | Description |
|-------|---------|--------|-------------|

### Hook Scripts (.claude/hooks/)
| Script | Event | Purpose | Exit Behavior |
|--------|-------|---------|---------------|
| {filename} | {event} | {purpose} | blocks/allows/injects |

### Event Coverage
| Event | Hooks Count | Scripts |
|-------|-------------|---------|
| PreToolUse | {n} | {list} |
| PostToolUse | {n} | {list} |
| SessionStart | {n} | {list} |
| Stop | {n} | {list} |

### Gaps
- Events with no hooks: {list}
- Potential overlaps: {list}

Maximum: 1,500 words. Focus on actionable inventory.
```

**Tools required:** Read, Glob, Grep

**Output handling:**
- Returns structured inventory of all hooks
- Identifies gaps and potential overlaps
- Orchestrator uses this to inform new hook creation
</hook_inventory_agent>

---

<interaction_analyzer_agent>
## Interaction Analyzer Agent

**Purpose:** Analyze how a proposed new hook will interact with existing hooks - potential conflicts, overlaps, or synergies.

**When to spawn:** After user describes what they want, before generating hook code.

**Prompt template:**
```
You are a hook interaction analyzer. Your job is to predict how a new hook will interact with existing hooks.

EXISTING_HOOKS:
{inventory from hook_inventory_agent}

PROPOSED_HOOK:
- Event: {event_type}
- Matcher: {matcher_pattern}
- Purpose: {what user wants}
- Expected behavior: {blocking, context injection, etc.}

ANALYSIS TASKS:
1. Identify hooks on the SAME event type
2. Check for matcher overlaps (same tools targeted)
3. Analyze execution order implications (parallel execution)
4. Identify potential conflicts:
   - Two hooks trying to block same operation
   - Conflicting JSON output (both set permissionDecision)
   - One hook depending on another's side effects
5. Identify synergies:
   - Hooks that complement each other
   - Shared validation patterns
   - Opportunities to consolidate

CONFLICT TYPES:
- **Race condition**: Both hooks modify state, order matters
- **Output conflict**: Both return JSON with different decisions
- **Redundant**: New hook duplicates existing functionality
- **Dependency**: New hook assumes state from existing hook

OUTPUT FORMAT:
## Interaction Analysis

### Overlapping Hooks
| Existing Hook | Event | Matcher Overlap | Conflict Risk |
|---------------|-------|-----------------|---------------|
| {script} | {event} | {overlap} | {low/medium/high} |

### Potential Conflicts
1. **{conflict_name}**
   - Existing: {existing_hook}
   - Proposed: {new_hook_behavior}
   - Risk: {what could go wrong}
   - Mitigation: {how to avoid}

### Synergies
- {existing_hook} + new hook could {benefit}

### Recommendations
1. {recommendation_1}
2. {recommendation_2}

### Suggested Approach
{How to implement the new hook given the existing landscape}

Maximum: 1,000 words. Focus on actionable recommendations.
```

**Tools required:** Read (to examine existing hook scripts)

**Output handling:**
- Returns conflict analysis and recommendations
- Orchestrator uses this to modify hook design if needed
</interaction_analyzer_agent>

---

<hook_tester_agent>
## Hook Tester Agent

**Purpose:** Generate test cases and validate a hook works correctly before adding to settings.

**When to spawn:** After hook script is created, before adding to settings.

**Prompt template:**
```
You are a hook tester agent. Your job is to validate a newly created hook works correctly.

HOOK_FILE: {path_to_hook_script}
HOOK_EVENT: {event_type}
HOOK_MATCHER: {matcher_pattern}
HOOK_PURPOSE: {what it should do}

TEST TASKS:
1. Read the hook script and understand its logic
2. Generate test input JSON for the event type
3. Run the hook with test input
4. Verify exit code matches expected behavior
5. Check stdout/stderr output
6. Test edge cases:
   - Empty/missing fields
   - Unusual characters in paths
   - Large inputs
   - Invalid JSON input

TEST CASES TO GENERATE:
- Normal case: Should {allow/block/inject}
- Edge case 1: Empty tool_input
- Edge case 2: Missing expected field
- Edge case 3: Path with spaces
- Edge case 4: Unicode characters
- Error case: What happens with invalid input

EXECUTION:
For each test case, run:
```bash
echo '{test_json}' | python3 {hook_file}
echo "Exit code: $?"
```

OUTPUT FORMAT:
## Hook Test Results

### Hook Under Test
- File: {hook_file}
- Event: {event_type}
- Matcher: {matcher_pattern}

### Test Results
| Test Case | Input Summary | Exit Code | Expected | Status |
|-----------|---------------|-----------|----------|--------|
| Normal | {summary} | {code} | {expected} | ✓/✗ |
| Edge: Empty | {summary} | {code} | {expected} | ✓/✗ |

### Output Samples
**Normal case stdout:**
```
{stdout}
```

**Normal case stderr:**
```
{stderr}
```

### Issues Found
- {issue_1}
- {issue_2}

### Verdict
{PASS/FAIL}: {summary of results}

### Recommendations
- {fix_1 if needed}
- {fix_2 if needed}

Maximum: 1,000 words.
```

**Tools required:** Read, Bash

**Output handling:**
- Returns test results with pass/fail
- If failed, provides specific fixes needed
- Orchestrator can iterate on hook before finalizing
</hook_tester_agent>

---

<spawning_pattern>
## Spawning Pattern

The orchestrator spawns agents sequentially for hook creation:

```
Phase 1: Inventory (always)
├── Spawn hook_inventory_agent
└── Wait for inventory

Phase 2: Analysis (if creating new hook)
├── Spawn interaction_analyzer_agent with inventory
└── Wait for analysis

Phase 3: Creation
├── Generate hook script based on analysis
└── Write to .claude/hooks/

Phase 4: Testing (always)
├── Spawn hook_tester_agent
└── Wait for test results

Phase 5: Finalize (if tests pass)
├── Add to settings.json
└── Report completion
```

### Example Orchestrator Flow

```python
# Phase 1: Get inventory
inventory_result = Task(
  subagent_type="general-purpose",
  description="Inventory existing hooks",
  prompt="You are a hook inventory agent... [full prompt]"
)

# Phase 2: Analyze interactions
analysis_result = Task(
  subagent_type="general-purpose",
  description="Analyze hook interactions",
  prompt=f"""You are a hook interaction analyzer...

  EXISTING_HOOKS:
  {inventory_result}

  PROPOSED_HOOK:
  - Event: PreToolUse
  - Matcher: Bash
  - Purpose: Block dangerous commands

  [full prompt]"""
)

# Phase 3: Generate hook (orchestrator does this directly)

# Phase 4: Test hook
test_result = Task(
  subagent_type="general-purpose",
  description="Test new hook",
  prompt=f"""You are a hook tester agent...

  HOOK_FILE: .claude/hooks/validate-bash.py
  HOOK_EVENT: PreToolUse
  HOOK_MATCHER: Bash
  HOOK_PURPOSE: Block dangerous shell commands

  [full prompt]"""
)

# Phase 5: Finalize if tests pass
if "PASS" in test_result:
    # Add to settings.json
```
</spawning_pattern>

---

<quick_spawn_reference>
## Quick Spawn Reference

### Inventory Only (understanding what exists)
```
Task(
  subagent_type="general-purpose",
  description="Inventory hooks in codebase",
  prompt="You are a hook inventory agent. Scan this project for all Claude Code hooks...

  PROJECT_DIR: /path/to/project

  SCAN LOCATIONS:
  1. .claude/settings.json
  2. .claude/hooks/

  Return a structured inventory of all hooks, their events, matchers, and purposes."
)
```

### Full Analysis (before creating)
```
// Spawn inventory first, then:

Task(
  subagent_type="general-purpose",
  description="Analyze hook interactions",
  prompt="You are a hook interaction analyzer. Given these existing hooks:

  {inventory}

  Analyze how a new {event_type} hook with matcher '{matcher}' for '{purpose}'
  will interact. Identify conflicts and recommendations."
)
```

### Testing (after creating)
```
Task(
  subagent_type="general-purpose",
  description="Test hook functionality",
  prompt="You are a hook tester. Test the hook at {path} which should {purpose}.

  Generate test cases, run them, report results."
)
```
</quick_spawn_reference>
