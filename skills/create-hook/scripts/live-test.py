#!/usr/bin/env python3
"""
live-test.py - prove a hook fires inside a real agent session, in a throwaway copy of the repo.

Usage:
    python3 live-test.py scratch --from REPO [--hooks-only] [--out DIR]
    python3 live-test.py run --dir SCRATCH --runtime claude|codex --hook SCRIPT --expect DECISION
                             (--command CMD | --prompt TEXT) [--herdr] [--model M] [--timeout SEC] [--json]

scratch   copies REPO's working tree (tracked and untracked, minus ignored files; --hooks-only
          copies just the hook config and scripts) into a new git repo whose origin is a local
          bare repo. A red case that slips through lands there, not on a real remote.
run       starts one agent session in SCRATCH with HOOK_TRACE set, asks it to do the thing,
          and reads the trace that hooks built on lib/hook-io.sh append:
              <runtime> <script> <event> <tool> <decision> exit=<code>
          It passes when a line for SCRIPT carries DECISION
          (pass | block | deny | ask | approve | context | continue).

Headless (default): `claude -p` with hook events in its stream, or `codex exec` with hook trust
bypassed for that invocation only. Decisions that need a human-facing UI (ask, PermissionRequest
approve, Notification) run interactively with --herdr: the agent starts in its own herdr workspace,
and the run also reports whether the agent ended blocked on a dialog.

Each run is one model call, seconds long and not fully deterministic. Use it for one red and one
green case per hook after test-hook.py passes, not for the whole fixture set.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOOK_PATHS = [".claude/settings.json", ".claude/settings.local.json", ".claude/hooks", ".codex/hooks.json",
              ".codex/config.toml", ".codex/hooks", ".agents/hooks"]


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def scratch(a):
    src = Path(a.src).resolve()
    out = Path(a.out or tempfile.mkdtemp(prefix=f"hook-live-{src.name}-"))
    repo = out / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    if a.hooks_only:
        files = [p for p in HOOK_PATHS if (src / p).exists()]
    else:
        files = sh("git", "-C", str(src), "ls-files", "-co", "--exclude-standard").stdout.splitlines()
        files += [p for p in HOOK_PATHS if (src / p).exists()]  # local settings are usually ignored
    for rel in dict.fromkeys(files):
        s, d = src / rel, repo / rel
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        elif s.is_file():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
    remote = out / "remote.git"
    sh("git", "init", "-q", "--bare", str(remote))
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                ["-c", "user.name=hook-test", "-c", "user.email=hook-test@localhost", "commit", "-qm", "scratch",
                 "--allow-empty"],
                ["remote", "add", "origin", str(remote)], ["push", "-q", "origin", "main"]):
        r = sh("git", "-C", str(repo), *cmd)
        if r.returncode:
            sys.exit(f"git {' '.join(cmd)} failed: {r.stderr.strip()}")
    print(repo)


def codex_home():
    """A throwaway CODEX_HOME: Codex saves a trust entry for every folder it runs in, and scratch folders
    shouldn't pile up in the user's config.toml. Auth is linked so token refreshes still land."""
    src = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    home = Path(tempfile.mkdtemp(prefix="hook-codex-home-"))
    if (src / "auth.json").exists():
        (home / "auth.json").symlink_to(src / "auth.json")
    if (src / "config.toml").exists():
        shutil.copy2(src / "config.toml", home / "config.toml")
    return home


def codex_args(a):
    """Workspace-write keeps .git read-only; open it and the scratch remote so git cases can run."""
    remote = sh("git", "-C", a.dir, "remote", "get-url", "origin").stdout.strip()
    roots = json.dumps([f"{a.dir}/.git"] + ([remote] if remote else []))
    args = ["--dangerously-bypass-hook-trust", "-c", f"sandbox_workspace_write.writable_roots={roots}"]
    if a.model:
        args += ["-m", a.model]
    if a.effort:
        args += ["-c", f"model_reasoning_effort={a.effort}"]
    return args


def headless(a, env):
    if a.runtime == "claude":
        cmd = ["claude", "-p", a.prompt, "--setting-sources", "project,local", "--permission-mode",
               "bypassPermissions", "--output-format", "stream-json", "--verbose", "--include-hook-events",
               "--max-turns", "4"] + (["--model", a.model] if a.model else [])
    else:
        cmd = ["codex", "exec", "--json", "--ephemeral", "-s", "workspace-write", *codex_args(a), "-C", a.dir,
               a.prompt]
    try:
        r = subprocess.run(cmd, cwd=a.dir, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=a.timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {a.timeout}s"}
    final, runtime_says = "", []
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            final = str(ev.get("result", ""))
        elif ev.get("subtype") == "hook_response" and ev.get("hook_event") not in ("SessionStart", "Stop"):
            out = str(ev.get("output") or ev.get("stdout") or "").strip()
            if out and out != "{}":
                runtime_says.append(f"{ev.get('hook_name')}: {out[:200]}")
        elif (ev.get("item") or {}).get("type") == "agent_message":
            final = ev["item"].get("text", "")
    runtime_says += [ln.split("error=", 1)[-1][:200] for ln in r.stderr.splitlines() if "hook" in ln.lower()
                     and "bypass-hook-trust" not in ln]
    return {"final": final.strip()[:600], "runtime": runtime_says, "exit": r.returncode}


def herdr(a, env):
    def h(*args):
        r = sh("herdr", *args)
        if r.returncode:
            raise RuntimeError(f"herdr {' '.join(args[:2])}: {r.stderr.strip() or r.stdout.strip()}")
        return json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}

    name = f"hooktest-{os.getpid()}"
    pass_env = [x for k in ("HOOK_TRACE", "CODEX_HOME") if k in env for x in ("--env", f"{k}={env[k]}")]
    ws = h("workspace", "create", "--cwd", a.dir, "--label", name, *pass_env, "--no-focus")["result"]
    pane = ws["root_pane"]["pane_id"]
    try:
        if a.runtime == "claude":
            args = ["--permission-mode", "default", "--name", name] + (["--model", a.model] if a.model else [])
        else:
            args = codex_args(a) + ["-c", "check_for_update_on_startup=false",
                                    "-c", f'projects."{a.dir}".trust_level="trusted"']
        start = sh("herdr", "agent", "start", name, "--kind", a.runtime, "--pane", pane, "--timeout", "60000",
                   "--", *args)
        if start.returncode:
            screen = sh("herdr", "pane", "read", pane, "--source", "visible").stdout
            if "agent_not_ready" in start.stdout + start.stderr and "trust this folder" in screen.lower():
                # The first-run trust dialog for the scratch folder this script just built:
                # Claude defaults to "No, exit", Codex to "Trust and continue" (saved in the throwaway home)
                for key in (("down", "enter") if a.runtime == "claude" else ("enter",)):
                    h("agent", "send-keys", name, key)
                h("agent", "wait", name, "--until", "idle", "--timeout", "30000")
            else:
                raise RuntimeError("agent did not start: " + (start.stdout + start.stderr).strip()[:200]
                                   + "\n" + "\n".join(screen.strip().splitlines()[-8:]))
        r = sh("herdr", "agent", "prompt", name, a.prompt, "--wait", "--timeout", str(a.timeout * 1000))
        status = (h("agent", "get", name).get("result") or {}).get("agent", {}).get("agent_status", "?")
        screen = sh("herdr", "agent", "read", name, "--source", "recent-unwrapped", "--lines", "40").stdout
        screen = "\n".join(ln for ln in screen.splitlines() if ln.strip())
        return {"final": screen[-600:], "runtime": [], "agent_status": status,
                "prompt_error": r.stderr.strip()[:200] if r.returncode else "",
                "workspace": ws["workspace"]["workspace_id"]}
    finally:
        if not a.keep:
            sh("herdr", "workspace", "close", ws["workspace"]["workspace_id"])


def run(a):
    if not a.prompt:
        a.prompt = f"Run exactly this shell command once, then report its result verbatim: {a.command}"
    a.dir = str(Path(a.dir).resolve())
    trace = Path(tempfile.mkstemp(prefix="hook-trace-")[1])
    env = dict(os.environ, HOOK_TRACE=str(trace))
    if a.runtime == "codex":
        env["CODEX_HOME"] = str(codex_home())
    started = time.time()
    try:
        res = herdr(a, env) if a.herdr else headless(a, env)
    except (RuntimeError, FileNotFoundError) as e:
        res = {"error": str(e)}
    finally:
        if a.runtime == "codex":
            shutil.rmtree(env["CODEX_HOME"], ignore_errors=True)
    lines = trace.read_text().splitlines() if trace.exists() else []
    trace.unlink(missing_ok=True)
    mine = [ln for ln in lines if ln.split(" ")[1:2] == [a.hook]]
    hit = any(ln.split(" ")[4:5] == [a.expect] for ln in mine)
    res.update(seconds=round(time.time() - started, 1), trace=mine, expect=a.expect, hook=a.hook,
               ok=hit and "error" not in res)
    if a.herdr and a.expect == "ask":
        res["ok"] = res["ok"] and res.get("agent_status") == "blocked"

    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"{'PASS' if res['ok'] else 'FAIL'}  {a.runtime} {a.hook} expect={a.expect}  {res['seconds']}s")
        for ln in mine or ["(no trace line for this hook: it never ran, or it doesn't use lib/hook-io.sh)"]:
            print(f"  trace    {ln}")
        for ln in res.get("runtime", []):
            print(f"  runtime  {ln}")
        if "agent_status" in res:
            print(f"  status   {res['agent_status']}" + ("  (kept: " + res["workspace"] + ")" if a.keep else ""))
        if res.get("error") or res.get("prompt_error"):
            print(f"  error    {res.get('error') or res.get('prompt_error')}")
        print("  agent    " + (res.get("final") or "").replace("\n", "\n           ")[:600])
    sys.exit(0 if res["ok"] else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scratch")
    s.add_argument("--from", dest="src", required=True)
    s.add_argument("--hooks-only", action="store_true")
    s.add_argument("--out")
    r = sub.add_parser("run")
    r.add_argument("--dir", required=True)
    r.add_argument("--runtime", choices=["claude", "codex"], required=True)
    r.add_argument("--hook", required=True, help="script basename as it appears in the trace, e.g. guard-bash.sh")
    r.add_argument("--expect", required=True,
                   choices=["pass", "block", "deny", "ask", "approve", "context", "continue"])
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--command", help="a shell command for the agent to run once")
    g.add_argument("--prompt", help="a free-form task (edits, multi-step work, a Stop gate)")
    r.add_argument("--herdr", action="store_true", help="run interactively in a herdr workspace")
    r.add_argument("--keep", action="store_true", help="leave the herdr workspace open to inspect")
    r.add_argument("--model")
    r.add_argument("--effort", help="Codex reasoning effort for the test agent")
    r.add_argument("--timeout", type=int, default=180, help="seconds")
    r.add_argument("--json", action="store_true")
    a = ap.parse_args()
    scratch(a) if a.cmd == "scratch" else run(a)


if __name__ == "__main__":
    main()
