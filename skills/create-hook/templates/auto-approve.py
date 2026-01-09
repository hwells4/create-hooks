#!/usr/bin/env python3
"""
Template: Auto-approve safe operations
Event: PreToolUse (matcher: Read|Write|Edit|Bash)
Purpose: Bypass permission dialogs for known-safe operations

Usage: Copy to .claude/hooks/ and customize SAFE_PATTERNS
"""

import json
import re
import sys


# Patterns for auto-approval (customize these)
SAFE_PATTERNS = {
    "Read": {
        # Auto-approve reading documentation and config
        "extensions": [".md", ".txt", ".json", ".yaml", ".yml", ".toml"],
        "paths": ["docs/", "README", ".claude/"],
    },
    "Write": {
        # Auto-approve writing to specific directories
        "paths": ["test/", "tests/", "__tests__/", "tmp/", ".claude/hooks/"],
        "extensions": [".test.ts", ".test.js", ".spec.ts", ".spec.js"],
    },
    "Edit": {
        # Auto-approve editing test files
        "extensions": [".test.ts", ".test.js", ".spec.ts", ".spec.js"],
    },
    "Bash": {
        # Auto-approve safe commands
        "commands": [
            r"^(npm|yarn|pnpm)\s+(run|test|build|lint)",
            r"^git\s+(status|log|diff|branch)",
            r"^ls\b",
            r"^cat\b.*\.(md|txt|json)$",
            r"^echo\b",
            r"^pwd$",
        ],
    },
}


def should_auto_approve(tool_name: str, tool_input: dict) -> tuple[bool, str]:
    """
    Check if operation should be auto-approved.
    Returns (should_approve, reason).
    """
    patterns = SAFE_PATTERNS.get(tool_name, {})

    if tool_name in ["Read", "Write", "Edit"]:
        file_path = tool_input.get("file_path", "")

        # Check extensions
        for ext in patterns.get("extensions", []):
            if file_path.endswith(ext):
                return True, f"Safe file type: {ext}"

        # Check paths
        for path in patterns.get("paths", []):
            if path in file_path:
                return True, f"Safe path: {path}"

    if tool_name == "Bash":
        command = tool_input.get("command", "")

        for pattern in patterns.get("commands", []):
            if re.match(pattern, command):
                return True, f"Safe command pattern"

    return False, ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    should_approve, reason = should_auto_approve(tool_name, tool_input)

    if should_approve:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            },
            "suppressOutput": True,  # Don't clutter verbose output
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
