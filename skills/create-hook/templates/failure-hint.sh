#!/usr/bin/env bash
# Template: turn a known tool failure into a precise next step
# Event: PostToolUseFailure   Matcher: Bash   (Claude Code only; Codex has no failure event)
#
# Key on the first line of .error ("Exit code N") and stable substrings; the rest
# of the error text is display output and changes between versions.

# shellcheck source=/dev/null
. "$(dirname "$0")/lib/hook-io.sh"
hook_read

error=$(printf '%s' "$HOOK_INPUT" | jq -r '.error // ""')

case "$error" in
    *"Cannot find module"*)
        hook_context "A Node module is missing. This project installs dependencies with the lockfile's package manager; run its install command, then retry." ;;
    *"command not found"*)
        hook_context "The command is not on PATH in the agent's shell. Check the project's toolchain setup (mise, nvm, venv) before installing anything globally." ;;
esac

hook_pass
