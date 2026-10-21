#!/bin/bash
# Template: Shell dispatcher with plugin checks
# Event: PostToolUse (adapt for other events)
# Purpose: Single hook that runs all checks in a checks/ directory.
#
# This is the recommended dispatcher pattern. Each check is a separate
# script in checks/ that receives pre-parsed arguments. To add a new
# check, drop a .sh file in checks/ and make it executable.
#
# Check interface: $1=file_path $2=rel_path $3=is_test $4=is_config
# Check exit codes: 0=pass, 2=warning (stdout shown to Claude)
#
# See references/dispatcher-pattern.md for the full guide.

set -euo pipefail

CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checks"

# --- Parse input once ---

JSON_INPUT=$(cat)
file_path=$(echo "${JSON_INPUT}" | jq -r '.tool_input.file_path // empty')

# Skip if no file path or file doesn't exist
if [ -z "${file_path}" ] || [ ! -f "${file_path}" ]; then
    exit 0
fi

# Resolve to absolute path
if [[ "${file_path}" != /* ]]; then
    file_path="${CLAUDE_PROJECT_DIR}/${file_path}"
fi

# --- Filter: only code files ---
# Customize this list for your project's languages

case "${file_path}" in
    *.ts|*.tsx|*.js|*.jsx) ;;
    # Add more: *.py|*.rb|*.go|*.rs)
    *) exit 0 ;;
esac

# --- Classify once ---

is_test="false"
case "${file_path}" in
    *__tests__*|*.test.*|*.spec.*|*/mocks/*|*/test/*|*mock*) is_test="true" ;;
esac

is_config="false"
case "${file_path}" in
    *.config.*) is_config="true" ;;
esac

rel_path="${file_path#${CLAUDE_PROJECT_DIR}/}"

# --- Run all checks ---

output=""
had_warning=false

for check in "${CHECKS_DIR}"/*.sh; do
    [ -x "${check}" ] || continue

    result=""
    exit_code=0
    result=$("${check}" "${file_path}" "${rel_path}" "${is_test}" "${is_config}" 2>&1) || exit_code=$?

    if [ -n "${result}" ]; then
        if [ -n "${output}" ]; then
            output="${output}
---
"
        fi
        output="${output}${result}"
        if [ "${exit_code}" = "2" ]; then
            had_warning=true
        fi
    fi
done

# --- Output ---

if [ -n "${output}" ]; then
    echo "${output}"
    if ${had_warning}; then
        exit 2
    fi
fi

exit 0
