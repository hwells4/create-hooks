# SessionStart Environment Variables

SessionStart hooks can persist environment variables for the entire Claude Code session using `CLAUDE_ENV_FILE`.

## Available Environment Variables

| Variable | Available In | Description |
|----------|--------------|-------------|
| `CLAUDE_PROJECT_DIR` | All hooks | Absolute path to project root |
| `CLAUDE_CODE_REMOTE` | All hooks | `"true"` if web/remote environment, empty for CLI |
| `CLAUDE_ENV_FILE` | SessionStart only | Path to file for persisting env vars |
| `CLAUDE_PLUGIN_ROOT` | Component hooks only | Absolute path to plugin/skill directory |

---

## How It Works

1. Claude Code creates a temporary env file at session start
2. Sets `CLAUDE_ENV_FILE` to that file's path
3. Your hook writes export statements to that file
4. Claude Code sources the file before each Bash command
5. Variables persist for ALL subsequent Bash tool calls

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  SessionStart   │────▶│  CLAUDE_ENV_FILE │────▶│   All Bash      │
│  Hook writes:   │     │  contains:       │     │   commands see: │
│  export FOO=bar │     │  export FOO=bar  │     │   $FOO = bar    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Basic Usage

### Setting Individual Variables

```bash
#!/bin/bash
# .claude/hooks/session-init.sh

if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=development' >> "$CLAUDE_ENV_FILE"
  echo 'export DEBUG=true' >> "$CLAUDE_ENV_FILE"
  echo 'export API_URL=http://localhost:3000' >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

### Python Version

```python
#!/usr/bin/env python3
import os
import sys

env_file = os.environ.get("CLAUDE_ENV_FILE")
if env_file:
    with open(env_file, "a") as f:
        f.write('export NODE_ENV=development\n')
        f.write('export DEBUG=true\n')

sys.exit(0)
```

## Advanced: Capturing Environment Changes

When your setup scripts modify the environment (like `nvm use` or `pyenv activate`), capture ALL changes:

```bash
#!/bin/bash
# Capture environment BEFORE setup
ENV_BEFORE=$(export -p | sort)

# Run setup that modifies environment
source ~/.nvm/nvm.sh
nvm use 20

# Capture environment AFTER setup
ENV_AFTER=$(export -p | sort)

# Write ONLY the differences to CLAUDE_ENV_FILE
if [ -n "$CLAUDE_ENV_FILE" ]; then
  # comm -13 shows lines only in AFTER (new/changed exports)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

## Common Patterns

### 1. Node.js Version Manager (nvm)

```bash
#!/bin/bash
ENV_BEFORE=$(export -p | sort)

# Load nvm and use project's Node version
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# Use version from .nvmrc or default
if [ -f ".nvmrc" ]; then
  nvm use
else
  nvm use default
fi

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

### 2. Python Virtual Environment

```bash
#!/bin/bash
ENV_BEFORE=$(export -p | sort)

# Activate virtualenv if present
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

### 3. Ruby Version Manager (rbenv)

```bash
#!/bin/bash
ENV_BEFORE=$(export -p | sort)

# Initialize rbenv
export PATH="$HOME/.rbenv/bin:$PATH"
eval "$(rbenv init -)"

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

### 4. Load Project-Specific Config

```bash
#!/bin/bash
# Load project config without exposing secrets

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if [ -n "$CLAUDE_ENV_FILE" ]; then
  # Set project paths
  echo "export PROJECT_ROOT=\"$PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export PATH=\"$PROJECT_DIR/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

  # Load safe config (NOT .env with secrets!)
  if [ -f "$PROJECT_DIR/.claude-env" ]; then
    cat "$PROJECT_DIR/.claude-env" >> "$CLAUDE_ENV_FILE"
  fi
fi

exit 0
```

### 5. Conditional Environment Based on Project Type

```bash
#!/bin/bash
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

if [ -n "$CLAUDE_ENV_FILE" ]; then
  # Node.js project
  if [ -f "$PROJECT_DIR/package.json" ]; then
    echo 'export PATH="./node_modules/.bin:$PATH"' >> "$CLAUDE_ENV_FILE"
  fi

  # Python project
  if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo 'export PYTHONDONTWRITEBYTECODE=1' >> "$CLAUDE_ENV_FILE"
  fi

  # Rust project
  if [ -f "$PROJECT_DIR/Cargo.toml" ]; then
    echo 'export CARGO_TERM_COLOR=always' >> "$CLAUDE_ENV_FILE"
  fi
fi

exit 0
```

## Using Environment Variables in Other Hooks

Variables set via `CLAUDE_ENV_FILE` are available in:
- All subsequent `Bash` tool calls
- Other hooks that run Bash commands

**NOT available in:**
- The same SessionStart hook that set them
- Python/other hooks directly (they run in separate processes)

### Accessing in Later Hooks

```python
#!/usr/bin/env python3
# PostToolUse hook - env vars ARE available via subprocess

import os
import subprocess
import sys

# This WON'T work (hook's own environment)
# my_var = os.environ.get("MY_VAR")

# This WILL work (Bash has the env file sourced)
result = subprocess.run(
    ["bash", "-c", "echo $MY_VAR"],
    capture_output=True,
    text=True
)
my_var = result.stdout.strip()

sys.exit(0)
```

## Settings Configuration

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-env.sh"
          }
        ]
      }
    ]
  }
}
```

### Matcher Options for SessionStart

| Matcher | When |
|---------|------|
| `startup` | New session started |
| `resume` | `--resume`, `--continue`, or `/resume` |
| `clear` | `/clear` command |
| `compact` | Auto or manual context compaction |
| (empty) | All of the above |

## Debugging

### Check if variables were set

```bash
# In Claude Code, run:
env | grep MY_VAR
```

### View the env file contents

```bash
# The file path is in CLAUDE_ENV_FILE during SessionStart only
# But you can check what was written:
cat /tmp/claude-env-*  # Approximate path
```

### Test your hook manually

```bash
# Simulate SessionStart input
echo '{"hook_event_name": "SessionStart", "source": "startup"}' | \
  CLAUDE_ENV_FILE=/tmp/test-env.sh \
  bash .claude/hooks/session-env.sh

# Check what was written
cat /tmp/test-env.sh
```

## Important Notes

1. **CLAUDE_ENV_FILE is ONLY available in SessionStart hooks** - other hook types don't have it

2. **Write `export` statements** - Just `VAR=value` won't export to subprocesses

3. **Append, don't overwrite** - Use `>>` not `>` in case multiple hooks write

4. **Don't store secrets** - The env file is temporary but readable; use secret managers for sensitive values

5. **PATH modifications** - Use `$PATH` not hardcoded paths:
   ```bash
   echo 'export PATH="./bin:$PATH"' >> "$CLAUDE_ENV_FILE"
   ```

6. **Quote properly** - Variables in the env file are evaluated when sourced:
   ```bash
   # This evaluates PROJECT_DIR at source time (good)
   echo "export MY_PATH=\"\$PROJECT_DIR/bin\"" >> "$CLAUDE_ENV_FILE"

   # This evaluates NOW (might not be what you want)
   echo "export MY_PATH=\"$PROJECT_DIR/bin\"" >> "$CLAUDE_ENV_FILE"
   ```
