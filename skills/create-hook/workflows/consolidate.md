# Consolidate Hooks into a Dispatcher

A dispatcher is one registered hook that parses the payload once and runs every executable in `checks/`. It earns its place when several checks share one event and matcher:

- Adding a check means dropping a file, with no config edit and, in Codex, no new trust review.
- One process tree replaces several, all sharing one answer.
- Checks can't contradict each other's decisions.

Keep separate hooks when they differ in event, matcher, `if` rule, async-ness, or runtime: each of those is cheaper as its own config entry.

## Add a check to an existing dispatcher

1. Write `checks/<name>.sh`. It receives the raw payload on stdin and the exported variables `HOOK_EVENT`, `HOOK_TOOL`, `HOOK_CMD`, `HOOK_PATHS`, `HOOK_CWD`, `HOOK_RUNTIME`, and the rest of the `HOOK_*` set. It exits 0 to pass, or exits 2 with its message on stderr.
2. Make it executable.
3. Test the dispatcher, not the check alone: `python3 scripts/test-hook.py "<dispatcher command>" <cases>`.

Done when one case trips the new check, one passes, and an existing check's case still behaves.

## Create a dispatcher

1. **Pick the event.** Use the inventory (`scripts/validate-hooks.py --inventory`) to find the event and matcher with the most command hooks.
   Done when the hooks to merge share event and matcher, and none needs `async` or its own `if`.

2. **Lay out.** Next to the existing scripts, create `dispatcher.sh` (from `templates/dispatcher.sh`), `lib/hook-io.sh`, and `checks/`.
   Done when the layout exists.

3. **Migrate.** Turn each hook into a check: drop its own stdin parsing in favor of the `HOOK_*` variables, and turn its block into `echo "<message>" >&2; exit 2`. A check that returned other JSON (context, approve) stays a standalone hook.
   Done when every migrated check has a red and a green case passing through the dispatcher.

4. **Swap the config.** In each runtime's config, replace the merged entries with one entry for the dispatcher. Set its timeout to cover the slowest check.
   Done when the validator shows one entry where several were, and Codex users have re-trusted it.

5. **Remove.** `git rm` the standalone scripts the checks replaced.

## Dispatcher behavior

- PreToolUse: checks run in order, and the first finding denies. A deny needs only one reason.
- Other events: checks run in parallel, and all findings return together through exit 2 and stderr.
- A check that crashes (exit other than 0 or 2) is skipped, like a failed hook. Add `onFailure: "block"` to the dispatcher's Claude entry if any check is a hard guardrail.
