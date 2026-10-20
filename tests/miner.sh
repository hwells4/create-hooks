#!/usr/bin/env bash
# Seeds synthetic Claude and Codex transcripts in a fake HOME and checks mine-candidates.py groups
# each signal, and ignores look-alikes. Usage: tests/miner.sh
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
work=$(cd "$(mktemp -d "${TMPDIR:-/tmp}/miner-tests.XXXXXX")" && pwd)
trap 'rm -r "$work"' EXIT
proj="$work/proj"
mkdir -p "$proj/.claude" && git -C "$proj" init -q

python3 - "$work" "$proj" <<'EOF'
import json, os, re, sys
home, proj = sys.argv[1] + "/home", sys.argv[2]
cdir = f"{home}/.claude/projects/{re.sub(r'[^A-Za-z0-9]', '-', proj)}"
os.makedirs(cdir)
def use(name, inp): return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t", "name": name, "input": inp}]}}
def res(text, err=True): return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": text, "is_error": err}]}}
def say(text): return {"type": "user", "message": {"content": text}}
claude = [
    use("Bash", {"command": "cd /x && git push origin main"}),
    res("The user doesn't want to proceed with this tool use. The tool use was rejected."),
    say([{"type": "text", "text": "[Request interrupted by user for tool use]"}]),
    use("Edit", {"file_path": "/x/package-lock.json"}),
    res("ok", err=False),
    say("no, don't edit the lockfile by hand"),
    use("Bash", {"command": "SC=/tmp/a && cat > $SC/x <<'EOF'\nbody\nEOF"}),
    res("PreToolUse:Bash hook error: docs quoted in a result", err=False),
    use("Bash", {"command": "ssh vps cat ~/.env"}),
    res("Permission for this action has been denied by the Claude Code auto mode classifier. Reason: [Credential Materialization]."),
    use("Write", {"file_path": "/x/brain/a.md"}),
    res("PreToolUse:Write hook error: Vault schema validation failed."),
    say("<command-name>/clear</command-name> no"),
]
with open(f"{cdir}/s1.jsonl", "w") as f:
    f.writelines(json.dumps(r) + "\n" for r in claude)
xdir = f"{home}/.codex/sessions/2026/10/19"
os.makedirs(xdir)
codex = [
    {"type": "session_meta", "payload": {"cwd": proj}},
    {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
        "input": 'text(await tools.exec_command({cmd:"git push --force origin main"}))'}},
    {"type": "response_item", "payload": {"type": "custom_tool_call_output",
        "output": "Script failed\nOutput:\nCommand blocked by PreToolUse hook: no force push"}},
    {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command",
        "arguments": json.dumps({"cmd": "rm -rf build"})}},
    {"type": "event_msg", "payload": {"type": "turn_aborted"}},
    {"type": "response_item", "payload": {"type": "message", "role": "user",
        "content": [{"type": "input_text", "text": "stop, use pnpm"}]}},
    {"type": "response_item", "payload": {"type": "message", "role": "user",
        "content": [{"type": "input_text", "text": "<environment_context>no</environment_context>"}]}},
]
with open(f"{xdir}/rollout-test.jsonl", "w") as f:
    f.writelines(json.dumps(r) + "\n" for r in codex)
json.dump({"permissions": {"allow": ["Bash(npm test:*)"]}}, open(f"{proj}/.claude/settings.local.json", "w"))
EOF

out=$(env -u CODEX_HOME HOME="$work/home" python3 "$root/skills/create-hook/scripts/mine-candidates.py" --project "$proj" --json)
q() { printf '%s' "$out" | jq -r "$1"; }

failed=0
check() { [ "$2" = "$3" ] || { echo "FAIL $1: got '$2', want '$3'"; failed=1; }; }
check sessions            "$(q .sessions)" 2
check rejected            "$(q '[.groups.rejected[].key] | join(",")')" "Bash git push"
check interrupt-dedup     "$(q '[.groups.interrupted[].key] | join(",")')" "Bash rm"
check corrected           "$(q '[.groups.corrected[].key] | sort | join(",")')" "Bash rm,Edit package-lock.json"
check classifier          "$(q '.groups.classifier[0].key')" "Bash ssh [Credential Materialization]"
check hook-claude         "$(q '[.groups.hook[].key] | map(select(startswith("PreToolUse:Write"))) | length')" 1
check hook-codex          "$(q '[.groups.hook[].key] | map(select(startswith("Command blocked"))) | length')" 1
check hook-not-docs       "$(q '[.groups.hook[].key] | map(select(contains("docs quoted"))) | length')" 0
check saved               "$(q '.groups.saved[0].key')" "Bash(npm test:*)"
check sample-has-line     "$(q '.groups.rejected[0].samples[0].at' | grep -c ':[0-9]*$')" 1

# Assignment-only first segment: the action is the command after it
check assignment-skip     "$(python3 -c "
import importlib.util as u; s=u.spec_from_file_location('m','$root/skills/create-hook/scripts/mine-candidates.py')
m=u.module_from_spec(s); s.loader.exec_module(m); print(m.command_head('SC=/a && cat > x'), '|', m.command_head('# note\ngit status'))")" "cat | git status"

[ "$failed" = 0 ] && echo "ALL MINER TESTS PASS"
exit "$failed"
