#!/usr/bin/env python3
"""
mine-candidates.py - find hook candidates in past Claude Code and Codex sessions.

Usage:
    python3 mine-candidates.py [--project DIR | --all] [--days N] [--runtime claude|codex|both]
                               [--top N] [--json]

Reads session transcripts (~/.claude/projects/*/*.jsonl, ~/.codex/sessions/**/rollout-*.jsonl)
and groups the moments where a human or a gate stopped the agent:

    rejected     the human refused a tool call at the permission prompt
    interrupted  the human interrupted while a tool call was in flight
    corrected    the human's next message pushed back ("no", "don't", "stop", "you forgot")
    classifier   Claude auto mode's classifier denied the call
    hook         an existing hook blocked the call (repeats mean the agent keeps trying)
    saved        "always allow" approvals already saved in .claude/settings.local.json

Each group is keyed by the action involved ("Bash git push", "Edit *.env") with a count,
the number of distinct sessions, and sample locations. Open a sample with
`cass expand PATH --line N` when cass is installed, or read the line from the file.
Standard library only.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

CORRECTION = re.compile(
    r"^\s*(no\b|nope\b|don'?t\b|do not\b|stop\b|wait\b|actually\b|never\b|undo\b|revert\b|"
    r"why (did|are|would) you\b|you (should|shouldn'?t|forgot|didn'?t|need to)\b|instead\b|"
    r"that'?s (wrong|not)\b|please (don'?t|stop|never)\b)",
    re.I,
)
REJECTED = ("The user doesn't want to proceed", "User rejected tool use",
            "rejected by user", "declined by user")
CLASSIFIER = re.compile(r"denied by the Claude Code auto mode classifier\. Reason: (\[[^\]]+\]|[^.]{0,60})")
HOOK_BLOCK = re.compile(r"((?:PreToolUse|PostToolUse|PermissionRequest|Stop)[:A-Za-z|]* hook[^:]*:\s*[^\n\"]{0,80}"
                        r"|Command blocked by PreToolUse hook:\s*[^\n\"]{0,80})")
NOT_HUMAN = ("<command-", "<local-command", "<system-reminder", "<user-prompt-submit-hook", "Caveat:",
             "Base directory for this skill", "This session is being continued", "<environment_context",
             "<user_instructions", "# AGENTS.md", "<turn_aborted", "<subagent", "[Request interrupted")
SETUP = {"cd", "export", "set", "source", ".", "pushd", "unset"}
TWO_WORD = {"git", "npm", "pnpm", "yarn", "bun", "npx", "cargo", "go", "pip", "pip3", "uv", "docker",
            "kubectl", "gh", "brew", "make", "python", "python3", "node", "railway", "vercel", "supabase"}
CODE_MODE_CMD = re.compile(r"exec_command\(\{\s*cmd:\s*\"((?:[^\"\\\\]|\\\\.)*)\"")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.M)


def action_key(tool: str, inp) -> str:
    """Collapse a tool call to a groupable label."""
    if tool in ("Bash", "exec_command", "shell", "local_shell", "unified_exec"):
        cmd = (inp.get("command") or inp.get("cmd") or "") if isinstance(inp, dict) else inp
        if isinstance(cmd, list):
            cmd = " ".join(cmd[2:] if cmd[:2] in (["bash", "-lc"], ["bash", "-c"], ["sh", "-c"]) else cmd)
        return "Bash " + command_head(str(cmd))
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = (inp.get("file_path") or inp.get("notebook_path") or "") if isinstance(inp, dict) else ""
        return "Edit " + path_glob(path)
    if tool == "apply_patch":
        text = (inp.get("command") or inp.get("input") or "") if isinstance(inp, dict) else str(inp)
        files = PATCH_FILE.findall(str(text))
        return "Edit " + (path_glob(files[0]) if files else "?")
    return tool


def command_head(cmd: str) -> str:
    # First line only (heredoc and -c bodies follow it); skip setup segments: `cd x && git push` -> git push
    for seg in re.split(r"&&|;|\|\|", first_line(cmd)):
        words = [w for w in seg.split() if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
        if words and words[0] not in SETUP:
            break
    if not words:
        return "?"
    head = os.path.basename(words[0])
    if head in TWO_WORD and len(words) > 1 and not words[1].startswith("-"):
        return f"{head} {words[1]}"
    return head


def first_line(cmd: str) -> str:
    return next((ln for ln in cmd.splitlines() if ln.strip() and not ln.lstrip().startswith("#")), "")


def path_glob(path: str) -> str:
    name = os.path.basename(path)
    if not name:
        return "?"
    if name.startswith(".") or "." not in name or name.endswith((".lock", "-lock.json")):
        return name
    return "*." + name.rsplit(".", 1)[1]


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(text_of(c.get("text") or c.get("content") or "") if isinstance(c, dict) else str(c)
                         for c in content)
    return ""


class Miner:
    def __init__(self, top: int):
        self.groups = defaultdict(lambda: defaultdict(lambda: {"count": 0, "sessions": set(), "samples": []}))
        self.top = top
        self.sessions = 0

    def add(self, kind, key, session, where, sample=""):
        g = self.groups[kind][key]
        g["count"] += 1
        g["sessions"].add(session)
        if len(g["samples"]) < 3:
            g["samples"].append({"at": where, "text": " ".join(sample.split())[:160]})

    def scan_text(self, text, last, session, where):
        """Classify a tool result that came back as an error against the gate patterns."""
        text = text.lstrip()
        if any(r in text[:300] for r in REJECTED):
            kind, key = "rejected", last
        elif m := CLASSIFIER.search(text[:400]):
            kind, key = "classifier", f"{last} {m.group(1)}"
        elif m := HOOK_BLOCK.match(text):
            kind, key = "hook", m.group(1)[:90]
        else:
            return None
        self.add(kind, key, session, where)
        return kind

    def claude_file(self, path: Path):
        self.sessions += 1
        last, session, rejected = "(no tool)", path.stem, False
        for n, line in enumerate(path.open(errors="replace"), 1):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            where = f"{path}:{n}"
            if rec.get("type") == "assistant" and isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        last = action_key(c.get("name", "?"), c.get("input") or {})
            elif rec.get("type") == "user":
                items = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
                for c in items:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_result":
                        rejected = False
                        if c.get("is_error"):
                            rejected = self.scan_text(text_of(c.get("content")), last, session, where) == "rejected"
                        continue
                    text = c.get("text") or ""
                    if text.startswith("[Request interrupted by user"):
                        if "tool use" in text and not rejected:
                            self.add("interrupted", last, session, where)
                    elif not rec.get("isMeta") and not text.startswith(NOT_HUMAN) and CORRECTION.match(text):
                        self.add("corrected", last, session, where, text)
                        last = "(no tool)"
                    elif text.strip() and not rec.get("isMeta") and not text.startswith(NOT_HUMAN):
                        last = "(no tool)"

    def codex_file(self, path: Path):
        self.sessions += 1
        last, session = "(no tool)", path.stem
        for n, line in enumerate(path.open(errors="replace"), 1):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            p = rec.get("payload") or {}
            kind, where = p.get("type"), f"{path}:{n}"
            if kind == "function_call":
                try:
                    args = json.loads(p.get("arguments") or "{}")
                except ValueError:
                    args = {}
                last = action_key(p.get("name", "?"), args)
            elif kind == "custom_tool_call":
                inner = CODE_MODE_CMD.search(str(p.get("input", "")))
                last = (action_key("exec_command", {"cmd": inner.group(1)}) if inner
                        else action_key(p.get("name", "?"), {"input": p.get("input", "")}))
            elif kind == "local_shell_call":
                last = action_key("local_shell", (p.get("action") or {}))
            elif kind in ("function_call_output", "custom_tool_call_output"):
                out = p.get("output")
                out = out if isinstance(out, str) else text_of(out)
                # Codex wraps results in a status preamble; gate messages follow it
                self.scan_text(re.sub(r"^(Script (completed|failed)|Exit code: \d+|Wall time[^\n]*|Output:)\s*", "",
                                      out.lstrip(), flags=re.M), last, session, where)
            elif kind == "turn_aborted" and rec.get("type") == "event_msg":
                self.add("interrupted", last, session, where)
            elif kind == "message" and p.get("role") == "user":
                text = text_of(p.get("content"))
                if text.startswith(NOT_HUMAN):
                    continue
                if CORRECTION.match(text):
                    self.add("corrected", last, session, where, text)
                last = "(no tool)"

    def saved_approvals(self, project: Path):
        f = project / ".claude" / "settings.local.json"
        try:
            allow = json.loads(f.read_text()).get("permissions", {}).get("allow", [])
        except (OSError, ValueError):
            return
        for rule in allow:
            self.add("saved", rule, "settings.local.json", str(f))

    def report(self):
        out = {}
        for kind, groups in self.groups.items():
            ranked = sorted(groups.items(), key=lambda kv: (-len(kv[1]["sessions"]), -kv[1]["count"]))
            out[kind] = [{"key": k, "count": g["count"], "sessions": len(g["sessions"]),
                          "samples": g["samples"]} for k, g in ranked[: self.top]]
        return out


SUGGEST = {
    "rejected": "PreToolUse guard on this action, or a permission deny rule if a prefix is enough",
    "interrupted": "PreToolUse guard (deny or ask) so the agent stops before you have to",
    "corrected": "the action key says where: a tool means a PreToolUse/PostToolUse hook, "
                 "(no tool) means a Stop gate or a CLAUDE.md / AGENTS.md rule",
    "classifier": "already caught in auto mode; a hook only if other modes or Codex need it",
    "hook": "the agent keeps hitting this hook: state the rule in CLAUDE.md / AGENTS.md so it stops trying",
    "saved": "each is an approval you gave; a pattern that needs repo state is a PermissionRequest hook",
}
ORDER = ["corrected", "rejected", "interrupted", "hook", "classifier", "saved"]


def spellings(project):
    """A session records the path it started in, symlinked or not (/var vs /private/var on macOS)."""
    return {str(project.absolute()), str(project.resolve())}


def claude_dirs(project):
    root = Path.home() / ".claude" / "projects"
    if project is None:
        return [d for d in root.glob("*") if d.is_dir()]
    slugs = {re.sub(r"[^A-Za-z0-9]", "-", p) for p in spellings(project)}
    return sorted({d for slug in slugs for d in root.glob(slug + "*") if d.is_dir()})


def codex_files(project, since):
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    for f in root.rglob("rollout-*.jsonl"):
        if f.stat().st_mtime < since:
            continue
        if project is not None:
            try:
                with f.open(errors="replace") as fh:
                    meta = json.loads(fh.readline()).get("payload") or {}
            except (OSError, ValueError):
                continue
            if not str(meta.get("cwd", "")).startswith(tuple(spellings(project))):
                continue
        yield f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="repo to mine (default: git root of the current directory)")
    ap.add_argument("--all", action="store_true", help="mine every project")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--runtime", choices=["claude", "codex", "both"], default="both")
    ap.add_argument("--top", type=int, default=8, help="groups per category")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    project = None
    if not a.all:
        raw = a.project or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                          text=True).stdout.strip() or os.getcwd()
        project = Path(raw).absolute()
    since = time.time() - a.days * 86400

    m = Miner(a.top)
    if a.runtime in ("claude", "both"):
        for d in claude_dirs(project):
            for f in d.glob("*.jsonl"):
                if f.stat().st_mtime >= since:
                    m.claude_file(f)
        if project is not None:
            m.saved_approvals(project)
    if a.runtime in ("codex", "both"):
        for f in codex_files(project, since):
            m.codex_file(f)

    rep = m.report()
    if a.json:
        json.dump({"project": str(project) if project else None, "days": a.days, "sessions": m.sessions,
                   "groups": rep}, sys.stdout, indent=2)
        print()
        return
    print(f"{m.sessions} sessions, last {a.days} days, {project or 'all projects'}\n")
    for kind in ORDER:
        if not rep.get(kind):
            continue
        print(f"== {kind}: {SUGGEST[kind]}")
        for g in rep[kind]:
            print(f"  {g['count']:>4}x {g['sessions']:>3} sess  {g['key']}")
            for s in g["samples"][:2 if kind == "corrected" else 1]:
                print(f"         {s['at']}" + (f"\n           \"{s['text']}\"" if s["text"] else ""))
        print()
    if not rep:
        print("No rejections, interrupts, corrections, or gate denials found.")


if __name__ == "__main__":
    main()
