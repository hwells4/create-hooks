---
name: create-hook
description: Hooks for Claude Code and Codex. Use to find which hooks are worth building from past sessions, create a hook (guard a tool call, inject context, gate Stop, auto-approve, notify), debug one that misfires or slows the agent, audit the hooks a project runs, consolidate several into a dispatcher, or port hooks between Claude Code and Codex.
---

# Create Hook

A hook is code the runtime runs at a lifecycle event. It reads one JSON payload on stdin and answers with an exit code or one JSON object. Claude Code and Codex share that contract almost field for field, so one script serves both; `references/runtimes.md` holds the differences.

Four words carry this skill:

- **Approved spec**: no hook file is written until the user has replied yes to the step 2 block. Showing the block ends your turn, in every runtime, however clear the request looks; a hook the user didn't confirm guards the wrong thing.
- **Hot path**: PreToolUse, PostToolUse, PermissionRequest, and UserPromptSubmit hooks run on every matching call while the agent waits. Hot-path hooks are tight: one jq parse, built-in matching, no interpreter startup, under 50ms.
- **Guardrail**: a hook catches the common case, and a crashed or timed-out hook lets the action through. Hard policy lives in the runtime's own controls (Claude permission rules, Codex sandbox and approval policy).
- **Red/green**: a hook is done when a fixture that should trip it goes red (deny or block) and a clean fixture goes green, in each target runtime's payload shape.

## Route

| Request | Go to |
|---|---|
| Which hooks should I have; ideas for hooks | `workflows/brainstorm.md` |
| Create or change a hook | Steps below |
| A hook doesn't fire, fires wrong, or is slow | `workflows/debug.md` |
| What hooks run here, and are they sound | `workflows/audit.md` |
| Several hooks on one event, or a `checks/` dispatcher exists | `workflows/consolidate.md` |
| Make existing hooks work in the other runtime | `workflows/port.md` |

## Steps

1. **Inventory.** Run `python3 scripts/validate-hooks.py --inventory --project <repo>`.
   Done when you can name every hook already on the target event in each target runtime. If that event has a dispatcher (a `checks/` directory), the new logic becomes a check: switch to `workflows/consolidate.md`.

2. **Spec.** Ask the user to approve the spec: reply with the block below ending in the question `Build this? (yes, or what to change)`, and wait for the answer before step 3. The block's shape:
   ```
   On PreToolUse [Bash, if Bash(git push *)] in both at project scope,
   a command hook checks the push target and denies pushes to main.

     red:   git push origin main            -> deny
     red:   git push -f origin HEAD:main    -> deny
     green: git push origin feature/x       -> pass
     gap:   Codex ignores `if`; the script filters for itself.
   ```
   The first line follows `On <Event> [matcher, if] in <claude|codex|both> at <user|project|local> scope, a <handler> checks <X> and answers <Y>.` Then two to four cases, each a concrete input and the decision it gets, with at least one red and one green, and the near miss the user is most likely to worry about. Then one `gap:` line per runtime limit that applies.
   When the event isn't obvious, choose it from `references/events.md`; when Codex is a target, read `references/runtimes.md` first. Scope: project is committed and shared, local is Claude's personal `.claude/settings.local.json`, user covers every project.
   Done when the user has approved the block. Its cases become step 5's first test cases.

3. **Mechanism.** Take the lowest rung that does the job (`references/handlers.md`):
   1. No hook: static guidance goes in CLAUDE.md / AGENTS.md; allowing or denying a command by its prefix is a permission rule. A rule that depends on argument order, repo state (the current branch), absolute paths like `/usr/bin/git`, or Codex needs a hook.
   2. `command` hook, narrowed by matcher and, in Claude, `if`.
   3. `async` command, for anything that only observes, records, or reports.
   4. `mcp_tool` or `http`, when the logic already lives behind a server.
   5. `prompt` (one model call) or `agent` (multi-turn verifier), for judgment a script cannot make. Claude only, seconds per run.

   Done when you can say why each lower rung falls short.

4. **Write.** Copy the closest template and `templates/lib/hook-io.sh` into the hooks directory: `.claude/hooks/` for Claude only, `.codex/hooks/` for Codex only, `.agents/hooks/` when both configs point at one script. Follow the rules below.
   Done when `bash -n` passes and every decision goes through a `hook_*` emitter.

5. **Test.** Derive cases from `fixtures/<runtime>/`, pointing `cwd` at the real repo so git and path lookups work:
   `jq --arg cwd "$PWD" '.cwd = $cwd | .tool_input.command = "git push origin main"' fixtures/claude/PreToolUse-bash.json > /tmp/push-main.json`
   Then run `python3 scripts/test-hook.py "<command>" /tmp/push-main.json:deny ...`, once per runtime with that runtime's config command string. The runner sets `CLAUDE_PROJECT_DIR` to the current directory for Claude cases and unsets it for Codex cases (those with `turn_id`).
   Done when every decision the hook can make has a case that lands as expected, in each target runtime's fixtures, and hot-path cases report a median under 50ms.


