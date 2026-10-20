#!/usr/bin/env bash
# Template: add live project state to the agent's context
# Event: SessionStart (matcher: startup|resume|clear|compact) or UserPromptSubmit
#
# Only for state that changes. Static conventions belong in CLAUDE.md / AGENTS.md,
# which load without running anything. Write facts, not commands: text phrased as
# system instructions can trip prompt-injection defenses.
# UserPromptSubmit runs on every prompt with a 30s default timeout; keep it cheap.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

dir=$(hook_project_dir)
branch=$(git -C "$dir" branch --show-current 2>/dev/null) || hook_pass
dirty=$(git -C "$dir" status --porcelain 2>/dev/null | head -20)

context="Current git branch: ${branch:-detached HEAD}."
[ -z "$dirty" ] || context="$context
Uncommitted changes:
$dirty"

hook_context "$context"
