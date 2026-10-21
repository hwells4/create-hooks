#!/bin/bash
# Template: Notification forwarder hook
# Event: Notification
# Purpose: Forward Claude Code notifications to external systems
#
# Usage: Copy to .claude/hooks/ and customize notification handling

set -e

# Read JSON input
INPUT=$(cat)

# Extract notification details
MESSAGE=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null || echo "")
TYPE=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('notification_type', ''))" 2>/dev/null || echo "")

# Skip if no message
[ -z "$MESSAGE" ] && exit 0

# Forward based on notification type
case "$TYPE" in
    "permission_prompt")
        # Claude is waiting for permission
        # Example: Send to macOS notification center
        if command -v osascript &> /dev/null; then
            osascript -e "display notification \"$MESSAGE\" with title \"Claude Code\" sound name \"Ping\""
        fi
        ;;

    "idle_prompt")
        # Claude has been waiting for input
        # Example: Play a sound
        if command -v afplay &> /dev/null; then
            afplay /System/Library/Sounds/Glass.aiff &
        fi
        ;;

    "auth_success")
        # Authentication completed
        # Log it
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auth: $MESSAGE" >> ~/.claude/auth.log
        ;;

    *)
        # Default: log to file
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$TYPE] $MESSAGE" >> ~/.claude/notifications.log
        ;;
esac

exit 0
