#!/usr/bin/env python3
"""Build a project whose hook configs exercise every validate-hooks.py rule. Usage: validator_fixture.py DIR"""
import json
import os
import sys
from pathlib import Path

P = Path(sys.argv[1])
H = P / ".claude/hooks"
for d in (H, P / ".claude/skills/fm", P / ".claude/agents", P / ".codex"):
    d.mkdir(parents=True, exist_ok=True)
scripts = {
    "block-good.sh": '#!/bin/bash\necho "blocked: dangerous" >&2\nexit 2\n',
    "exit1.sh": '#!/bin/bash\ninput=$(cat)\ntool=$(echo "$input" | jq -r .tool_name)\n'
                '[ "$tool" = Bash ] && { echo "block this" >&2; exit 1; }\nexit 0\n',
    "exit2-stdout.sh": '#!/bin/bash\necho "reason on stdout"\nexit 2\n',
    "stop-good.sh": '#!/bin/bash\ninput=$(cat)\n[ "$(echo "$input" | jq -r .stop_hook_active)" = true ] && exit 0\nexit 0\n',
    "stop-loop.py": '#!/usr/bin/env python3\nimport json\nprint(json.dumps({"decision": "approve"}))\n',
    "noexec.sh": "#!/bin/bash\nexit 0\n",
    "noshebang.sh": "echo hi\n",
    "badsyntax.sh": "#!/bin/bash\nif then fi (\n",
    "badsyntax.py": "#!/usr/bin/env python3\ndef x(:\n",
    "ask.sh": "#!/bin/bash\necho '{\"hookSpecificOutput\":{\"permissionDecision\":\"ask\"}}'\n",
    "ask-lib.sh": '#!/bin/bash\nsource lib/hook-io.sh\nhook_ask "check"\n',
}
for name, body in scripts.items():
    (H / name).write_text(body)
    os.chmod(H / name, 0o644 if name == "noexec.sh" else 0o755)

(P / ".claude/skills/fm/SKILL.md").write_text("---\nname: fm\nhooks:\n  PreToolUse: []\n---\nbody\n")
(P / ".claude/agents/plain.md").write_text("---\nname: a\n---\nhooks: not frontmatter\n")

def cmd(c, **kw):
    return dict(type="command", command=c, **kw)

PD = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/'
GT = "$(git rev-parse --show-toplevel)/.claude/hooks/"
dup = {"matcher": "Edit", "hooks": [cmd("echo done", **{"async": True})]}
claude = {"hooks": {
    "PreToolUse": [
        {"matcher": "Bash", "hooks": [cmd(PD + "block-good.sh", timeout=5)]},
        {"matcher": "Bash", "hooks": [cmd("${CLAUDE_PROJECT_DIR}/.claude/hooks/exit1.sh", timeout=5)]},
        {"matcher": "Edit|MultiEdit", "hooks": [cmd("bash .claude/hooks/exit2-stdout.sh", timeout=5)]},
        {"matcher": "Task", "hooks": [{"type": "prompt", "prompt": "Is this subagent call ok?"}]},
        {"matcher": "Write", "hooks": [cmd(PD + "missing.sh", timeout=5)]},
        {"matcher": "Read", "hooks": [cmd(PD + "noexec.sh", timeout=5)]},
    ],
    "Stop": [
        {"hooks": [cmd(PD + "stop-good.sh", timeout=10)]},
        {"hooks": [cmd(PD + "stop-loop.py", **{"if": "Bash(git *)"})]},
    ],
    "UserPromptSubmit": [{"matcher": "foo", "hooks": [cmd("bash " + PD + "noexec.sh")]}],
    "SessionStart": [{"hooks": [{"type": "prompt", "prompt": "hi"}, cmd(".claude/hooks/noshebang.sh")]}],
    "Notification": [{"hooks": [{"type": "agent", "prompt": "x"},
                                cmd("bash .claude/hooks/badsyntax.sh"),
                                cmd("python3 .claude/hooks/badsyntax.py")]}],
    "PostToolUse": [dup],
}}
(P / ".claude/settings.json").write_text(json.dumps(claude, indent=1))
(P / ".claude/settings.local.json").write_text(json.dumps({"hooks": {"PostToolUse": [dup]}}))

codex = {"description": "test", "version": 2, "hooks": {
    "PreToolUse": [
        {"matcher": "Bash", "hooks": [cmd(GT + "block-good.sh", timeout=5)]},
        {"matcher": "Bash", "hooks": [cmd("$CLAUDE_PROJECT_DIR/.claude/hooks/ask.sh", timeout=5,
                                          args=["x"], **{"if": "Bash(rm *)"})]},
        {"matcher": "Bash", "hooks": [cmd(GT + "ask-lib.sh", timeout=5, once=True)]},
        {"matcher": "Bash", "hooks": [{"type": "http", "url": "http://localhost/x"},
                                      {"type": "prompt", "prompt": "ok?"}]},
    ],
    "Notification": [{"hooks": [cmd("echo n")]}],
    "PostToolUseFailure": [{"hooks": [cmd("echo f")]}],
    "Stop": [{"matcher": "x", "hooks": [cmd('"' + GT[:-15] + '"/.claude/hooks/stop-good.sh', timeout=10)]}],
}}
(P / ".codex/hooks.json").write_text(json.dumps(codex, indent=1))
(P / ".codex/config.toml").write_text(
    'model = "x"\n[[hooks.SessionStart]]\n[[hooks.SessionStart.hooks]]\n'
    'type = "command"\ncommand = "echo toml-start"\n')
print("built", P)
