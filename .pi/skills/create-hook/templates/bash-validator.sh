#!/bin/bash
# Template: Bash command validator hook
# Event: PreToolUse (matcher: Bash)
# Purpose: Block dangerous shell commands
#
# Usage: Copy this file to .claude/hooks/ and customize BLOCKED_PATTERNS

set -e

# Patterns to block (customize these)
BLOCKED_PATTERNS=(
    "rm -rf /"
    "rm -rf ~"
    "rm -rf \$HOME"
    "> /dev/sda"
    "mkfs."
    ":(){:|:&};:"  # Fork bomb
)

# Read JSON input from stdin
INPUT=$(cat)

# Extract tool name and command using grep/sed (portable)
TOOL_NAME=$(echo "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:.*"\([^"]*\)"/\1/')

# Only process Bash tool
if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# Extract command (handles multiline by looking for the field)
COMMAND=$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:.*"\([^"]*\)"/\1/')

# Check against blocked patterns
for PATTERN in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -q "$PATTERN"; then
        echo "Blocked: Command contains dangerous pattern '$PATTERN'" >&2
        exit 2
    fi
done

# Command is safe
exit 0
