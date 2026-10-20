#!/usr/bin/env python3
"""
validate-hooks.py - Inventory and lint every hook an agent will run in a project.

Covers both Claude Code and Codex.

Claude: ~/.claude/settings.json, DIR/.claude/settings.json, DIR/.claude/settings.local.json,
        plus frontmatter `hooks:` in DIR/.claude/skills/*/SKILL.md and agents/*.md (listed only).
Codex:  ~/.codex/hooks.json, ~/.codex/config.toml, DIR/.codex/hooks.json, DIR/.codex/config.toml
        (config.toml needs Python 3.11+ for tomllib).

Usage:
    python3 validate-hooks.py [--project DIR] [--runtime claude|codex|both] [--json]
    python3 validate-hooks.py --inventory

Exit code 1 if any ERROR finding, else 0.
"""

import argparse
import json
import os
import py_compile
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    tomllib = None

# --- Rule tables -------------------------------------------------------------

CLAUDE_EVENTS = set("""
SessionStart Setup InstructionsLoaded UserPromptSubmit UserPromptExpansion MessageDisplay
PreToolUse PermissionRequest PermissionDenied PostToolUse PostToolUseFailure PostToolBatch
Notification SubagentStart SubagentStop TaskCreated TaskCompleted Stop StopFailure
TeammateIdle ConfigChange CwdChanged DirectoryAdded FileChanged WorktreeCreate
WorktreeRemove PreCompact PostCompact PreModelSwitch PostModelSwitch Elicitation
ElicitationResult SessionEnd
""".split())

CODEX_EVENTS = set("""
SessionStart SessionEnd UserPromptSubmit PreToolUse PermissionRequest PostToolUse
PreCompact PostCompact SubagentStart SubagentStop Stop Interrupt
""".split())

# Claude events that accept prompt/agent handlers (PermissionRequest: prompt only).
CLAUDE_LLM_EVENTS = set("""
PreToolUse PostToolUse PostToolUseFailure PostToolBatch PermissionDenied Stop
SubagentStop TaskCreated TaskCompleted TeammateIdle UserPromptSubmit UserPromptExpansion
""".split())
CLAUDE_COMMAND_ONLY = {"SessionStart", "Setup"}  # command|mcp_tool only

NO_MATCHER = {
    "claude": set("""UserPromptSubmit PostToolBatch Stop TeammateIdle TaskCreated
                     TaskCompleted WorktreeCreate WorktreeRemove MessageDisplay CwdChanged""".split()),
    "codex": {"UserPromptSubmit", "Stop", "Interrupt"},
}

CLAUDE_IF_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure",
                    "PermissionRequest", "PermissionDenied"}
TIMEOUT_EVENTS = {"Stop", "SubagentStop", "PreToolUse", "PostToolUse"}
STOP_EVENTS = {"Stop", "SubagentStop"}
CLAUDE_ONLY_FIELDS = ["if", "args", "onFailure", "asyncRewake", "shell", "once"]
SCRIPT_EXTS = (".sh", ".py", ".js", ".ts", ".rb")

PROJECT_DIR_VAR = re.compile(r"\$\{?CLAUDE_PROJECT_DIR\}?")
QUOTE_VARS = re.compile(r"\$\{CLAUDE_PROJECT_DIR\}|\$\{?CLAUDE_PLUGIN_ROOT\}?")
GIT_TOPLEVEL = "$(git rev-parse --show-toplevel)"


class Report:
    def __init__(self):
        self.rows = []
        self.findings = []

    def add(self, level, message, location):
        finding = {"level": level, "message": message, "location": location}
        if finding not in self.findings:
            self.findings.append(finding)

    def has_errors(self):
        return any(f["level"] == "ERROR" for f in self.findings)


def short(path, project_dir):
    """Display a path relative to the project or ~."""
    for base, label in ((project_dir, ""), (Path.home(), "~/")):
        try:
            return label + str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def load_json(path, report, loc):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as e:
        report.add("ERROR", f"cannot parse JSON: {e}", loc)
        return None


def iter_handlers(data, report, loc):
    """Yield (event, matcher, index_path, handler) from a {"hooks": {...}} mapping."""
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        report.add("ERROR", "`hooks` must be an object keyed by event name", loc)
        return
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            report.add("ERROR", f"{event} must be a list of matcher groups", loc)
            continue
        for i, group in enumerate(groups):
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                report.add("ERROR", "matcher group needs a `hooks` list", f"{loc}:{event}[{i}]")
                continue
            for j, handler in enumerate(group["hooks"]):
                if not isinstance(handler, dict):
                    report.add("ERROR", "handler must be an object", f"{loc}:{event}[{i}].hooks[{j}]")
                    continue
                yield event, group.get("matcher"), f"{event}[{i}].hooks[{j}]", handler


