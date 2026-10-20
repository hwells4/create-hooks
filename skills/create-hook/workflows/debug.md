# Debug a Hook

Work down the chain a hook run takes: registered, matched, started, answered, understood. Stop at the first broken link.

## Steps

1. **Registered.** Run `python3 scripts/validate-hooks.py --project <repo>` and open `/hooks` in the runtime.
   Done when the hook appears in `/hooks` under the expected event and source. If it is missing:
   - Claude: the settings file failed to parse, the folder's workspace trust isn't accepted, or `disableAllHooks` / `allowManagedHooksOnly` is set.
   - Codex: the entry isn't trusted yet (`/hooks`), the project `.codex/` layer isn't trusted, or the event doesn't exist in Codex (`references/events.md`).

2. **Matched.** Compare the matcher with the real `tool_name`, including Codex's `apply_patch` and `spawn_agent` (`references/runtimes.md`). In Claude, check that an `if` rule matches the call and that the event honors `if` at all; on events that don't, the hook never runs.
   Done when you can say which field the matcher tested and why it matched or missed. For Claude, `CLAUDE_CODE_DEBUG_LOG_LEVEL=verbose` logs matcher counts.

3. **Started.** Wrap the command with `templates/debug-wrap.sh`, trigger the event once, and read `python3 scripts/hook-log.py`. To trigger it without touching the user's session, reproduce in a scratch copy with `scripts/live-test.py` (SKILL.md step 8); for a `hook-io.sh` hook its trace line is the same proof.
   Done when a log line exists for the run. No line means the command never started: the path doesn't resolve from the session's `cwd` (Codex sessions can start in a subdirectory), the script isn't executable, or the shebang's interpreter is missing.

4. **Answered.** Save the payload and replay it: `python3 scripts/test-hook.py "<command>" payload.json:<expected>`. Claude's debug log (`claude --debug-file <path>`) shows the raw output and any parse error.
   Done when the replay gives the outcome you expect. Usual causes when it doesn't:
   - The block used `exit 1`. Only exit 2 blocks.
   - The message went to stdout with exit 2. The agent sees only stderr.
   - Something besides the JSON object reached stdout (a shell profile line, a stray `echo`), so the JSON was read as plain text.
   - On Codex: `ask`, `continue`, or another unsupported field made the hook count as failed (`references/runtimes.md`).

5. **Understood.** If the agent sees the message but acts wrong, rewrite it: say what was refused and the exact next step, as facts.
   Done when a rerun of the triggering prompt produces the intended behavior.

## Slow hooks

1. Get durations: `python3 scripts/hook-log.py --summary`, or Claude's debug log `Hooks:` lines.
2. Replay the slow case with `test-hook.py --repeat 20` to get a stable median.
3. Apply `references/performance.md` from the top: `if` filter, fewer processes, early exit, async.

Done when the hook's median is under 50ms on the hot path, or the hook is async.

## Disable while fixing

- Claude: `"disableAllHooks": true` in settings, or `claude --settings '{"disableAllHooks": true}'` for one run.
- Codex: disable the entry in `/hooks`.

Remove the debug wrapper from the command when done.
