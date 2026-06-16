#!/usr/bin/env python3
"""
Template: Context injection hook
Event: SessionStart or UserPromptSubmit
Purpose: Add useful context at session start or per-prompt

Usage: Copy to .claude/hooks/ and customize get_context()
"""

import json
import os
import subprocess
import sys
from datetime import datetime


def get_session_context() -> str:
    """
    Generate context for SessionStart.
    Called once when Claude Code starts.
    """
    lines = []

    # Add current date/time
    now = datetime.now()
    lines.append(f"Session started: {now.strftime('%Y-%m-%d %H:%M')}")

    # Add git status if in a repo
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        lines.append(f"Git branch: {branch}")

        # Get recent commits
        commits = subprocess.check_output(
            ["git", "log", "--oneline", "-3"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if commits:
            lines.append(f"Recent commits:\n{commits}")

        # Check for uncommitted changes
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if status:
            change_count = len(status.split("\n"))
            lines.append(f"Uncommitted changes: {change_count} files")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Add custom project info
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    # Check for common files
    indicators = {
        "package.json": "Node.js project",
        "Cargo.toml": "Rust project",
        "pyproject.toml": "Python project",
        "go.mod": "Go project",
        "Gemfile": "Ruby project",
    }
    for file, description in indicators.items():
        if os.path.exists(os.path.join(project_dir, file)):
            lines.append(f"Project type: {description}")
            break

    return "\n".join(lines)


def get_prompt_context(prompt: str) -> str:
    """
    Generate context for UserPromptSubmit.
    Called on every user message.
    """
    lines = []

    # Add timestamp for each prompt
    now = datetime.now()
    lines.append(f"[{now.strftime('%H:%M')}]")

    # Add context based on prompt content
    # (customize this for your needs)

    return "\n".join(lines) if lines else ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    event = input_data.get("hook_event_name", "")

    if event == "SessionStart":
        context = get_session_context()
        if context:
            # Method 1: Plain stdout (simpler)
            print(context)

            # Method 2: JSON (more control)
            # output = {
            #     "hookSpecificOutput": {
            #         "hookEventName": "SessionStart",
            #         "additionalContext": context
            #     }
            # }
            # print(json.dumps(output))

    elif event == "UserPromptSubmit":
        prompt = input_data.get("prompt", "")
        context = get_prompt_context(prompt)
        if context:
            print(context)

    sys.exit(0)


if __name__ == "__main__":
    main()
