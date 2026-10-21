# Prompt-Based Hooks

Instead of running shell commands, hooks can invoke an LLM for evaluation. This enables intelligent, context-aware decisions without writing code.

## Configuration Syntax

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Your evaluation instructions with $ARGUMENTS placeholder",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Must be `"prompt"` (not `"command"`) |
| `prompt` | Yes | Instructions for the LLM. Use `$ARGUMENTS` for context. |
| `timeout` | No | Seconds to wait (default: 60) |

## Supported Events

| Event | Use Case |
|-------|----------|
| **Stop** | Intelligent task completion checking |
| **SubagentStop** | Subagent work validation |
| **UserPromptSubmit** | Prompt analysis and filtering |
| **PreToolUse** | Context-aware tool approval |
| **PermissionRequest** | Dynamic permission decisions |

**Not supported:** PostToolUse, SessionStart, SessionEnd, PreCompact, Notification

## $ARGUMENTS Placeholder

The `$ARGUMENTS` variable is replaced with JSON containing event-specific data (same structure as stdin for command hooks):

```json
// For Stop event:
{
  "session_id": "abc123",
  "transcript_path": "/path/to/session.jsonl",
  "hook_event_name": "Stop",
  "stop_hook_active": false
}

// For PreToolUse event:
{
  "session_id": "abc123",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." }
}
```

## LLM Response Schema

The LLM must return valid JSON:

```json
{
  "decision": "approve|block",
  "reason": "Explanation shown to Claude or user",
  "continue": false,
  "stopReason": "Message shown to user when continue=false",
  "systemMessage": "Warning message shown to user"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `decision` | Yes | `"approve"` allows, `"block"` prevents |
| `reason` | Yes | Explanation (shown to Claude for block, logged for approve) |
| `continue` | No | Set `false` to stop Claude entirely |
| `stopReason` | No | User message when `continue: false` |
| `systemMessage` | No | Warning displayed to user |

## When to Use Prompt vs Command

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Regex pattern matching | `command` | Deterministic, faster |
| File system checks | `command` | Direct access needed |
| External API calls | `command` | Network/auth handling |
| Task completeness evaluation | `prompt` | Requires judgment |
| Code quality assessment | `prompt` | Context-aware |
| Intent validation | `prompt` | Nuanced understanding |
| Transcript analysis | `prompt` | LLM excels at this |

## Examples

### Intelligent Stop Hook

Evaluate if Claude should stop based on task completion:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Review the conversation context and determine if Claude should stop.\n\nCheck for:\n1. Were all requested tasks completed?\n2. Are there uncommitted code changes?\n3. Were tests run if code was modified?\n4. Are there unresolved errors or TODOs?\n\nContext:\n$ARGUMENTS\n\nRespond with JSON: {\"decision\": \"approve|block\", \"reason\": \"explanation\"}",
            "timeout": 45
          }
        ]
      }
    ]
  }
}
```

### Context-Aware PreToolUse

Evaluate tool calls based on conversation context:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate this file modification request.\n\nCheck:\n1. Does the change align with the user's stated intent?\n2. Is this modifying a sensitive file (.env, credentials, etc.)?\n3. Does this seem like an appropriate change?\n\nTool call:\n$ARGUMENTS\n\nRespond with: {\"decision\": \"approve|block\", \"reason\": \"...\"}",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Prompt Filtering

Analyze user prompts before processing:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Analyze this user prompt for potential issues.\n\nCheck for:\n1. Requests that might cause data loss\n2. Ambiguous instructions that need clarification\n3. Scope creep from the original task\n\nPrompt:\n$ARGUMENTS\n\nIf issues found, respond with {\"decision\": \"block\", \"reason\": \"Issue description\"}.\nOtherwise respond with {\"decision\": \"approve\", \"reason\": \"Prompt is clear\"}.",
            "timeout": 20
          }
        ]
      }
    ]
  }
}
```

## Combining with Command Hooks

You can mix prompt and command hooks for the same event:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/check-git-status.py"
          },
          {
            "type": "prompt",
            "prompt": "Evaluate task completeness: $ARGUMENTS",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Both hooks run in parallel. If either blocks, the action is blocked.

## Preventing Infinite Loops

For Stop hooks, always check `stop_hook_active` in your prompt:

```json
{
  "type": "prompt",
  "prompt": "Check if Claude should stop.\n\nIMPORTANT: If stop_hook_active is true, Claude is already continuing from a previous stop hook. Allow stopping to prevent infinite loops.\n\n$ARGUMENTS"
}
```

## Debugging Prompt Hooks

1. **Check output**: Use `claude --debug` to see LLM responses
2. **Test prompts**: Run prompts manually to verify they produce valid JSON
3. **Simplify**: Start with simple prompts, add complexity gradually
4. **Timeout**: Increase timeout if responses are being cut off

## Performance Considerations

- Prompt hooks are slower than command hooks (LLM inference time)
- Default 60s timeout may be too short for complex evaluations
- Use command hooks for simple checks, reserve prompt hooks for judgment calls
- Consider `timeout` carefully for each use case
