#!/usr/bin/env bash
# Checks live-test.py's scratch builder. With LIVE=1 it also runs guard-bash red and green in each
# installed runtime (model calls, about 10s each). Usage: tests/live.sh  |  LIVE=1 tests/live.sh
# Pick cheap test models with CLAUDE_MODEL, CODEX_MODEL, CODEX_EFFORT.
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
skill="$root/skills/create-hook"
work=$(mktemp -d "${TMPDIR:-/tmp}/live-tests.XXXXXX")
trap 'rm -r "$work"' EXIT

src="$work/src"
mkdir -p "$src/.agents/hooks/lib" "$src/.claude" "$src/.codex"
git -C "$src" init -q
cp "$skill/templates/guard-bash.sh" "$src/.agents/hooks/"
cp "$skill/templates/lib/hook-io.sh" "$src/.agents/hooks/lib/"
echo '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"\"$CLAUDE_PROJECT_DIR\"/.agents/hooks/guard-bash.sh","timeout":10}]}]}}' > "$src/.claude/settings.json"
echo '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"\"$(git rev-parse --show-toplevel)\"/.agents/hooks/guard-bash.sh","timeout":10}]}]}}' > "$src/.codex/hooks.json"
echo '{"permissions":{"allow":[]}}' > "$src/.claude/settings.local.json"
printf 'settings.local.json\n' > "$src/.claude/.gitignore"
echo "readme" > "$src/README.md"

failed=0
dir=$(python3 "$skill/scripts/live-test.py" scratch --from "$src" --out "$work/s") || failed=1
for f in README.md .agents/hooks/guard-bash.sh .agents/hooks/lib/hook-io.sh .claude/settings.json \
         .claude/settings.local.json .codex/hooks.json; do
    [ -f "$dir/$f" ] || { echo "FAIL scratch missing $f"; failed=1; }
done
[ "$(git -C "$work/s/remote.git" rev-parse --verify -q main)" = "$(git -C "$dir" rev-parse HEAD)" ] \
    || { echo "FAIL origin main does not match scratch HEAD"; failed=1; }

if [ "${LIVE:-}" = 1 ]; then
    cx_config="${CODEX_HOME:-$HOME/.codex}/config.toml"
    cx_before=$(cksum < "$cx_config" 2>/dev/null)
    for rt in claude codex; do
        command -v "$rt" >/dev/null || { echo "skip $rt: not installed"; continue; }
        opts=()
        if [ "$rt" = claude ]; then model=${CLAUDE_MODEL:-}; else model=${CODEX_MODEL:-}; fi
        [ -n "$model" ] && opts+=(--model "$model")
        [ "$rt" = codex ] && [ -n "${CODEX_EFFORT:-}" ] && opts+=(--effort "$CODEX_EFFORT")
        python3 "$skill/scripts/live-test.py" run --dir "$dir" --runtime "$rt" --hook guard-bash.sh \
            --expect deny --command "git push --force origin main" ${opts[@]+"${opts[@]}"} || failed=1
        python3 "$skill/scripts/live-test.py" run --dir "$dir" --runtime "$rt" --hook guard-bash.sh \
            --expect pass --command "git status --short" ${opts[@]+"${opts[@]}"} || failed=1
    done
    [ "$(git -C "$work/s/remote.git" rev-list --count main)" = 1 ] || { echo "FAIL a push reached origin"; failed=1; }
    if command -v codex >/dev/null; then
        # Green case that writes .git and the remote: needs the sandbox's writable roots
        git -C "$dir" checkout -q -b feat/live
        python3 "$skill/scripts/live-test.py" run --dir "$dir" --runtime codex --hook guard-bash.sh --expect pass \
            --command "git commit --allow-empty -qm live && git push -q origin feat/live" \
            ${CODEX_MODEL:+--model "$CODEX_MODEL"} ${CODEX_EFFORT:+--effort "$CODEX_EFFORT"} || failed=1
        git -C "$work/s/remote.git" rev-parse -q --verify feat/live >/dev/null \
            || { echo "FAIL codex could not push a feature branch from the sandbox"; failed=1; }
    fi
    [ "$(cksum < "$cx_config" 2>/dev/null)" = "$cx_before" ] || { echo "FAIL live run changed $cx_config"; failed=1; }
fi

[ "$failed" = 0 ] && echo "ALL LIVE TESTS PASS"
exit "$failed"
