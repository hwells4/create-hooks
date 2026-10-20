#!/usr/bin/env python3
"""
test-hook.py - run a hook command against fixture payloads and check the outcome.

Usage:
    python3 test-hook.py [--repeat N] HOOK_COMMAND FIXTURE:EXPECT [FIXTURE:EXPECT ...]

    HOOK_COMMAND  the exact command string from the hook config (run through sh -c)
    FIXTURE       JSON payload file, e.g. fixtures/claude/PreToolUse-bash.json
    EXPECT        pass | block | deny | ask | allow | approve | context | continue

Outcomes are read the way the runtimes read them:
    exit 2                                   -> block
    exit 0 + permissionDecision deny|ask|allow -> deny | ask | allow
    exit 0 + decision.behavior allow|deny      -> approve | deny
    exit 0 + decision "block" (Stop, PostToolUse) -> continue
    exit 0 + additionalContext or plain text   -> context
    exit 0, nothing printed                    -> pass
    any other exit                             -> error (the action goes ahead: fail-open)

A Codex fixture (has turn_id) runs without CLAUDE_PROJECT_DIR, the way Codex runs hooks.
Exit status: 0 when every case matches, 1 otherwise.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time


def classify(code: int, stdout: str) -> tuple[str, str]:
    """Return (outcome, note)."""
    if code == 2:
        return "block", ""
    if code != 0:
        return "error", f"exit {code}"
    out = stdout.strip()
    if not out:
        return "pass", ""
    if not out.startswith("{"):
        return "context", "plain-text stdout"
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return "error", "stdout starts with '{' but is not one JSON object"
    hso = data.get("hookSpecificOutput") or {}
    decision = hso.get("permissionDecision")
    if decision in ("deny", "ask", "allow", "defer"):
        return decision, ""
    behavior = (hso.get("decision") or {}).get("behavior")
    if behavior == "allow":
        return "approve", ""
    if behavior == "deny":
        return "deny", ""
    if data.get("decision") == "block":
        return "continue", ""
    if data.get("decision") == "approve":
        return "error", "deprecated decision: approve"
    if hso.get("additionalContext"):
        return "context", ""
    return "pass", "JSON with no decision"


def run_case(command: str, fixture: str, repeat: int) -> tuple[str, str, float, str]:
    with open(fixture) as f:
        payload = f.read()
    try:
        is_codex = "turn_id" in json.loads(payload)
    except json.JSONDecodeError:
        sys.exit(f"{fixture}: not valid JSON")

    env = dict(os.environ)
    if is_codex:
        env.pop("CLAUDE_PROJECT_DIR", None)
    else:
        env.setdefault("CLAUDE_PROJECT_DIR", os.getcwd())

    timings, result = [], None
    for _ in range(repeat):
        start = time.perf_counter()
        result = subprocess.run(
            ["sh", "-c", command], input=payload, capture_output=True, text=True, env=env, timeout=60
        )
        timings.append((time.perf_counter() - start) * 1000)
    outcome, note = classify(result.returncode, result.stdout)
    detail = result.stderr.strip().splitlines()[0] if result.stderr.strip() else ""
    return outcome, note, statistics.median(timings), detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeat", type=int, default=5, help="runs per case; median is reported (default 5)")
    parser.add_argument("command")
    parser.add_argument("cases", nargs="+", metavar="FIXTURE:EXPECT")
    args = parser.parse_args()

    failures = 0
    for case in args.cases:
        fixture, _, expect = case.rpartition(":")
        if not fixture:
            sys.exit(f"{case}: expected FIXTURE:EXPECT")
        outcome, note, ms, detail = run_case(args.command, fixture, args.repeat)
        ok = outcome == expect
        failures += not ok
        line = f"{'PASS' if ok else 'FAIL'}  {outcome:<8} {ms:7.1f}ms  {fixture}"
        if not ok:
            line += f"  (expected {expect})"
        if note:
            line += f"  [{note}]"
        if detail and (not ok or outcome in ("block", "error")):
            line += f"\n      stderr: {detail}"
        print(line)

    print(f"\n{len(args.cases) - failures}/{len(args.cases)} cases match")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
