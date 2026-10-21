#!/usr/bin/env python3
"""
hook-log.py - View hook debug logs in a friendly format

Usage:
    python3 hook-log.py              # Show recent activity
    python3 hook-log.py --watch      # Live tail (like tail -f)
    python3 hook-log.py --errors     # Only show non-zero exit codes
    python3 hook-log.py --clear      # Clear the log file
    python3 hook-log.py --path       # Just print the log file path

Requires: Hooks wrapped with debug-wrap.sh
"""

import argparse
import os
import sys
import time
from pathlib import Path


def get_log_path():
    """Find the debug log file."""
    # Check current project first
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    log_path = Path(project_dir) / ".claude" / "hooks" / ".debug.log"
    return log_path


def parse_line(line):
    """Parse a log line into components."""
    line = line.strip()
    if not line:
        return None

    parts = line.split(" ", 3)
    if len(parts) < 3:
        return None

    timestamp = parts[0]
    exit_part = parts[1] if parts[1].startswith("exit=") else None
    if not exit_part:
        return None

    exit_code = int(exit_part.split("=")[1])
    hook_name = " ".join(parts[2:])

    return {
        "time": timestamp,
        "exit": exit_code,
        "hook": hook_name,
    }


def format_entry(entry):
    """Format a log entry for display."""
    if entry["exit"] == 0:
        icon = "\033[32m✓\033[0m"  # green checkmark
    elif entry["exit"] == 2:
        icon = "\033[31m✗\033[0m"  # red X (blocked)
    else:
        icon = "\033[33m!\033[0m"  # yellow warning

    exit_str = f"exit={entry['exit']}" if entry["exit"] != 0 else ""
    return f"{entry['time']}  {icon}  {entry['hook']:<40} {exit_str}"


def show_logs(log_path, errors_only=False, limit=50):
    """Display recent log entries."""
    if not log_path.exists():
        print(f"No debug log found at: {log_path}")
        print()
        print("To enable hook debugging:")
        print("1. Copy debug-wrap.sh to your .claude/hooks/ directory")
        print("2. Wrap your hook commands in settings.json:")
        print('   "command": ".claude/hooks/debug-wrap.sh python3 .claude/hooks/my-hook.py"')
        return

    lines = log_path.read_text().strip().split("\n")
    entries = [parse_line(line) for line in lines if line.strip()]
    entries = [e for e in entries if e is not None]

    if errors_only:
        entries = [e for e in entries if e["exit"] != 0]

    # Show last N entries
    entries = entries[-limit:]

    if not entries:
        print("No hook activity recorded yet." if not errors_only else "No errors recorded.")
        return

    print(f"\033[1mHOOK ACTIVITY\033[0m ({log_path})")
    print("-" * 60)

    for entry in entries:
        print(format_entry(entry))

    print("-" * 60)

    # Summary
    total = len(entries)
    blocked = sum(1 for e in entries if e["exit"] == 2)
    errors = sum(1 for e in entries if e["exit"] == 1)

    summary = f"{total} invocations"
    if blocked:
        summary += f", \033[31m{blocked} blocked\033[0m"
    if errors:
        summary += f", \033[33m{errors} errors\033[0m"

    print(summary)
    print()
    print("\033[2mTip: If a hook isn't appearing here, check that it's wrapped with debug-wrap.sh\033[0m")


def watch_logs(log_path):
    """Live tail the log file."""
    print(f"Watching {log_path} (Ctrl+C to stop)")
    print("-" * 60)

    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch()

    # Get initial file size
    last_size = log_path.stat().st_size

    try:
        while True:
            current_size = log_path.stat().st_size
            if current_size > last_size:
                with open(log_path) as f:
                    f.seek(last_size)
                    new_content = f.read()
                    for line in new_content.strip().split("\n"):
                        entry = parse_line(line)
                        if entry:
                            print(format_entry(entry))
                last_size = current_size
            elif current_size < last_size:
                # File was truncated/cleared
                last_size = 0
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")


def clear_logs(log_path):
    """Clear the log file."""
    if log_path.exists():
        log_path.write_text("")
        print(f"Cleared: {log_path}")
    else:
        print("No log file to clear.")


def main():
    parser = argparse.ArgumentParser(description="View hook debug logs")
    parser.add_argument("--watch", "-w", action="store_true", help="Live tail the log")
    parser.add_argument("--errors", "-e", action="store_true", help="Only show errors")
    parser.add_argument("--clear", "-c", action="store_true", help="Clear the log file")
    parser.add_argument("--path", "-p", action="store_true", help="Print log file path")
    parser.add_argument("--limit", "-n", type=int, default=50, help="Number of entries to show")

    args = parser.parse_args()
    log_path = get_log_path()

    if args.path:
        print(log_path)
    elif args.clear:
        clear_logs(log_path)
    elif args.watch:
        watch_logs(log_path)
    else:
        show_logs(log_path, errors_only=args.errors, limit=args.limit)


if __name__ == "__main__":
    main()
