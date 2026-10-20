#!/usr/bin/env bash
# Template: run a fast per-file check after an edit and hand failures to the agent
# Event: PostToolUse   Matcher: Write|Edit
#
# The tool already ran, so exit 2 does not undo anything: the stderr becomes
# feedback the agent reads next to the tool result. Keep each check to the
# changed file and well under a second; anything slower belongs in an async
# hook (see references/performance.md).

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

findings=""
while IFS= read -r path; do
    [ -f "$path" ] || continue
    out=""
    case "$path" in
        *.sh)            command -v shellcheck >/dev/null && out=$(shellcheck -f gcc "$path" 2>&1) ;;
        *.py)            command -v ruff >/dev/null && out=$(ruff check --quiet "$path" 2>&1) ;;
        *.json)          out=$(jq empty "$path" 2>&1) ;;
        # *.ts|*.tsx)    out=$(npx --no-install eslint --quiet "$path" 2>&1) ;;
    esac
    [ -z "$out" ] || findings="$findings$path:
$out
"
done <<EOF
$(hook_paths)
EOF

[ -z "$findings" ] || hook_block "post-edit-check found problems. Fix them before moving on:
$findings"
hook_pass
