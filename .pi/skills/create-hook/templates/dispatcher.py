#!/usr/bin/env python3
"""
Template: Python function dispatcher
Event: Any (PostToolUse, PreToolUse, UserPromptSubmit, etc.)
Purpose: Single hook entry point that routes to multiple handler functions.

Use this when your checks need complex logic (AST parsing, API calls, shared
data structures). For simple grep/awk pattern checks, use the shell dispatcher
template instead (dispatcher.sh).

Usage:
  1. Copy to .claude/hooks/
  2. Rename to {event}-dispatcher.py (e.g., post-write-dispatcher.py)
  3. Replace the example handlers with your logic
  4. Register ONE entry in settings.json

See references/dispatcher-pattern.md for the full guide.
"""

import json
import sys


# ── Handler Functions ──────────────────────────────────────
#
# Each handler receives the parsed context and returns:
#   None          → skip (this handler doesn't apply)
#   {"message": "..."} → informational output (stdout)
#   {"message": "...", "block": True} → block the action (exit 2)
#
# Add your handlers here, then register them in HANDLERS below.


def handle_example_lint(tool_name, tool_input, **ctx):
    """Example: lint check on file writes."""
    file_path = tool_input.get("file_path", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None
    if not file_path.endswith((".py", ".js", ".ts")):
        return None
    # ... your lint logic here ...
    return {"message": f"Lint passed: {file_path}"}


def handle_example_security(tool_name, tool_input, **ctx):
    """Example: block writes to sensitive files."""
    file_path = tool_input.get("file_path", "")
    sensitive = [".env", "credentials", "secrets", "id_rsa"]
    for pattern in sensitive:
        if pattern in file_path:
            return {
                "message": f"Blocked: write to sensitive file {file_path}",
                "block": True,
            }
    return None


# ── Handler Registry ───────────────────────────────────────
#
# Order matters: handlers run top-to-bottom.
# If any handler sets block=True, the action is blocked.

HANDLERS = [
    handle_example_lint,
    handle_example_security,
]


# ── Dispatcher Core (usually no changes needed below) ──────

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    ctx = {
        "tool_result": data.get("tool_result", {}),
        "session_id": data.get("session_id", ""),
        "hook_event_name": data.get("hook_event_name", ""),
    }

    messages = []
    should_block = False

    for handler in HANDLERS:
        try:
            result = handler(tool_name, tool_input, **ctx)
            if result is None:
                continue
            if result.get("block"):
                should_block = True
            msg = result.get("message")
            if msg:
                messages.append(msg)
        except Exception:
            pass  # Individual handler failure doesn't break others

    if should_block:
        print("\n".join(messages), file=sys.stderr)
        sys.exit(2)

    if messages:
        print("\n".join(messages))

    sys.exit(0)


if __name__ == "__main__":
    main()
