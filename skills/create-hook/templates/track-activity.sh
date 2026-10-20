#!/usr/bin/env bash
# Template: record what happened this session so a Stop gate can decide in microseconds
# Event: PostToolUse   Matcher: Write|Edit|Bash   Config: "async": true
#
# Pairs with stop-gate.sh. Async: it never blocks a tool call, and it only writes state.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

state="${TMPDIR:-/tmp}/agent-hook-state-${HOOK_SESSION:-unknown}"

case "$HOOK_TOOL" in
    Write|Edit|apply_patch)
        echo edited > "$state" ;;
    Bash)
        # Customize: the commands that count as verification ("npm test" also matches pnpm, "go test" also cargo).
        case "$HOOK_CMD" in
            *"npm test"*|*pytest*|*"go test"*|*"bun test"*)
                echo verified > "$state" ;;
        esac ;;
esac

hook_pass
