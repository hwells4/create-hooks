#!/usr/bin/env bash
# Builds a project with known-bad and known-good hook configs and checks validate-hooks.py
# reports each rule. Usage: tests/validator.sh
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
work=$(mktemp -d "${TMPDIR:-/tmp}/validator-tests.XXXXXX")
trap 'rm -r "$work"' EXIT
mkdir -p "$work/home" "$work/proj" && git -C "$work/proj" init -q
python3 "$root/tests/validator_fixture.py" "$work/proj" >/dev/null
out=$(HOME="$work/home" python3 "$root/skills/create-hook/scripts/validate-hooks.py" --project "$work/proj" 2>&1)
code=$?

failed=0
expect() { case "$out" in *"$1"*) ;; *) echo "MISSING: $1"; failed=1 ;; esac; }
expect "top-level keys ['version'] not allowed"
expect "script not found"
expect "not executable"
expect "means the hook NEVER runs"
expect "SessionStart accepts only command|mcp_tool"
expect "Codex ignores \`args\`"
expect "Codex does not support http"
expect "unknown codex event 'Notification'"
expect "exit 1 is non-blocking"
expect "MultiEdit"
expect "exit 2 shows only stderr"
expect "stop_hook_active"
expect "deprecated"
expect "has no shebang"
expect "runs once"
[ "$code" = 1 ] || { echo "expected exit 1, got $code"; failed=1; }
case "$out" in *"block-good.sh:"*|*"stop-good.sh:"*|*"ask-lib.sh:"*) echo "clean script was flagged"; failed=1 ;; esac

clean=$(HOME="$work/home" python3 "$root/skills/create-hook/scripts/validate-hooks.py" --project "$root" 2>&1) || { echo "repo itself not clean: $clean"; failed=1; }

[ "$failed" = 0 ] && echo "ALL VALIDATOR TESTS PASS" || { echo "VALIDATOR TESTS FAILED"; echo "$out"; }
exit "$failed"
