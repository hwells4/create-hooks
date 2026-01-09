# Security Best Practices

## Disclaimer

**USE AT YOUR OWN RISK**: Claude Code hooks execute arbitrary shell commands automatically. You are responsible for:
- Commands you configure
- Files hooks can access (anything your user account can access)
- Testing hooks before production use

---

## Input Validation

**ALWAYS validate and sanitize inputs:**

```python
#!/usr/bin/env python3
import json
import os
import re
import sys

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})

# 1. Block path traversal
file_path = tool_input.get("file_path", "")
if ".." in file_path:
    print("Path traversal blocked", file=sys.stderr)
    sys.exit(2)

# 2. Validate against allowed paths
project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
if not file_path.startswith(project_dir):
    print("Access outside project directory blocked", file=sys.stderr)
    sys.exit(2)

# 3. Skip sensitive files
SENSITIVE_PATTERNS = [
    r"\.env$",
    r"\.env\.",
    r"credentials",
    r"secrets?\.ya?ml",
    r"\.pem$",
    r"\.key$",
    r"\.git/",
]

for pattern in SENSITIVE_PATTERNS:
    if re.search(pattern, file_path, re.IGNORECASE):
        print(f"Sensitive file access blocked: {pattern}", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
```

---

## Shell Variable Quoting

**ALWAYS quote shell variables:**

```bash
#!/bin/bash
# GOOD - quoted variables
FILE_PATH="$1"
cat "$FILE_PATH"

# BAD - unquoted (vulnerable to injection)
# cat $FILE_PATH
```

---

## Use Absolute Paths

**ALWAYS use absolute paths for scripts:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate.py"
          }
        ]
      }
    ]
  }
}
```

---

## Sensitive File Protection

**Block access to sensitive files:**

```python
#!/usr/bin/env python3
"""PreToolUse hook to protect sensitive files."""

import json
import sys

PROTECTED_FILES = [
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.yaml",
    ".git/config",
    "id_rsa",
    "id_ed25519",
]

PROTECTED_EXTENSIONS = [
    ".pem",
    ".key",
    ".p12",
    ".pfx",
]

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

if tool_name not in ["Read", "Write", "Edit"]:
    sys.exit(0)

file_path = tool_input.get("file_path", "")

# Check protected files
for protected in PROTECTED_FILES:
    if file_path.endswith(protected) or f"/{protected}" in file_path:
        print(f"Access to {protected} is blocked for security", file=sys.stderr)
        sys.exit(2)

# Check protected extensions
for ext in PROTECTED_EXTENSIONS:
    if file_path.endswith(ext):
        print(f"Access to {ext} files is blocked for security", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
```

---

## Command Injection Prevention

**Validate Bash commands:**

```python
#!/usr/bin/env python3
"""PreToolUse hook to prevent dangerous commands."""

import json
import re
import sys

BLOCKED_COMMANDS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\$HOME",
    r">\s*/dev/sd",
    r"dd\s+.*of=/dev/",
    r"mkfs\.",
    r":\(\)\{.*\}",  # Fork bomb
    r"chmod\s+-R\s+777",
    r"curl.*\|\s*(ba)?sh",  # Pipe to shell
    r"wget.*\|\s*(ba)?sh",
]

REQUIRE_CONFIRMATION = [
    r"sudo\s+",
    r"npm\s+publish",
    r"git\s+push.*--force",
    r"docker\s+rm",
    r"kubectl\s+delete",
]

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

command = data.get("tool_input", {}).get("command", "")

# Block dangerous commands
for pattern in BLOCKED_COMMANDS:
    if re.search(pattern, command, re.IGNORECASE):
        print(f"Dangerous command blocked: matches {pattern}", file=sys.stderr)
        sys.exit(2)

# Require confirmation for risky commands
for pattern in REQUIRE_CONFIRMATION:
    if re.search(pattern, command, re.IGNORECASE):
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"Risky command requires confirmation: {pattern}"
            }
        }
        print(json.dumps(output))
        sys.exit(0)

sys.exit(0)
```

---

## Configuration Safety

Claude Code protects against runtime hook modifications:

1. **Snapshot at startup** - Hooks are captured when session starts
2. **External modification warning** - Alerts if hooks change during session
3. **Review required** - Use `/hooks` menu to apply changes

This prevents malicious hook injection during a session.

---

## Security Checklist

Before deploying hooks:

- [ ] Validate all inputs from `tool_input`
- [ ] Quote all shell variables (`"$VAR"` not `$VAR`)
- [ ] Block path traversal (`..` in paths)
- [ ] Use absolute paths for scripts
- [ ] Protect sensitive files (`.env`, keys, credentials)
- [ ] Block dangerous commands (rm -rf /, sudo, etc.)
- [ ] Test hooks manually before enabling
- [ ] Log security-relevant operations
- [ ] Review hooks periodically for vulnerabilities
