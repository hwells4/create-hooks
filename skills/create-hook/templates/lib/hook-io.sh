#!/usr/bin/env bash
# hook-io.sh - parse hook stdin once, emit decisions that Claude Code and Codex both accept.
#
# Usage, at the top of a hook script:
#   . "$(dirname "$0")/lib/hook-io.sh"
#   hook_read
#
# After hook_read these are set:
#   HOOK_EVENT  HOOK_TOOL  HOOK_CWD  HOOK_CMD  HOOK_FILE  HOOK_PROMPT  HOOK_SESSION
#   HOOK_STOP_ACTIVE (true|false)  HOOK_RUNTIME (claude|codex)  HOOK_INPUT (raw JSON)
#
# Every emitter ends the script. Requires jq. Compatible with bash 3.2 (macOS /bin/bash).
# With HOOK_TRACE=<file> in the environment, each run appends one line:
#   <runtime> <script> <event> <tool> <decision> exit=<code>

# shellcheck disable=SC2153  # HOOK_* are assigned by the eval in hook_read

hook_read() {
    HOOK_INPUT=$(< /dev/stdin)
    eval "$(printf '%s' "$HOOK_INPUT" | jq -r '@sh "
        HOOK_EVENT=\(.hook_event_name // "")
        HOOK_SESSION=\(.session_id // "")
        HOOK_TOOL=\(.tool_name // "")
        HOOK_CWD=\(.cwd // "")
        HOOK_CMD=\(.tool_input.command // "" | tostring)
        HOOK_FILE=\(.tool_input.file_path // .tool_input.notebook_path // "")
        HOOK_PROMPT=\(.prompt // "")
        HOOK_STOP_ACTIVE=\(.stop_hook_active // false)
        _HOOK_TURN_ID=\(.turn_id // "")"')"

    # Codex marks turn-scoped events with turn_id and keeps its own tool names on stdin.
    # Set HOOK_RUNTIME in the hook command to override detection.
    if [ -z "${HOOK_RUNTIME:-}" ]; then
        case "$HOOK_TOOL" in
            apply_patch|spawn_agent) HOOK_RUNTIME=codex ;;
            *) if [ -n "$_HOOK_TURN_ID" ]; then HOOK_RUNTIME=codex; else HOOK_RUNTIME=claude; fi ;;
        esac
    fi
    : "${HOOK_CWD:=$PWD}"
    if [ -n "${HOOK_TRACE:-}" ]; then trap '_hook_trace $?' EXIT; fi
}

_hook_trace() {
    printf '%s %s %s %s %s exit=%s\n' "$HOOK_RUNTIME" "${0##*/}" "${HOOK_EVENT:--}" "${HOOK_TOOL:--}" \
        "${_HOOK_DECISION:-pass}" "$1" >> "$HOOK_TRACE"
}

# Project root. Claude exports CLAUDE_PROJECT_DIR; Codex does not, so fall back to the git root.
hook_project_dir() {
    if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
        printf '%s\n' "$CLAUDE_PROJECT_DIR"
    else
        git -C "$HOOK_CWD" rev-parse --show-toplevel 2>/dev/null || printf '%s\n' "$HOOK_CWD"
    fi
}

# Absolute paths a file-editing call touches, one per line.
# Claude Write/Edit carry file_path; Codex apply_patch carries a patch in tool_input.command.
hook_paths() {
    if [ "$HOOK_TOOL" = apply_patch ]; then
        printf '%s\n' "$HOOK_CMD" | sed -n \
            -e 's/^\*\*\* Add File: //p' \
            -e 's/^\*\*\* Update File: //p' \
            -e 's/^\*\*\* Delete File: //p' \
            -e 's/^\*\*\* Move to: //p'
    elif [ -n "$HOOK_FILE" ]; then
        printf '%s\n' "$HOOK_FILE"
    fi | while IFS= read -r p; do
        case "$p" in
            /*) printf '%s\n' "$p" ;;
            ?*) printf '%s\n' "$HOOK_CWD/$p" ;;
        esac
    done
}

# Exit 2 with the reason on stderr. Blocks PreToolUse, UserPromptSubmit, Stop, SubagentStop;
# on PostToolUse it hands the reason to the agent as feedback. Same meaning in both runtimes.
hook_block() {
    _HOOK_DECISION=block
    printf '%s\n' "$1" >&2
    exit 2
}

# PreToolUse: refuse the call; the reason goes to the agent.
hook_deny() {
    _HOOK_DECISION=deny
    jq -nc --arg r "$1" \
        '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
    exit 0
}

# PreToolUse: send the call to the human. Codex has no "ask", so it fails closed as a deny.
hook_ask() {
    if [ "$HOOK_RUNTIME" = codex ]; then
        hook_deny "Needs human approval: $1"
    fi
    _HOOK_DECISION=ask
    jq -nc --arg r "$1" \
        '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
    exit 0
}

# PermissionRequest: approve on the human's behalf.
hook_approve() {
    _HOOK_DECISION=approve
    jq -nc '{hookSpecificOutput: {hookEventName: "PermissionRequest", decision: {behavior: "allow"}}}'
    exit 0
}

# Add a factual note to the agent's context for the current event.
hook_context() {
    _HOOK_DECISION=context
    jq -nc --arg e "$HOOK_EVENT" --arg c "$1" \
        '{hookSpecificOutput: {hookEventName: $e, additionalContext: $c}}'
    exit 0
}

# Stop / SubagentStop: keep the agent working, with the reason as its next instruction.
hook_continue() {
    _HOOK_DECISION="continue"
    jq -nc --arg r "$1" '{decision: "block", reason: $r}'
    exit 0
}

# Nothing to say: let the action through.
hook_pass() {
    exit 0
}
