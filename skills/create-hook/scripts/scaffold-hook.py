#!/usr/bin/env python3
"""
Scaffold a new Claude Code hook with proper structure.

Usage:
    python3 scaffold-hook.py <event> <name> [--lang=python|bash]

Examples:
    python3 scaffold-hook.py PreToolUse validate-bash
    python3 scaffold-hook.py SessionStart load-context --lang=bash
    python3 scaffold-hook.py Stop ensure-tests
"""

import argparse
import os
import stat
import sys
from datetime import datetime

PYTHON_TEMPLATE = '''#!/usr/bin/env python3
"""
{name} - {description}

Event: {event}
{matcher_line}Created: {date}
"""

import json
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {{e}}", file=sys.stderr)
        sys.exit(0)

    event = input_data.get("hook_event_name", "")
{event_specific_code}
    # TODO: Add your logic here

    sys.exit(0)


if __name__ == "__main__":
    main()
'''

BASH_TEMPLATE = '''#!/bin/bash
# {name} - {description}
#
# Event: {event}
# {matcher_line}Created: {date}

set -e

# Read JSON input from stdin
INPUT=$(cat)

# Parse JSON fields (requires python3)
parse_json() {{
    echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null || echo ""
}}

EVENT=$(parse_json "hook_event_name")
{event_specific_code}
# TODO: Add your logic here

exit 0
'''

EVENT_CODE = {
    "PreToolUse": {
        "python": '''    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_use_id = input_data.get("tool_use_id", "")

    # Example: Block dangerous commands
    # if tool_name == "Bash":
    #     command = tool_input.get("command", "")
    #     if "rm -rf" in command:
    #         print("Blocked: dangerous command", file=sys.stderr)
    #         sys.exit(2)
''',
        "bash": '''TOOL_NAME=$(parse_json "tool_name")

# Example: Block based on tool name
# if [ "$TOOL_NAME" = "Bash" ]; then
#     COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))")
#     if echo "$COMMAND" | grep -q "rm -rf"; then
#         echo "Blocked: dangerous command" >&2
#         exit 2
#     fi
# fi
''',
    },
    "PostToolUse": {
        "python": '''    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_response = input_data.get("tool_response", {})

    # Example: Provide feedback after tool execution
    # if tool_name == "Write":
    #     file_path = tool_input.get("file_path", "")
    #     # Run linter, provide feedback, etc.
''',
        "bash": '''TOOL_NAME=$(parse_json "tool_name")

# Example: Run linter after file writes
# if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
#     # npm run lint --quiet
#     echo "File written, consider running tests"
# fi
''',
    },
    "UserPromptSubmit": {
        "python": '''    prompt = input_data.get("prompt", "")

    # Example: Inject context or validate prompts
    # if "deploy" in prompt.lower():
    #     print("Reminder: Run tests before deploying")
''',
        "bash": '''PROMPT=$(parse_json "prompt")

# Example: Add context to conversation
# echo "Current time: $(date)"
''',
    },
    "Stop": {
        "python": '''    stop_hook_active = input_data.get("stop_hook_active", False)
    transcript_path = input_data.get("transcript_path", "")

    # IMPORTANT: Prevent infinite loops
    if stop_hook_active:
        sys.exit(0)  # Already continuing from previous stop hook

    # Example: Ensure tests were run before stopping
    # import subprocess
    # result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    # if result.stdout.strip():
    #     print(json.dumps({
    #         "decision": "block",
    #         "reason": "You have uncommitted changes. Please commit or stash them."
    #     }))
''',
        "bash": '''STOP_ACTIVE=$(parse_json "stop_hook_active")

# IMPORTANT: Prevent infinite loops
if [ "$STOP_ACTIVE" = "True" ] || [ "$STOP_ACTIVE" = "true" ]; then
    exit 0
fi

# Example: Check for uncommitted changes
# if [ -n "$(git status --porcelain)" ]; then
#     echo '{"decision": "block", "reason": "Uncommitted changes detected"}'
# fi
''',
    },
    "SessionStart": {
        "python": '''    source = input_data.get("source", "")  # startup, resume, clear, compact

    # Example: Load project context
    # import subprocess
    # git_status = subprocess.check_output(["git", "status", "--short"], text=True)
    # print(f"Git status:\\n{git_status}")

    # Example: Persist environment variables (only for SessionStart)
    # env_file = os.environ.get("CLAUDE_ENV_FILE")
    # if env_file:
    #     with open(env_file, "a") as f:
    #         f.write("export MY_VAR=value\\n")
''',
        "bash": '''SOURCE=$(parse_json "source")  # startup, resume, clear, compact

# Example: Show project status
# echo "Project: $(basename $(pwd))"
# echo "Branch: $(git branch --show-current 2>/dev/null || echo 'not a git repo')"

# Example: Persist environment variables
# if [ -n "$CLAUDE_ENV_FILE" ]; then
#     echo 'export MY_VAR=value' >> "$CLAUDE_ENV_FILE"
# fi
''',
    },
    "SessionEnd": {
        "python": '''    reason = input_data.get("reason", "")  # clear, logout, prompt_input_exit, other

    # Example: Cleanup or logging
    # with open(os.path.expanduser("~/.claude/session.log"), "a") as f:
    #     f.write(f"Session ended: {reason}\\n")
''',
        "bash": '''REASON=$(parse_json "reason")  # clear, logout, prompt_input_exit, other

# Example: Log session end
# echo "Session ended: $REASON" >> ~/.claude/session.log
''',
    },
    "Notification": {
        "python": '''    message = input_data.get("message", "")
    notification_type = input_data.get("notification_type", "")  # permission_prompt, idle_prompt, etc.

    # Example: Forward to system notifications
    # import subprocess
    # if notification_type == "idle_prompt":
    #     subprocess.run(["osascript", "-e", f'display notification "{message}" with title "Claude Code"'])
''',
        "bash": '''MESSAGE=$(parse_json "message")
TYPE=$(parse_json "notification_type")  # permission_prompt, idle_prompt, etc.

# Example: macOS notification
# if [ "$TYPE" = "idle_prompt" ]; then
#     osascript -e "display notification \\"$MESSAGE\\" with title \\"Claude Code\\""
# fi
''',
    },
}


