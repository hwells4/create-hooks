#!/bin/bash
# debug-wrap.sh - Minimal hook wrapper for debugging
#
# Logs when hooks fire and their exit codes with ~0.5ms overhead.
# Use by wrapping your hook command in settings.json:
#
#   Before: "command": "python3 .claude/hooks/my-hook.py"
#   After:  "command": ".claude/hooks/debug-wrap.sh python3 .claude/hooks/my-hook.py"
#
# View logs with: tail -f .claude/hooks/.debug.log
# Or use: python3 scripts/hook-log.py (in this plugin)

LOG="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/.debug.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null

# Pass stdin through to the hook, capture exit code
cat | "$@"
CODE=$?

# Log: timestamp, exit code, hook command (just the script name)
echo "$(date '+%H:%M:%S') exit=$CODE ${1##*/} ${2##*/}" >> "$LOG"

exit $CODE
