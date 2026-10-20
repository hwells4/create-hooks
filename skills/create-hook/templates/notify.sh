#!/usr/bin/env bash
# Template: desktop notification when the agent needs the human or finishes
# Event: Notification (Claude Code), Stop (Codex has no Notification event)
#
# Claude Code: returns terminalSequence so the runtime emits OSC 9 itself (hooks have no
# /dev/tty). Keep this hook synchronous there: async hooks deliver only additionalContext
# and systemMessage. Codex: shells out to the OS notifier; set "async": true.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

message=$(printf '%s' "$HOOK_INPUT" | jq -r '.message // "Agent finished"')

if [ "$HOOK_RUNTIME" = claude ]; then
    jq -nc --arg m "$message" '{terminalSequence: ("\u001b]9;" + $m + "\u0007")}'
    exit 0
fi

if command -v osascript >/dev/null; then
    osascript -e "display notification \"${message//\"/\\\"}\" with title \"Codex\"" >/dev/null 2>&1
elif command -v notify-send >/dev/null; then
    notify-send "Codex" "$message" >/dev/null 2>&1
fi
hook_pass
