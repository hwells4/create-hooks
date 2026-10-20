# Hook Performance

A synchronous hook adds its full runtime to every event it matches. On the hot path (PreToolUse, PostToolUse, PermissionRequest, UserPromptSubmit) that cost repeats on every tool call. Matching hooks run in parallel, so an event costs as much as its slowest hook.

## Measured costs

From `scripts/test-hook.py` (median, Apple Silicon):

| Hook | ms |
|---|---|
| spawn floor (`true`) | 3.5 |
| one `jq` call | 6 |
| bash template on `lib/hook-io.sh` (one jq, built-in regex) | 10 |
| same logic in Python | 19 |
| same logic, one `grep` per rule (old template) | 21 |
| Node, parsing stdin and nothing else | 26 |

Interpreter startup is the bulk of the cost. A hook that loads dependencies (TypeScript compilers, npm packages) costs far more before it does any work.

## Cheapest first

1. **No process.** Claude's `if` field (`"Bash(git *)"`, `"Edit(*.ts)"`) is evaluated by Claude before anything spawns. Narrow every tool hook with a matcher, and with `if` when Claude is the runtime.
2. **One parse.** `hook_read` reads every common field in one jq call. A further `jq` on `$HOOK_INPUT` costs about 6ms each, so pull extra fields together.
3. **Built-ins over processes.** `[[ $x =~ $re ]]`, `case`, and parameter expansion cost microseconds. Each `grep`, `sed`, or `$(...)` pipeline adds a fork.
4. **Exit early.** Check the cheapest disqualifier first (wrong tool, wrong extension, empty command) and `hook_pass`.
5. **Async for observers.** Logging, metrics, notifications, test runs whose result can arrive next turn: `"async": true`. A Stop gate stays cheap when an async PostToolUse hook records state and the gate reads one file (`track-activity.sh` + `stop-gate.sh`).
6. **Bound the work.** A per-file check touches the changed file only. Whole-project lint, type-check, or test runs belong in an async hook or in the agent's own next step.
7. **Explicit timeouts.** Blocking hooks set a `timeout` near their real budget (5-30s). The default is 600s.
8. **Context budget.** `additionalContext` is read on the next model call: every injected line costs tokens every time. Inject what changed, briefly.

## Finding a slow hook

- Claude: `claude --debug-file /tmp/claude.log`, then look for `Hooks:` lines ending in a duration (v2.1.296+).
- Either runtime: wrap the command with `templates/debug-wrap.sh` and read the durations with `scripts/hook-log.py --slow 50`.
- In isolation: `python3 scripts/test-hook.py --repeat 20 "<command>" fixture.json:<expect>`.
