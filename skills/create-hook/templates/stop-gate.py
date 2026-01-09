#!/usr/bin/env python3
"""
Template: Stop gate hook
Event: Stop or SubagentStop
Purpose: Ensure Claude completes required steps before stopping

Usage: Copy to .claude/hooks/ and customize check_completion()
"""

import json
import os
import subprocess
import sys


def check_completion(transcript_path: str, stop_hook_active: bool) -> tuple[bool, str]:
    """
    Check if Claude should be allowed to stop.
    Returns (can_stop, reason_to_continue).

    Customize this function for your workflow requirements.
    """
    # IMPORTANT: Prevent infinite loops
    # If we already forced Claude to continue once, let it stop now
    if stop_hook_active:
        return True, ""

    # Example checks (customize these):

    # 1. Check if tests were run
    # Look for test commands in recent transcript
    # (In real implementation, you'd parse transcript_path)

    # 2. Check for uncommitted changes
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if status:
            return False, (
                "You have uncommitted changes. Please commit your work:\n"
                f"Files changed: {len(status.split(chr(10)))}\n"
                "Run: git add . && git commit -m 'your message'"
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 3. Check for lint errors (example for JS/TS projects)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    package_json = os.path.join(project_dir, "package.json")

    if os.path.exists(package_json):
        try:
            result = subprocess.run(
                ["npm", "run", "lint", "--", "--quiet"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return False, (
                    "Lint errors detected. Please fix them before finishing:\n"
                    f"{result.stderr[:500] if result.stderr else result.stdout[:500]}"
                )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # 4. Check for TODO comments in modified files
    try:
        diff_files = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip().split("\n")

        for file in diff_files:
            if not file or not os.path.exists(file):
                continue
            try:
                with open(file) as f:
                    for i, line in enumerate(f, 1):
                        if "TODO" in line and "# TODO:" not in line:
                            return False, (
                                f"Found TODO in {file}:{i}\n"
                                f"Please address before finishing:\n"
                                f"  {line.strip()}"
                            )
            except (IOError, UnicodeDecodeError):
                pass
    except subprocess.CalledProcessError:
        pass

    return True, ""


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = input_data.get("transcript_path", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    can_stop, reason = check_completion(transcript_path, stop_hook_active)

    if not can_stop:
        # Block stopping and tell Claude what to do
        output = {
            "decision": "block",
            "reason": reason,
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
