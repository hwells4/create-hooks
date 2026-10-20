#!/usr/bin/env bash
# Template: approve read-only shell commands so the human is not prompted for them
# Event: PermissionRequest   Matcher: Bash
#
# Fires only when a permission prompt is about to appear. Approves single, plain
# commands from the allowlist; anything chained, redirected, or substituted falls
# through to the normal prompt. Claude's permission allow rules do the same job
# without a process: prefer them when the runtime is Claude-only.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

[ -n "$HOOK_CMD" ] || hook_pass

# Anything that can chain, redirect, or substitute goes to the human.
# shellcheck disable=SC2016  # literal '$(' pattern
case "$HOOK_CMD" in
    *';'*|*'&'*|*'|'*|*'>'*|*'<'*|*'`'*|*'$('*|*$'\n'*) hook_pass ;;
esac

SAFE='^(ls|pwd|cat|head|tail|wc|rg|grep|find|tree|git (status|diff|log|show|branch))( |$)'
[[ $HOOK_CMD =~ $SAFE ]] && hook_approve

hook_pass