def frontmatter_has_hooks(path):
    try:
        text = path.read_text()
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    return re.search(r"^hooks\s*:", block, re.M) is not None


def collect(project_dir, runtimes, report):
    """Return a list of entries: dicts with runtime, scope, file, event, matcher, handler, loc."""
    home = Path.home()
    entries = []

    def add_source(runtime, scope, path, data):
        name = short(path, project_dir)
        for event, matcher, idx, handler in iter_handlers(data, report, name):
            entries.append({"runtime": runtime, "scope": scope, "file": name, "path": path,
                            "event": event, "matcher": matcher, "handler": handler,
                            "loc": f"{name}:{idx}"})

    if "claude" in runtimes:
        for scope, path in (("user", home / ".claude/settings.json"),
                            ("project", project_dir / ".claude/settings.json"),
                            ("local", project_dir / ".claude/settings.local.json")):
            if path.is_file():
                data = load_json(path, report, short(path, project_dir))
                if data is not None:
                    add_source("claude", scope, path, data)
        fm_files = sorted((project_dir / ".claude/skills").glob("*/SKILL.md"))
        fm_files += sorted((project_dir / ".claude/agents").glob("*.md"))
        for path in fm_files:
            if frontmatter_has_hooks(path):
                report.rows.append(row("claude", "project", short(path, project_dir), "-", None,
                                       {"type": "frontmatter"}, "frontmatter hooks present"))

    if "codex" in runtimes:
        for scope, base in (("user", home / ".codex"), ("project", project_dir / ".codex")):
            path = base / "hooks.json"
            if path.is_file():
                name = short(path, project_dir)
                data = load_json(path, report, name)
                if isinstance(data, dict):
                    extra = sorted(set(data) - {"description", "hooks"})
                    if extra:
                        report.add("ERROR", f"top-level keys {extra} not allowed "
                                   "(only description, hooks)", name)
                    add_source("codex", scope, path, data)
            path = base / "config.toml"
            if path.is_file():
                name = short(path, project_dir)
                if tomllib is None:
                    report.rows.append(row("codex", scope, name, "-", None, {"type": "-"},
                                           "not parsed (needs Python 3.11)"))
                    report.add("WARN", "config.toml not parsed (needs Python 3.11 for tomllib)", name)
                    continue
                try:
                    data = tomllib.loads(path.read_text())
                except (OSError, ValueError) as e:
                    report.add("ERROR", f"cannot parse TOML: {e}", name)
                    continue
                if isinstance(data.get("hooks"), dict):
                    data["hooks"].pop("state", None)  # Codex trust store, not an event
                add_source("codex", scope, path, data)
    return entries


def target_of(handler):
    for key in ("command", "url", "prompt", "tool"):
        if handler.get(key):
            return str(handler[key])
    return ""


def row(runtime, scope, file, event, matcher, handler, target=None):
    text = (target if target is not None else target_of(handler)).replace("\n", " ")
    flags = []
    if handler.get("async"):
        flags.append("async")
    if "timeout" in handler:
        flags.append(f"timeout={handler['timeout']}")
    if "if" in handler:
        flags.append(f"if={handler['if']}")
    if "onFailure" in handler:
        flags.append(f"onFailure={handler['onFailure']}")
    return {"runtime": runtime, "scope": scope, "file": file, "event": event,
            "matcher": matcher if matcher not in (None, "") else "*",
            "type": handler.get("type", "?"),
            "target": text if len(text) <= 60 else text[:57] + "...",
            "flags": ",".join(flags)}


