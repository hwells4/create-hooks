#!/usr/bin/env bash
# debug-wrap.sh - log every run of a hook: time, runtime, event, exit code, duration.
#
# Opt-in while debugging; remove it once the hook behaves. Wrap the configured command:
#   Before: "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-bash.sh"
#   After:  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/debug-wrap.sh \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-bash.sh"
#
# Log: ${HOOK_DEBUG_LOG:-$HOME/.cache/agent-hooks/debug.log}
# View: python3 scripts/hook-log.py   (in this skill)

LOG="${HOOK_DEBUG_LOG:-$HOME/.cache/agent-hooks/debug.log}"
mkdir -p "$(dirname "$LOG")" 2>/dev/null

now_ms() {
    if [ -n "${EPOCHREALTIME:-}" ]; then
        local t=${EPOCHREALTIME/[.,]/}
        echo $(( t / 1000 ))
    else
        perl -MTime::HiRes=time -e 'printf "%d\n", time * 1000'
    fi
}

input=$(< /dev/stdin)
event=unknown
[[ $input =~ \"hook_event_name\"[[:space:]]*:[[:space:]]*\"([A-Za-z]+)\" ]] && event=${BASH_REMATCH[1]}
runtime=claude
[[ $input =~ \"turn_id\" ]] && runtime=codex

start=$(now_ms)
printf '%s' "$input" | "$@"
code=$?
elapsed=$(( $(now_ms) - start ))

printf '%s %s %s exit=%s %sms %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$runtime" "$event" "$code" "$elapsed" "${1##*/}" >> "$LOG"
exit $code