6. **Register.** Add the handler to each runtime's config at the chosen scope; `references/config.md` has the shapes and path idioms.
   Done when the file parses and the command path resolves when the session starts in a subdirectory.

7. **Validate.** Run `python3 scripts/validate-hooks.py --project <repo>`.
   Done when it reports no ERROR and each WARN is fixed or explained to the user.

8. **Live.** Build a throwaway copy with `python3 scripts/live-test.py scratch --from <repo>` (its origin is a local bare repo, so a red case that slips through lands there), and run one red and one green spec case per target runtime:
   `python3 scripts/live-test.py run --dir <scratch> --runtime claude --hook <script.sh> --expect deny --command "git push origin main"`
   It runs `claude -p` or `codex exec` and reads the line each `hook-io.sh` hook appends to `HOOK_TRACE`. Claude runs with permissions bypassed, so a red case the hook misses really executes: pick red cases whose damage stays inside the scratch repo (a push, deleting a tracked file), and leave anything that reaches outside it (`rm -rf ~`, a real API call) to fixtures. Add `--herdr` (herdr installed) for decisions that only show in an interactive session: `ask`, PermissionRequest, Notification. Use `--prompt` instead of `--command` for edits and Stop gates.
   Done when each live case prints PASS, or the user has chosen to skip live tests (each run is a model call of several seconds).

9. **Report.** Give the spec line, files written, fixture and live test results with timings, the `references/runtimes.md` rows that change this hook's behavior in each runtime, what it can't see (edits made through Bash bypass Write/Edit hooks), and the activation step: Claude picks up settings edits on its own (confirm in `/hooks`); Codex runs a new or edited hook only after the user trusts it in `/hooks`.

## Rules every hook script follows

- Read stdin once with `hook_read`; take fields from the `HOOK_*` variables or one more jq call on `$HOOK_INPUT`.
- One answer channel: exit 2 with the message on stderr, or exit 0 with exactly one JSON object on stdout. Keep stdout otherwise silent, since any extra line turns the JSON into plain text.
- Exit 2 is the only blocking exit code. Exit 1 is a hook error, and the action goes ahead.
- Messages are written for the agent: what was refused and the next step to take.
- Stop and SubagentStop hooks pass when `HOOK_STOP_ACTIVE` is true.
- Paths are absolute and quoted, built from `hook_project_dir` or the payload's `cwd`.
- Scripts run on macOS `/bin/bash` 3.2: indexed arrays, `[[ =~ ]]`, and `case` are available; associative arrays and `${x,,}` are not.
- Work that outlives the decision runs detached with stdout and stderr redirected, after the answer is printed.

## Templates

| Template | Event | Runtimes |
|---|---|---|
| `guard-bash.sh` | PreToolUse `Bash` | both |
| `guard-files.sh` | PreToolUse `Write\|Edit` (Codex `apply_patch`) | both |
| `post-edit-check.sh` | PostToolUse `Write\|Edit` | both |
| `inject-context.sh` | SessionStart, UserPromptSubmit | both |
| `track-activity.sh` + `stop-gate.sh` | PostToolUse (async) + Stop | both |
| `approve-safe.sh` | PermissionRequest `Bash` | both |
| `notify.sh` | Notification (Claude), Stop (Codex) | both |
| `failure-hint.sh` | PostToolUseFailure `Bash` | Claude |
| `dispatcher.sh` | any; runs `checks/*.sh` | both |
| `stop-check.prompt.json` | Stop, prompt handler | Claude |
| `stop-verify.agent.json` | Stop, agent handler | Claude |
| `debug-wrap.sh` | wraps any command; logs exit and duration | both |

## References

Load each when its condition holds:

- `references/events.md`: choosing an event, what it can control, matcher values.
- `references/handlers.md`: handler types and fields (`if`, `async`, `timeout`, `onFailure`, exec vs shell form); prompt and agent response schema.
- `references/io.md`: input fields, the exit-code matrix, JSON output for each kind of decision.
- `references/runtimes.md`: any hook that must run in Codex, or in both runtimes.
- `references/config.md`: registering a hook in settings files, `hooks.json` / `config.toml`, plugins, or skill and agent frontmatter.
- `references/performance.md`: hot-path hooks, or a hook reported as slow.
- `references/security.md`: hooks that read paths, run commands, or approve actions.

Full schemas: https://code.claude.com/docs/en/hooks and https://learn.chatgpt.com/docs/hooks