def print_inventory(rows):
    print("INVENTORY")
    if not rows:
        print("  No hooks found.")
        return
    cols = ["runtime", "scope", "file", "event", "matcher", "type", "target", "flags"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  " + "  ".join(c.upper().ljust(widths[c]) for c in cols))
    for r in rows:
        print("  " + "  ".join(str(r[c]).ljust(widths[c]) for c in cols))


def lint_entry(e, report):
    runtime, event, handler, loc = e["runtime"], e["event"], e["handler"], e["loc"]
    htype = handler.get("type")
    matcher = e["matcher"]

    valid = CLAUDE_EVENTS if runtime == "claude" else CODEX_EVENTS
    if event not in valid:
        report.add("ERROR", f"unknown {runtime} event '{event}'", loc)
        return

    # Handler type support
    if runtime == "claude":
        if htype not in ("command", "http", "mcp_tool", "prompt", "agent"):
            report.add("ERROR", f"unknown handler type '{htype}'", loc)
        elif event in CLAUDE_COMMAND_ONLY and htype not in ("command", "mcp_tool"):
            report.add("ERROR", f"{event} accepts only command|mcp_tool, not {htype}", loc)
        elif htype == "prompt" and event not in CLAUDE_LLM_EVENTS | {"PermissionRequest"}:
            report.add("ERROR", f"prompt handlers are not supported on {event}", loc)
        elif htype == "agent" and event not in CLAUDE_LLM_EVENTS:
            report.add("ERROR", f"agent handlers are not supported on {event}", loc)
    else:
        if htype in ("prompt", "agent"):
            report.add("WARN", f"Codex parses {htype} handlers but skips them", loc)
        elif htype == "http":
            report.add("ERROR", "Codex does not support http handlers", loc)
        elif htype not in ("command", "mcp_tool"):
            report.add("ERROR", f"unknown handler type '{htype}'", loc)

    # Matchers
    if matcher not in (None, "", "*") and event in NO_MATCHER[runtime]:
        report.add("WARN", f"matcher '{matcher}' is ignored on {event}", loc)
    if isinstance(matcher, str):
        parts = [p.strip("^$() ") for p in matcher.split("|")]
        if "MultiEdit" in matcher:
            report.add("WARN", "matcher contains MultiEdit (tool no longer exists)", loc)
        if "Task" in parts:
            report.add("WARN", "matcher 'Task': the Claude subagent tool is now 'Agent'", loc)

    # Claude-only fields and `if`
    if runtime == "codex":
        for field in CLAUDE_ONLY_FIELDS:
            if field == "args" and "args" in handler:
                report.add("ERROR", "Codex ignores `args`: the command runs with no arguments", loc)
            elif field in handler:
                report.add("WARN", f"Codex silently ignores Claude-only field `{field}`", loc)
    elif "if" in handler and event not in CLAUDE_IF_EVENTS:
        report.add("ERROR", f"`if` on {event} means the hook NEVER runs "
                   "(only tool events honor `if`)", loc)

    if htype != "command":
        return
    command = str(handler.get("command", ""))

    if "timeout" not in handler and not handler.get("async") and event in TIMEOUT_EVENTS:
        report.add("WARN", f"no timeout on {event}: default is 600s; a hung hook stalls the agent", loc)
    if runtime == "codex" and PROJECT_DIR_VAR.search(json.dumps(handler)):
        report.add("WARN", "$CLAUDE_PROJECT_DIR is unset in Codex; use "
                   f"\"{GIT_TOPLEVEL}\"", loc)
    if "args" not in handler:
        for m in QUOTE_VARS.finditer(command):
            if command[:m.start()].count('"') % 2 == 0:
                report.add("WARN", f"{m.group(0)} not wrapped in double quotes "
                           "(breaks on paths with spaces)", loc)
                break


def resolve_script(command, project_dir):
    """Return (path, invoked_directly) for the script a command runs, or (None, False)."""
    expanded = command.replace(GIT_TOPLEVEL, str(project_dir))
    expanded = PROJECT_DIR_VAR.sub(lambda _: str(project_dir), expanded)
    expanded = re.sub(r"\$\{?HOME\}?", lambda _: str(Path.home()), expanded)
    try:
        tokens = shlex.split(expanded)
    except ValueError:
        return None, False
    for i, tok in enumerate(tokens):
        if tok in ("&&", "||", ";", "|"):
            break
        path = Path(os.path.expanduser(tok))
        if not path.is_absolute():
            path = project_dir / path
        if tok.endswith(SCRIPT_EXTS) or ("/" in tok and path.is_file() and os.access(path, os.X_OK)):
            return path, i == 0
    return None, False


def check_syntax(path):
    """Return an error string, or None if syntax is fine (or not checkable)."""
    if path.suffix == ".sh":
        proc = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
        if proc.returncode:
            lines = proc.stderr.strip().splitlines() or ["bash -n failed"]
            return lines[0].replace(str(path) + ": ", "")
        return None
    if path.suffix == ".py":
        with tempfile.TemporaryDirectory() as tmp:
            try:
                py_compile.compile(str(path), cfile=os.path.join(tmp, "x.pyc"), doraise=True)
            except py_compile.PyCompileError as e:
                return str(e.msg).strip().splitlines()[-1]
    return None


EXIT1 = re.compile(r"\bexit\s+1\b|sys\.exit\(\s*1\s*\)|process\.exit\(\s*1\s*\)")
EXIT2 = re.compile(r"\bexit\s+2\b|sys\.exit\(\s*2\s*\)|process\.exit\(\s*2\s*\)")
BLOCK_WORDS = re.compile(r"\b(block|deny|denied|decision|tool_name|tool_input|permission)", re.I)
STDERR = re.compile(r">&2|/dev/stderr|sys\.stderr|hook_block|console\.error")
APPROVE = re.compile(r"""["']?decision["']?\s*:\s*["']approve["']""")
ASK = re.compile(r"""["']?permissionDecision["']?\s*:\s*\\?["']ask""")


def lint_script(e, project_dir, report):
    handler = e["handler"]
    if handler.get("type") != "command":
        return
    path, direct = resolve_script(str(handler.get("command", "")), project_dir)
    if path is None:
        return
    loc, name = e["loc"], short(path, project_dir)
    if not path.is_file():
        report.add("ERROR", f"script not found: {name}", loc)
        return
    if direct and not os.access(path, os.X_OK):
        report.add("ERROR", f"{name} is invoked directly but not executable (chmod +x)", loc)
    try:
        text = path.read_text(errors="replace")
    except OSError as err:
        report.add("ERROR", f"cannot read {name}: {err}", loc)
        return
    if direct and not text.startswith("#!"):
        report.add("WARN", f"{name} has no shebang line", loc)
    err = check_syntax(path)
    if err:
        report.add("ERROR", f"syntax error in {name}: {err}", loc)

    if EXIT1.search(text) and BLOCK_WORDS.search(text):
        report.add("WARN", f"{name}: exit 1 is non-blocking; use exit 2 or JSON", loc)
    if EXIT2.search(text) and not STDERR.search(text):
        report.add("WARN", f"{name}: exit 2 shows only stderr; stdout is discarded", loc)
    if e["event"] in STOP_EVENTS and not re.search(r"stop_hook_active|HOOK_STOP_ACTIVE", text):
        report.add("WARN", f"{name}: never checks stop_hook_active (loop risk; "
                   "Claude caps at 8 continuations)", loc)
    if APPROVE.search(text):
        report.add("WARN", f"{name}: \"decision\": \"approve\" is deprecated", loc)
    if e["runtime"] == "codex" and ASK.search(text) and "hook_ask" not in text:
        report.add("WARN", f"{name}: Codex rejects permissionDecision \"ask\"; the tool call "
                   "goes ahead (use hook_ask from lib/hook-io.sh, which falls back to deny)", loc)


def lint_global(entries, report):
    for f in dict.fromkeys(e["file"] for e in entries if e["runtime"] == "codex"):
        report.add("INFO", "Codex runs a new or edited hook only after it is trusted: "
                   "open /hooks in Codex and trust it", f)

    seen = {}
    for e in entries:
        if e["runtime"] != "claude":
            continue
        key = (e["event"], e["matcher"] or "", json.dumps(e["handler"], sort_keys=True))
        seen.setdefault(key, {})[e["file"]] = True
    for (event, _m, _h), files in seen.items():
        files = list(files)
        if len(files) > 1:
            report.add("INFO", f"identical {event} handler in {', '.join(files)} runs once",
                       files[0])


def main():
    parser = argparse.ArgumentParser(description="Inventory and lint Claude Code and Codex hooks.")
    parser.add_argument("--project", default=".", help="Project directory (default: cwd)")
    parser.add_argument("--runtime", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--inventory", action="store_true", help="Print only the inventory")
    args = parser.parse_args()

    project_dir = Path(args.project).expanduser().resolve()
    runtimes = ["claude", "codex"] if args.runtime == "both" else [args.runtime]
    report = Report()
    entries = collect(project_dir, runtimes, report)

    for e in entries:
        report.rows.append(row(e["runtime"], e["scope"], e["file"], e["event"],
                               e["matcher"], e["handler"]))
        if not args.inventory:
            lint_entry(e, report)
            lint_script(e, project_dir, report)
    if not args.inventory:
        lint_global(entries, report)

    if args.json:
        out = {"project": str(project_dir), "inventory": report.rows}
        if not args.inventory:
            out["findings"] = report.findings
        print(json.dumps(out, indent=2))
    else:
        print_inventory(report.rows)
        if not args.inventory:
            print("\nFINDINGS")
            if not report.findings:
                print("  None.")
            order = {"ERROR": 0, "WARN": 1, "INFO": 2}
            for f in sorted(report.findings, key=lambda f: order[f["level"]]):
                print(f"  {f['level']:<5} {f['location']}: {f['message']}")
            counts = {lvl: sum(f["level"] == lvl for f in report.findings) for lvl in order}
            print(f"\n{counts['ERROR']} error(s), {counts['WARN']} warning(s), {counts['INFO']} info")

    sys.exit(1 if report.has_errors() and not args.inventory else 0)


if __name__ == "__main__":
    main()
