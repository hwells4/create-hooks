#!/usr/bin/env bash
# Template: keep the agent working when it edited code but never ran the tests
# Event: Stop (or SubagentStop)
#
# Reads the state track-activity.sh wrote, so the gate itself costs one file read.
# A Stop hook that runs the linter or test suite makes every turn wait for it;
# send the agent back to run them instead.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

# Already continuing because of a stop hook: let it end rather than loop.
[ "$HOOK_STOP_ACTIVE" = true ] && hook_pass

state="${TMPDIR:-/tmp}/agent-hook-state-${HOOK_SESSION:-unknown}"
[ "$(cat "$state" 2>/dev/null)" = edited ] || hook_pass

hook_continue "Code changed since the last test run. Run the project's tests, fix any failures, then finish."
