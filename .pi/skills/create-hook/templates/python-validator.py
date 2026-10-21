#!/usr/bin/env python3
"""
Template: Python validation hook
Event: PreToolUse (matcher: varies)
Purpose: Validate tool inputs with complex logic

Usage: Copy to .claude/hooks/ and customize validate_tool_input()
"""

import json
import re
import sys


def validate_tool_input(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """
    Validate tool input. Return (is_valid, error_message).

    Customize this function for your validation logic.
    """
    # Example: Validate Bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")

        # Block dangerous patterns
        dangerous = [
            r"\brm\s+-rf\s+/",
            r"\bsudo\b",
            r">\s*/dev/",
            r"\bdd\s+.*of=/dev/",
        ]

        for pattern in dangerous:
            if re.search(pattern, command):
                return False, f"Command blocked: matches dangerous pattern"

        # Require description for complex commands
        if "|" in command or "&&" in command:
            if not tool_input.get("description"):
                return False, "Complex commands require a description"

    # Example: Validate Write tool
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")

        # Block writes to sensitive files
        sensitive = [".env", "credentials", "secrets", ".git/"]
        for pattern in sensitive:
            if pattern in file_path:
                return False, f"Cannot write to sensitive path: {pattern}"

    # Example: Validate Edit tool
    if tool_name == "Edit":
        file_path = tool_input.get("file_path", "")

        # Warn on package.json edits
        if file_path.endswith("package.json"):
            return False, "Editing package.json requires confirmation. Use 'npm install' instead for dependencies."

    return True, ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    is_valid, error_message = validate_tool_input(tool_name, tool_input)

    if not is_valid:
        print(error_message, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
