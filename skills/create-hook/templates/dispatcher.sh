#!/usr/bin/env bash
# Template: one registered hook that runs every check in checks/
# Event: any; written for PreToolUse or PostToolUse on Write|Edit
#
# Parses stdin once, exports the HOOK_* variables, and runs each executable
# checks/*.sh with the raw payload on stdin. Check contract:
#   exit 0            pass
#   exit 2 + stderr   finding (stderr is the message for the agent)
# PreToolUse stops at the first finding (a deny needs only one reason).
# Other events run all checks in parallel and report every finding together.
# Adding a check is dropping a file in checks/: no config change, no new trust review.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read
export HOOK_EVENT HOOK_TOOL HOOK_CWD HOOK_CMD HOOK_FILE HOOK_PROMPT HOOK_SESSION HOOK_STOP_ACTIVE HOOK_RUNTIME
HOOK_PATHS=$(hook_paths)
export HOOK_PATHS

checks_dir="$(cd "$(dirname "$0")" && pwd)/checks"

if [ "$HOOK_EVENT" = PreToolUse ]; then
    for check in "$checks_dir"/*.sh; do
        [ -x "$check" ] || continue
        msg=$(printf '%s' "$HOOK_INPUT" | "$check" 2>&1 >/dev/null)
        [ $? -eq 2 ] && hook_deny "${check##*/}: $msg"
    done
    hook_pass
fi

out=$(mktemp -d "${TMPDIR:-/tmp}/hook-dispatch.XXXXXX")
trap 'rm -r "$out"' EXIT
for check in "$checks_dir"/*.sh; do
    [ -x "$check" ] || continue
    name=${check##*/}
    ( printf '%s' "$HOOK_INPUT" | "$check" 2>"$out/$name.err" >/dev/null; echo $? > "$out/$name.code" ) &
done
wait

findings=""
for code_file in "$out"/*.code; do
    [ -e "$code_file" ] || continue
    [ "$(cat "$code_file")" = 2 ] || continue
    name=$(basename "$code_file" .code)
    findings="$findings--- $name
$(cat "$out/$name.err")
"
done

# Findings go to stderr with exit 2: that is the channel the agent reads.
[ -z "$findings" ] || hook_block "$findings"
hook_pass
