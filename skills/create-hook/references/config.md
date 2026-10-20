# Registering a Hook

Read the target file before editing it, merge into any existing `hooks` object, and keep every other key untouched. Paths for each runtime and scope are in `runtimes.md`.

## Claude settings (`.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-bash.sh",
            "if": "Bash(rm *)",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- Several `if` rules on one script mean several handler entries, one rule each.
- Hard-blocking policy that must fail closed adds `"onFailure": "block"`.
- Observers add `"async": true`.

## Codex (`.codex/hooks.json`, `~/.codex/hooks.json`)

Same shape. Top-level keys are limited to `description` and `hooks`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "\"$(git rev-parse --show-toplevel)\"/.agents/hooks/guard-bash.sh",
            "timeout": 10,
            "statusMessage": "Checking command"
          }
        ]
      }
    ]
  }
}
```

The same hooks can live inline in `config.toml`:

```toml
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = '"$(git rev-parse --show-toplevel)"/.agents/hooks/guard-bash.sh'
timeout = 10
```

After writing, tell the user to open `/hooks` in Codex and trust the new entry.

## Plugin (`hooks/hooks.json` at the plugin root)

One file serves both runtimes when it uses shell form and `${CLAUDE_PLUGIN_ROOT}`:

```json
{
  "description": "Guardrails for shell commands",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/hooks/guard-bash.sh", "timeout": 10 }
        ]
      }
    ]
  }
}
```

State that must survive plugin updates goes in `${CLAUDE_PLUGIN_DATA}`. `${CLAUDE_PLUGIN_ROOT}` is replaced on every update. Shell-form plugin commands read user options from `$CLAUDE_PLUGIN_OPTION_<KEY>`; `${user_config.*}` works only in exec-form `args` (Claude).

## Skill and agent frontmatter (Claude only)

```yaml
---
name: deploy
description: ...
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/check-deploy.sh"
          once: true
---
```

A skill's hooks register when the skill is invoked and stay for the rest of the session (`once: true` removes a hook after its first successful run). An agent's hooks run only while that agent runs, and its `Stop` becomes `SubagentStop`.

## Check

- `jq empty <file>` for JSON, or `python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],"rb"))' <file>` for TOML.
- Start a shell in a subdirectory of the repo and run the command string with a fixture on stdin. A path that resolves only from the repo root shows up here.
