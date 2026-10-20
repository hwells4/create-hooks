#!/usr/bin/env bash
# Template: refuse dangerous shell commands
# Event: PreToolUse   Matcher: Bash   (same matcher in Claude Code and Codex)
#
# Claude config can add  "if": "Bash(rm *)"  per rule to skip the process entirely;
# Codex ignores "if", so this script still filters on its own.
#
# This is a guardrail: it catches the obvious forms. For hard enforcement use
# permission deny rules (Claude) or sandbox/approval policy (Codex).

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

# shellcheck disable=SC2016  # literal $HOME in a regex
# Extended regexes (bash =~, POSIX ERE) matched against the full command line.
DENY_PATTERNS=(
    '(^|[;&|[:space:]])rm[[:space:]]+-[a-zA-Z]*([rR][a-zA-Z]*f|f[a-zA-Z]*[rR])[a-zA-Z]*[[:space:]]+(/|~|\$HOME)([[:space:]]|/?$)'
    '(^|[;&|[:space:]])git[[:space:]]+push[[:space:]].*(--force|-f)([[:space:]]|$).*(main|master)'
    '(^|[;&|[:space:]])mkfs\.'
    '>[[:space:]]*/dev/(sd|nvme|disk)'
)

# Commands that should reach a human instead of being refused outright.
ASK_PATTERNS=(
    '(^|[;&|[:space:]])git[[:space:]]+reset[[:space:]]+--hard'
    '(^|[;&|[:space:]])(curl|wget)[^|]*\|[[:space:]]*(ba|z)?sh'
)

[ -n "$HOOK_CMD" ] || hook_pass

# Built-in regex matching: no grep process per rule on the hot path.
for rule in "${DENY_PATTERNS[@]}"; do
    [[ $HOOK_CMD =~ $rule ]] && hook_deny "Blocked by guard-bash: command matches /$rule/. Use a narrower command."
done
for rule in "${ASK_PATTERNS[@]}"; do
    [[ $HOOK_CMD =~ $rule ]] && hook_ask "guard-bash: command matches /$rule/."
done

hook_pass
