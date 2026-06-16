#!/usr/bin/env python3
"""
validate-hook.py - Validate Claude Code hooks are correctly configured

This linter ensures hooks are properly installed and will run when Claude restarts.

Checks:
1. Hook script exists and is executable
2. Has valid shebang (#!/usr/bin/env python3 or #!/bin/bash)
3. No syntax errors (Python AST or bash -n)
4. Handles JSON input from stdin
5. Returns valid exit codes (0, 1, or 2)
6. Settings.json references the hook correctly
7. Reports installation level (project/user/local)

Installation Levels:
- PROJECT: .claude/settings.json - runs only in this project
- LOCAL:   .claude/settings.local.json - project-level, gitignored
- USER:    ~/.claude/settings.json - runs in ALL projects

Usage:
    # Validate a specific hook (checks script + where it's registered)
    python3 validate-hook.py .claude/hooks/my-hook.py

    # Validate all hooks in project
    python3 validate-hook.py --all

    # Validate settings.json configuration
    python3 validate-hook.py --settings

    # Full project validation (settings + all hooks + installation report)
    python3 validate-hook.py --project

Exit codes:
    0 - All validations passed
    1 - Validation errors found
    2 - Fatal error (missing files, etc.)
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class InstallationInfo:
    """Tracks where a hook is registered."""
    project: bool = False
    local: bool = False
    user: bool = False
    events: list[str] = field(default_factory=list)
    matchers: list[str] = field(default_factory=list)

    @property
    def is_installed(self) -> bool:
        return self.project or self.local or self.user

    def level_description(self) -> str:
        levels = []
        if self.project:
            levels.append("PROJECT (.claude/settings.json)")
        if self.local:
            levels.append("LOCAL (.claude/settings.local.json)")
        if self.user:
            levels.append("USER (~/.claude/settings.json)")
        return ", ".join(levels) if levels else "NOT INSTALLED"

    def scope_description(self) -> str:
        if self.user:
            return "Will run in ALL projects"
        elif self.project or self.local:
            return "Will run in THIS project only"
        return "Will NOT run (not registered in any settings file)"


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []
        self.installation: Optional[InstallationInfo] = None

    def error(self, msg: str):
        self.errors.append(f"❌ {msg}")

    def warn(self, msg: str):
        self.warnings.append(f"⚠️  {msg}")

    def ok(self, msg: str):
        self.passed.append(f"✓ {msg}")

    def info(self, msg: str):
        self.passed.append(f"ℹ️  {msg}")

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def print_report(self, title: str):
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)

        for msg in self.passed:
            print(f"  {msg}")
        for msg in self.warnings:
            print(f"  {msg}")
        for msg in self.errors:
            print(f"  {msg}")

        # Print installation status if available
        if self.installation:
            print()
            print("  📍 INSTALLATION STATUS:")
            if self.installation.project:
                print("  ✓ Registered in PROJECT settings (.claude/settings.json)")
            else:
                print("  ✗ Not in project settings (.claude/settings.json)")

            if self.installation.local:
                print("  ✓ Registered in LOCAL settings (.claude/settings.local.json)")
            else:
                print("  ✗ Not in local settings (.claude/settings.local.json)")

            if self.installation.user:
                print("  ✓ Registered in USER settings (~/.claude/settings.json)")
            else:
                print("  ✗ Not in user settings (~/.claude/settings.json)")

            print()
            if self.installation.is_installed:
                print(f"  ⚡ {self.installation.scope_description()}")
                if self.installation.events:
                    events_str = ", ".join(sorted(set(self.installation.events)))
                    print(f"  🎯 Events: {events_str}")
                if self.installation.matchers:
                    matchers_str = ", ".join(sorted(set(self.installation.matchers)))
                    print(f"  🔍 Matchers: {matchers_str}")
            else:
                print("  ⚠️  Hook script exists but is NOT registered in any settings file!")
                print("     It will NOT run until added to settings.json")

        print()
        if self.success:
            if self.installation and not self.installation.is_installed:
                print(f"  ⚠️  SCRIPT VALID but NOT INSTALLED ({len(self.passed)} checks passed)")
            else:
                print(f"  ✅ PASSED ({len(self.passed)} checks, {len(self.warnings)} warnings)")
        else:
            print(f"  ❌ FAILED ({len(self.errors)} errors, {len(self.warnings)} warnings)")
        print()


# Event schemas - what fields each event provides
EVENT_SCHEMAS = {
    "PreToolUse": {
        "required": ["tool_name", "tool_input"],
        "optional": ["tool_use_id", "session_id"],
        "has_matcher": True,
        "can_block": True,
    },
    "PostToolUse": {
        "required": ["tool_name", "tool_input", "tool_response"],
        "optional": ["tool_use_id", "session_id"],
        "has_matcher": True,
        "can_block": False,
    },
    "UserPromptSubmit": {
        "required": ["prompt"],
        "optional": ["session_id"],
        "has_matcher": False,
        "can_block": True,
    },
    "Stop": {
        "required": ["stop_hook_active"],
        "optional": ["transcript_path", "session_id"],
        "has_matcher": False,
        "can_block": True,
    },
    "SubagentStop": {
        "required": ["stop_hook_active"],
        "optional": ["transcript_path", "session_id"],
        "has_matcher": False,
        "can_block": True,
    },
    "SessionStart": {
        "required": ["source"],
        "optional": ["session_id"],
        "has_matcher": True,
        "can_block": False,
    },
    "SessionEnd": {
        "required": ["reason"],
        "optional": ["session_id"],
        "has_matcher": False,
        "can_block": False,
    },
    "PermissionRequest": {
        "required": ["tool_name", "tool_input"],
        "optional": ["tool_use_id", "session_id"],
        "has_matcher": True,
        "can_block": True,
    },
    "PreCompact": {
        "required": [],
        "optional": ["session_id"],
        "has_matcher": True,
        "can_block": False,
    },
    "Notification": {
        "required": ["message", "notification_type"],
        "optional": ["session_id"],
        "has_matcher": True,
        "can_block": False,
    },
}

# Test inputs for each event type
TEST_INPUTS = {
    "PreToolUse": {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/test.txt", "content": "test"},
        "tool_use_id": "test-123",
        "session_id": "session-abc",
    },
    "PostToolUse": {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/test.txt", "content": "test"},
        "tool_response": {"success": True},
        "tool_use_id": "test-123",
        "session_id": "session-abc",
    },
    "UserPromptSubmit": {
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Hello, world!",
        "session_id": "session-abc",
    },
    "Stop": {
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "transcript_path": "/tmp/transcript.json",
        "session_id": "session-abc",
    },
    "SubagentStop": {
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "transcript_path": "/tmp/transcript.json",
        "session_id": "session-abc",
    },
    "SessionStart": {
        "hook_event_name": "SessionStart",
        "source": "startup",
        "session_id": "session-abc",
    },
    "SessionEnd": {
        "hook_event_name": "SessionEnd",
        "reason": "logout",
        "session_id": "session-abc",
    },
    "PermissionRequest": {
        "hook_event_name": "PermissionRequest",
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
        "tool_use_id": "test-123",
        "session_id": "session-abc",
    },
    "PreCompact": {
        "hook_event_name": "PreCompact",
        "session_id": "session-abc",
    },
    "Notification": {
        "hook_event_name": "Notification",
        "message": "Test notification",
        "notification_type": "idle_prompt",
        "session_id": "session-abc",
    },
}


def get_settings_paths(project_dir: Path) -> dict[str, Path]:
    """Get all possible settings file paths."""
    return {
        "project": project_dir / ".claude" / "settings.json",
        "local": project_dir / ".claude" / "settings.local.json",
        "user": Path.home() / ".claude" / "settings.json",
    }


def find_hook_in_settings(settings_path: Path, hook_script: Path, project_dir: Path) -> tuple[bool, list[str], list[str]]:
    """
    Check if a hook script is registered in a settings file.
    Returns (found, events, matchers).
    """
    if not settings_path.exists():
        return False, [], []

    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False, [], []

    hooks_config = settings.get("hooks", {})
    if not hooks_config:
        return False, [], []

    found = False
    events = []
    matchers = []

    # Normalize hook script path for comparison
    hook_name = hook_script.name
    hook_abs = hook_script.resolve()

    for event, configs in hooks_config.items():
        for config in configs:
            matcher = config.get("matcher", "*")
            hook_list = config.get("hooks", [])

            for hook in hook_list:
                if hook.get("type", "command") != "command":
                    continue

                command = hook.get("command", "")
                if not command:
                    continue

                # Expand $CLAUDE_PROJECT_DIR (handle both quoted and unquoted)
                expanded = command.replace('"$CLAUDE_PROJECT_DIR"', str(project_dir))
                expanded = expanded.replace("'$CLAUDE_PROJECT_DIR'", str(project_dir))
                expanded = expanded.replace("$CLAUDE_PROJECT_DIR", str(project_dir))

                # Check if this command references our hook by name
                if hook_name in expanded:
                    # Strip quotes and check each part
                    # Remove quotes for path comparison
                    clean_expanded = expanded.replace('"', '').replace("'", '')

                    for part in clean_expanded.split():
                        if hook_name in part:
                            # Try path resolution
                            try:
                                cmd_path = Path(part).resolve()
                                if cmd_path == hook_abs:
                                    found = True
                                    events.append(event)
                                    if matcher != "*":
                                        matchers.append(matcher)
                                    break
                            except (OSError, ValueError):
                                pass

                            # Fallback: string match on filename
                            if part.endswith(hook_name):
                                found = True
                                events.append(event)
                                if matcher != "*":
                                    matchers.append(matcher)
                                break

    return found, events, matchers


def check_installation_status(hook_script: Path, project_dir: Path) -> InstallationInfo:
    """Check where a hook is registered across all settings levels."""
    info = InstallationInfo()
    paths = get_settings_paths(project_dir)

    # Check each level
    found, events, matchers = find_hook_in_settings(paths["project"], hook_script, project_dir)
    if found:
        info.project = True
        info.events.extend(events)
        info.matchers.extend(matchers)

    found, events, matchers = find_hook_in_settings(paths["local"], hook_script, project_dir)
    if found:
        info.local = True
        info.events.extend(events)
        info.matchers.extend(matchers)

    found, events, matchers = find_hook_in_settings(paths["user"], hook_script, project_dir)
    if found:
        info.user = True
        info.events.extend(events)
        info.matchers.extend(matchers)

    return info


def detect_hook_event(script_path: Path, content: str) -> Optional[str]:
    """Try to detect which event this hook is for from its content."""
    # Check docstring/comments
    event_pattern = r'Event:\s*(\w+)'
    match = re.search(event_pattern, content)
    if match:
        event = match.group(1)
        if event in EVENT_SCHEMAS:
            return event

    # Check for event-specific field access
    if "stop_hook_active" in content:
        return "Stop"
    if "tool_response" in content:
        return "PostToolUse"
    if '"prompt"' in content or "prompt" in content:
        if "tool_name" not in content:
            return "UserPromptSubmit"
    if "notification_type" in content:
        return "Notification"
    if '"source"' in content and "startup" in content:
        return "SessionStart"
    if '"reason"' in content and "tool_name" not in content:
        return "SessionEnd"
    if "tool_name" in content:
        return "PreToolUse"  # Default for tool-related hooks

    return None


def validate_hook_script(script_path: Path, project_dir: Path, event_hint: Optional[str] = None) -> ValidationResult:
    """Validate a single hook script and check its installation status."""
    result = ValidationResult()

    # 1. Check file exists
    if not script_path.exists():
        result.error(f"Script not found: {script_path}")
        return result
    result.ok(f"Script exists: {script_path.name}")

    # 2. Check executable
    if not os.access(script_path, os.X_OK):
        result.error("Script is not executable (run: chmod +x)")
    else:
        result.ok("Script is executable")

    # 3. Read content
    try:
        content = script_path.read_text()
    except Exception as e:
        result.error(f"Cannot read script: {e}")
        return result

    # 4. Check shebang and determine language
    lines = content.split('\n')
    is_python = False
    is_bash = False

    if not lines or not lines[0].startswith('#!'):
        result.error("Missing shebang (should start with #!/usr/bin/env python3 or #!/bin/bash)")
    elif 'python' in lines[0]:
        result.ok("Valid Python shebang")
        is_python = True
    elif 'bash' in lines[0] or 'sh' in lines[0]:
        result.ok("Valid Bash shebang")
        is_bash = True
    else:
        result.warn(f"Unusual shebang: {lines[0]}")
        # Try to guess from extension
        if script_path.suffix == '.py':
            is_python = True
        elif script_path.suffix == '.sh':
            is_bash = True

    # 5. Syntax check
    if is_python:
        try:
            ast.parse(content)
            result.ok("Python syntax valid")
        except SyntaxError as e:
            result.error(f"Python syntax error: {e.msg} (line {e.lineno})")
            return result  # Can't continue with broken syntax
    elif is_bash:
        try:
            proc = subprocess.run(
                ['bash', '-n', str(script_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0:
                result.error(f"Bash syntax error: {proc.stderr.strip()}")
            else:
                result.ok("Bash syntax valid")
        except subprocess.TimeoutExpired:
            result.warn("Bash syntax check timed out")
        except FileNotFoundError:
            result.warn("Cannot check bash syntax (bash not found)")

    # 6. Check for JSON input handling
    if is_python:
        if 'json.load(sys.stdin)' in content or 'json.loads' in content:
            result.ok("Handles JSON input from stdin")
        else:
            result.warn("No json.load(sys.stdin) found - may not handle input correctly")
    elif is_bash:
        if 'cat' in content or 'INPUT=$(' in content or 'read' in content:
            result.ok("Reads input from stdin")
        else:
            result.warn("May not read input from stdin")

    # 7. Detect event type
    event = event_hint or detect_hook_event(script_path, content)
    if event:
        result.ok(f"Detected event type: {event}")

        # Check for infinite loop protection in Stop hooks
        if event in ["Stop", "SubagentStop"]:
            if "stop_hook_active" not in content:
                result.error("Stop hook missing stop_hook_active check (infinite loop risk!)")
            else:
                result.ok("Has stop_hook_active check (prevents infinite loops)")
    else:
        result.warn("Could not detect event type from script content")

    # 8. Check exit code usage
    if is_python:
        if 'sys.exit(2)' in content:
            result.ok("Uses exit(2) for blocking")
        if 'sys.exit(0)' in content:
            result.ok("Uses exit(0) for success")
        if 'sys.exit(1)' in content:
            result.warn("Uses exit(1) - non-blocking error (logged only)")
    elif is_bash:
        if 'exit 2' in content:
            result.ok("Uses exit 2 for blocking")
        if 'exit 0' in content:
            result.ok("Uses exit 0 for success")

    # 9. Runtime test with sample input
    if event and (is_python or is_bash):
        test_input = TEST_INPUTS.get(event, {"hook_event_name": "Unknown"})
        try:
            interpreter = 'python3' if is_python else 'bash'
            proc = subprocess.run(
                [interpreter, str(script_path)],
                input=json.dumps(test_input),
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )
            if proc.returncode in [0, 1, 2]:
                result.ok(f"Runtime test passed (exit code: {proc.returncode})")
                if proc.stdout.strip():
                    try:
                        json.loads(proc.stdout)
                        result.ok("Outputs valid JSON")
                    except json.JSONDecodeError:
                        # Non-JSON output is fine for some hooks
                        if len(proc.stdout) < 200:
                            result.ok(f"Outputs text: {proc.stdout.strip()[:50]}")
            else:
                result.error(f"Unexpected exit code: {proc.returncode}")
            if proc.stderr.strip() and proc.returncode != 2:
                result.warn(f"Stderr output: {proc.stderr.strip()[:100]}")
        except subprocess.TimeoutExpired:
            result.error("Script timed out (>10s) on test input")
        except Exception as e:
            result.error(f"Runtime test failed: {e}")

    # 10. Check installation status
    result.installation = check_installation_status(script_path, project_dir)

    return result


def validate_settings(settings_path: Path, project_dir: Path, level_name: str = "") -> ValidationResult:
    """Validate hooks configuration in a settings.json file."""
    result = ValidationResult()

    display_name = level_name or settings_path.name

    if not settings_path.exists():
        result.info(f"{display_name}: File not found (no hooks at this level)")
        return result

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError as e:
        result.error(f"Invalid JSON in {display_name}: {e}")
        return result

    result.ok(f"{display_name}: Valid JSON")

    hooks = settings.get("hooks", {})
    if not hooks:
        result.info(f"{display_name}: No hooks configured")
        return result

    result.ok(f"{display_name}: {len(hooks)} event type(s) configured")

    for event, configs in hooks.items():
        if event not in EVENT_SCHEMAS:
            result.error(f"Unknown event type: {event}")
            continue

        schema = EVENT_SCHEMAS[event]

        for i, config in enumerate(configs):
            # Check matcher usage
            if "matcher" in config and not schema["has_matcher"]:
                result.warn(f"{event}[{i}]: Matcher specified but {event} doesn't support matchers")

            hook_list = config.get("hooks", [])
            for j, hook in enumerate(hook_list):
                hook_type = hook.get("type", "command")

                if hook_type == "command":
                    command = hook.get("command", "")
                    if not command:
                        result.error(f"{event}[{i}].hooks[{j}]: Empty command")
                        continue

                    # Expand and check script path
                    expanded_cmd = command.replace("$CLAUDE_PROJECT_DIR", str(project_dir))
                    expanded_cmd = expanded_cmd.replace('"$CLAUDE_PROJECT_DIR"', str(project_dir))

                    # Try to find the script path in the command
                    script_path = None
                    for part in expanded_cmd.split():
                        if part.endswith('.py') or part.endswith('.sh'):
                            script_path = Path(part)
                            break

                    if script_path:
                        if script_path.exists():
                            result.ok(f"{event}: Script exists: {script_path.name}")
                            # Check if executable
                            if not os.access(script_path, os.X_OK):
                                result.error(f"{event}: Script not executable: {script_path.name}")
                        else:
                            result.error(f"{event}: Script not found: {script_path}")
                    else:
                        result.warn(f"{event}[{i}].hooks[{j}]: Could not identify script in command")

                elif hook_type == "prompt":
                    prompt = hook.get("prompt", "")
                    if not prompt:
                        result.error(f"{event}[{i}].hooks[{j}]: Empty prompt")
                    else:
                        result.ok(f"{event}: Prompt-based hook configured")
                        if not schema["can_block"]:
                            result.warn(f"{event}: Prompt hooks on {event} cannot block operations")

    return result


def find_all_hooks(project_dir: Path) -> list[Path]:
    """Find all hook scripts in the project."""
    hooks = []
    hooks_dir = project_dir / ".claude" / "hooks"

    if hooks_dir.exists():
        for f in hooks_dir.iterdir():
            if f.is_file() and (f.suffix in ['.py', '.sh'] or f.name.startswith('hook')):
                hooks.append(f)

    return hooks


def validate_project(project_dir: Path) -> bool:
    """Full project validation with installation status."""
    print(f"\n{'#'*60}")
    print(f"  HOOK VALIDATION: {project_dir}")
    print('#'*60)

    all_passed = True
    paths = get_settings_paths(project_dir)

    # Validate all settings files
    print("\n📁 SETTINGS FILES")
    print("-" * 40)

    for level, settings_path in paths.items():
        level_display = {
            "project": "PROJECT (.claude/settings.json)",
            "local": "LOCAL (.claude/settings.local.json)",
            "user": "USER (~/.claude/settings.json)"
        }[level]

        result = validate_settings(settings_path, project_dir, level_display)

        # Print condensed result
        if settings_path.exists():
            status = "✅" if result.success else "❌"
            print(f"  {status} {level_display}")
            for err in result.errors:
                print(f"      {err}")
        else:
            print(f"  ⚪ {level_display} (not found)")

        if not result.success:
            all_passed = False

    # Validate all hook scripts
    hooks = find_all_hooks(project_dir)

    if hooks:
        print(f"\n📜 HOOK SCRIPTS ({len(hooks)} found)")
        print("-" * 40)

        for hook in hooks:
            result = validate_hook_script(hook, project_dir)
            result.print_report(f"Hook: {hook.name}")
            if not result.success:
                all_passed = False
    else:
        print("\n📜 HOOK SCRIPTS")
        print("-" * 40)
        print("  No hook scripts found in .claude/hooks/")

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("  ✅ ALL VALIDATIONS PASSED")
        print("  Hooks are properly configured and will run when Claude starts.")
    else:
        print("  ❌ SOME VALIDATIONS FAILED")
        print("  Fix the errors above to ensure hooks work correctly.")
    print("=" * 60 + "\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Validate Claude Code hooks are properly installed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("script", nargs="?", help="Hook script to validate")
    parser.add_argument("--all", action="store_true", help="Validate all hooks in .claude/hooks/")
    parser.add_argument("--settings", action="store_true", help="Validate all settings files")
    parser.add_argument("--project", action="store_true", help="Full project validation")
    parser.add_argument("--event", help="Specify event type for the hook")
    parser.add_argument("--dir", default=".", help="Project directory (default: current)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    project_dir = Path(args.dir).resolve()

    if args.project or (not args.script and not args.all and not args.settings):
        success = validate_project(project_dir)
        sys.exit(0 if success else 1)

    if args.settings:
        paths = get_settings_paths(project_dir)
        all_passed = True

        for level, settings_path in paths.items():
            result = validate_settings(settings_path, project_dir, level.upper())
            result.print_report(f"Settings: {level.upper()}")
            if not result.success:
                all_passed = False

        sys.exit(0 if all_passed else 1)

    if args.all:
        hooks = find_all_hooks(project_dir)
        if not hooks:
            print("No hooks found in .claude/hooks/")
            sys.exit(0)

        all_passed = True
        for hook in hooks:
            result = validate_hook_script(hook, project_dir, args.event)
            result.print_report(f"Hook: {hook.name}")
            if not result.success:
                all_passed = False

        sys.exit(0 if all_passed else 1)

    if args.script:
        script_path = Path(args.script)
        if not script_path.is_absolute():
            script_path = project_dir / script_path

        result = validate_hook_script(script_path, project_dir, args.event)
        result.print_report(f"Hook: {script_path.name}")
        sys.exit(0 if result.success else 1)

    parser.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
