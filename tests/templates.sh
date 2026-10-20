#!/usr/bin/env bash
# Runs every template against Claude Code and Codex fixtures under macOS /bin/bash (3.2).
# Usage: tests/templates.sh        Exit 0 when every case matches.

set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
skill="$root/skills/create-hook"
fx="$skill/fixtures"
t="$skill/templates"
run="python3 $skill/scripts/test-hook.py --repeat 3"
BASH_BIN=${BASH_BIN:-/bin/bash}

work=$(mktemp -d "${TMPDIR:-/tmp}/hook-tests.XXXXXX")
trap 'rm -r "$work"' EXIT
proj="$work/project"
mkdir -p "$proj/src" && git -C "$proj" init -q && touch "$proj/src/app.ts"

# case NAME BASE_FIXTURE JQ_FILTER: write a variant with cwd pointed at the temp project.
case_() {
    jq --arg p "$proj" "$3"' | .cwd = $p' "$fx/$2" > "$work/$1.json"
    printf '%s' "$work/$1.json"
}
same() { case_ "$1" "$2" '.'; }

failed=0
check() { echo "== $1"; shift; "$@" || failed=1; echo; }

check guard-bash $run "$BASH_BIN $t/guard-bash.sh" \
    "$(same c-ok claude/PreToolUse-bash.json):pass" \
    "$(case_ c-rm claude/PreToolUse-bash.json '.tool_input.command="rm -rf /"'):deny" \
    "$(case_ c-rm-home claude/PreToolUse-bash.json '.tool_input.command="cd x && rm -fr ~"'):deny" \
    "$(case_ c-rm-local claude/PreToolUse-bash.json '.tool_input.command="rm -rf ./build"'):pass" \
    "$(case_ c-push claude/PreToolUse-bash.json '.tool_input.command="git push --force origin main"'):deny" \
    "$(case_ c-reset claude/PreToolUse-bash.json '.tool_input.command="git reset --hard HEAD~1"'):ask" \
    "$(same x-ok codex/PreToolUse-bash.json):pass" \
    "$(case_ x-reset codex/PreToolUse-bash.json '.tool_input.command="git reset --hard"'):deny"

check guard-files $run "$BASH_BIN $t/guard-files.sh" \
    "$(same c-write claude/PreToolUse-write.json):pass" \
    "$(case_ c-env claude/PreToolUse-edit.json '.tool_input.file_path="/x/.env"'):deny" \
    "$(case_ c-lock claude/PreToolUse-write.json '.tool_input.file_path="/x/pnpm-lock.yaml"'):deny" \
    "$(same x-patch-env codex/PreToolUse-apply_patch.json):deny" \
    "$(case_ x-patch-ok codex/PreToolUse-apply_patch.json '.tool_input.command="*** Begin Patch\n*** Update File: src/app.ts\n*** End Patch\n"'):pass"

printf '{"a": 1,}\n' > "$proj/bad.json"
check post-edit-check $run "$BASH_BIN $t/post-edit-check.sh" \
    "$(case_ c-edit-ok claude/PostToolUse-edit.json '.tool_input.file_path = ($p + "/src/app.ts")' ):pass" \
    "$(case_ c-edit-bad claude/PostToolUse-edit.json '.tool_input.file_path = ($p + "/bad.json")'):block" \
    "$(case_ x-patch-bad codex/PostToolUse-apply_patch.json '.tool_input.command="*** Begin Patch\n*** Update File: bad.json\n*** End Patch\n"'):block"

check inject-context $run "$BASH_BIN $t/inject-context.sh" \
    "$(same c-start claude/SessionStart.json):context" \
    "$(same x-start codex/SessionStart.json):context" \
    "$(same x-prompt codex/UserPromptSubmit.json):context"

check approve-safe $run "$BASH_BIN $t/approve-safe.sh" \
    "$(same c-status claude/PermissionRequest-bash.json):approve" \
    "$(case_ c-chain claude/PermissionRequest-bash.json '.tool_input.command="git status; rm x"'):pass" \
    "$(case_ c-subst claude/PermissionRequest-bash.json '.tool_input.command="cat $(echo /etc/passwd)"'):pass" \
    "$(same x-status codex/PermissionRequest-bash.json):approve"

check failure-hint $run "$BASH_BIN $t/failure-hint.sh" \
    "$(same c-module claude/PostToolUseFailure-bash.json):context" \
    "$(case_ c-other claude/PostToolUseFailure-bash.json '.error="Exit code 1\nboom"'):pass"

check notify $run "$BASH_BIN $t/notify.sh" \
    "$(same c-notify claude/Notification.json):pass"

# Stop gate: state written by track-activity decides the outcome.
sid="test-$$"
edit=$(case_ c-track-edit claude/PostToolUse-edit.json ".session_id=\"$sid\"")
tests=$(case_ c-track-test claude/PostToolUse-bash.json ".session_id=\"$sid\"")
stop=$(case_ c-stop claude/Stop.json ".session_id=\"$sid\"")
stop_active=$(case_ c-stop-active claude/Stop.json ".session_id=\"$sid\" | .stop_hook_active=true")
check track+stop sh -c "
    $run '$BASH_BIN $t/track-activity.sh' '$edit:pass' &&
    $run '$BASH_BIN $t/stop-gate.sh' '$stop:continue' '$stop_active:pass' &&
    $run '$BASH_BIN $t/track-activity.sh' '$tests:pass' &&
    $run '$BASH_BIN $t/stop-gate.sh' '$stop:pass'"
rm -f "${TMPDIR:-/tmp}/agent-hook-state-$sid"

# Dispatcher: two checks, one finding.
mkdir -p "$work/hooks/checks" "$work/hooks/lib"
cp "$t/dispatcher.sh" "$work/hooks/" && cp "$t/lib/hook-io.sh" "$work/hooks/lib/"
printf '#!/usr/bin/env bash\nexit 0\n' > "$work/hooks/checks/ok.sh"
printf '#!/usr/bin/env bash\ncase "$HOOK_PATHS" in *app.ts*) echo "app.ts is frozen" >&2; exit 2;; esac\n' > "$work/hooks/checks/frozen.sh"
chmod +x "$work/hooks/checks/"*.sh
check dispatcher $run "$BASH_BIN $work/hooks/dispatcher.sh" \
    "$(same c-pre-app claude/PreToolUse-write.json):deny" \
    "$(same c-post-app claude/PostToolUse-edit.json):block" \
    "$(case_ c-post-other claude/PostToolUse-edit.json '.tool_input.file_path="/x/other.md"'):pass" \
    "$(same x-pre-patch codex/PreToolUse-apply_patch.json):deny"

check debug-wrap sh -c "HOOK_DEBUG_LOG='$work/debug.log' $run '$BASH_BIN $t/debug-wrap.sh $BASH_BIN $t/guard-bash.sh' '$(case_ w-rm claude/PreToolUse-bash.json '.tool_input.command="rm -rf /"'):deny' && grep -q 'claude PreToolUse exit=0' '$work/debug.log' && echo 'debug log ok'"

for f in "$t"/*.json; do jq -e '.hooks' "$f" >/dev/null || { echo "invalid template JSON: $f"; failed=1; }; done

[ "$failed" = 0 ] && echo "ALL TEMPLATE TESTS PASS" || echo "TEMPLATE TESTS FAILED"
exit "$failed"