def get_matcher_events():
    """Events that support matchers."""
    return ["PreToolUse", "PostToolUse", "PermissionRequest", "SessionStart", "PreCompact", "Notification"]


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new Claude Code hook")
    parser.add_argument("event", help="Hook event type (PreToolUse, PostToolUse, Stop, etc.)")
    parser.add_argument("name", help="Hook name (e.g., validate-bash)")
    parser.add_argument("--lang", choices=["python", "bash"], default="python", help="Script language")
    parser.add_argument("--description", default="TODO: Add description", help="Hook description")
    parser.add_argument("--output", help="Output directory (default: .claude/hooks)")

    args = parser.parse_args()

    # Validate event type
    valid_events = [
        "PreToolUse", "PostToolUse", "PermissionRequest",
        "UserPromptSubmit", "Stop", "SubagentStop",
        "SessionStart", "SessionEnd", "PreCompact", "Notification"
    ]
    if args.event not in valid_events:
        print(f"Error: Invalid event '{args.event}'", file=sys.stderr)
        print(f"Valid events: {', '.join(valid_events)}", file=sys.stderr)
        sys.exit(1)

    # Generate matcher line
    matcher_line = ""
    if args.event in get_matcher_events():
        matcher_line = "Matcher: TODO (e.g., Write|Edit, Bash, *)\n"

    # Get event-specific code
    event_code = EVENT_CODE.get(args.event, {}).get(args.lang, "")
    if not event_code:
        event_code = "    # Event-specific code goes here\n" if args.lang == "python" else "# Event-specific code goes here\n"

    # Select template
    template = PYTHON_TEMPLATE if args.lang == "python" else BASH_TEMPLATE

    # Generate content
    content = template.format(
        name=args.name,
        description=args.description,
        event=args.event,
        matcher_line=matcher_line,
        date=datetime.now().strftime("%Y-%m-%d"),
        event_specific_code=event_code,
    )

    # Determine output path
    ext = ".py" if args.lang == "python" else ".sh"
    output_dir = args.output or ".claude/hooks"
    output_path = os.path.join(output_dir, f"{args.name}{ext}")

    # Create directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Check if file exists
    if os.path.exists(output_path):
        print(f"Error: File already exists: {output_path}", file=sys.stderr)
        sys.exit(1)

    # Write file
    with open(output_path, "w") as f:
        f.write(content)

    # Make executable
    os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Created: {output_path}")
    print()
    print("Next steps:")
    print(f"1. Edit {output_path} to add your logic")
    print("2. Add to .claude/settings.json:")
    print()

    # Generate settings snippet
    settings_matcher = '"Write|Edit"' if args.event in get_matcher_events() else ""
    if settings_matcher:
        print(f'''{{
  "hooks": {{
    "{args.event}": [
      {{
        "matcher": {settings_matcher},
        "hooks": [
          {{
            "type": "command",
            "command": "{'python3' if args.lang == 'python' else 'bash'} \\"$CLAUDE_PROJECT_DIR\\"/{output_path}"
          }}
        ]
      }}
    ]
  }}
}}''')
    else:
        print(f'''{{
  "hooks": {{
    "{args.event}": [
      {{
        "hooks": [
          {{
            "type": "command",
            "command": "{'python3' if args.lang == 'python' else 'bash'} \\"$CLAUDE_PROJECT_DIR\\"/{output_path}"
          }}
        ]
      }}
    ]
  }}
}}''')


if __name__ == "__main__":
    main()
