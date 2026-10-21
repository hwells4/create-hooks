#!/usr/bin/env python3
"""
Template: Permission Request handler
Event: PermissionRequest
Purpose: Programmatically handle permission dialogs with auto-approve, deny, or modify

This hook runs when a permission dialog would be shown to the user.
Unlike PreToolUse (which can deny before dialog), PermissionRequest intercepts
the dialog itself and can respond on the user's behalf.

Usage: Copy to .claude/hooks/ and customize the handle_permission() function
"""

import json
import os
import sys


def handle_permission(
    tool_name: str,
    tool_input: dict,
    permission_mode: str,
) -> dict | None:
    """
    Handle a permission request.

    Returns:
        None - Show normal permission dialog to user
        dict - Automated response with structure:
            {
                "behavior": "allow" | "deny",
                "updatedInput": {...},  # Optional, for "allow" only
                "message": "...",       # Optional, for "deny" only
                "interrupt": False      # Optional, for "deny" only - stops Claude entirely
            }
    """

    # Example 1: Auto-approve reads of documentation files
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path.endswith((".md", ".txt", ".rst", ".mdx")):
            return {
                "behavior": "allow",
            }

    # Example 2: Auto-approve glob/grep in safe directories
    if tool_name in ("Glob", "Grep"):
        path = tool_input.get("path", "")
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if path.startswith(project_dir) or not path:
            return {
                "behavior": "allow",
            }

    # Example 3: Deny and stop Claude for dangerous operations
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        dangerous_patterns = ["rm -rf /", "sudo rm", "> /dev/sd", "mkfs"]
        for pattern in dangerous_patterns:
            if pattern in command:
                return {
                    "behavior": "deny",
                    "message": f"Dangerous command blocked: contains '{pattern}'",
                    "interrupt": True,  # Stop Claude entirely
                }

    # Example 4: Modify and allow (sanitize input)
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        # Add timeout to long-running commands
        if command.startswith(("npm ", "yarn ", "pip ")):
            return {
                "behavior": "allow",
                "updatedInput": {
                    **tool_input,
                    "timeout": 120000,  # 2 minutes
                },
            }

    # Example 5: Deny with feedback (but don't stop Claude)
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        protected = [".env", ".env.local", "credentials.json", "secrets.yaml"]
        for p in protected:
            if file_path.endswith(p):
                return {
                    "behavior": "deny",
                    "message": f"Cannot write to protected file: {p}. Use environment variables instead.",
                    "interrupt": False,  # Claude can try alternative approach
                }

    # Return None to show normal permission dialog
    return None


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    permission_mode = input_data.get("permission_mode", "default")

    decision = handle_permission(tool_name, tool_input, permission_mode)

    if decision is not None:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": decision,
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
