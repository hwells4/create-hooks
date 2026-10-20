#!/usr/bin/env bash
# Template: refuse edits to protected files
# Event: PreToolUse   Matcher: Write|Edit
#
# Codex routes apply_patch through the Write|Edit matcher, but stdin still says
# tool_name "apply_patch" with the patch text in tool_input.command; hook_paths
# extracts every file the patch touches, so one script covers both runtimes.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

# Shell glob patterns matched against each absolute path.
PROTECTED=(
    '*/.env' '*/.env.*'
    '*.pem' '*.key' '*/id_rsa*'
    '*/.git/*'
    '*/package-lock.json' '*/pnpm-lock.yaml' '*/yarn.lock' '*/uv.lock'
)

while IFS= read -r path; do
    for glob in "${PROTECTED[@]}"; do
        # shellcheck disable=SC2254  # unquoted on purpose: $glob is a pattern
        case "$path" in
            $glob) hook_deny "Blocked by guard-files: $path is protected ($glob). Edit the source it is generated from, or ask the user." ;;
        esac
    done
done <<EOF
$(hook_paths)
EOF

hook_pass
