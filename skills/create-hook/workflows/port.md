# Port Hooks Between Claude Code and Codex

Goal: the same behavior in the target runtime, or a named gap the user accepted.

## Steps

1. **Inventory the source.** Run `python3 scripts/validate-hooks.py --inventory --runtime <source>`.
   Done when each hook to port is listed with its event, matcher, handler type, and the fields it uses.

2. **Classify each hook** using `references/runtimes.md`:
   - **portable**: a command hook on an event both runtimes have, using only shared fields;
   - **adaptable**: needs a script or config change (file paths from `apply_patch`, `if` moved into the script, exec form to shell form, `ask` to deny, a `CLAUDE_PROJECT_DIR` path to the git root);
   - **no equivalent**: an event or handler the target lacks (Claude's PostToolUseFailure, Notification, prompt or agent handlers; Codex's Interrupt). Name the nearest substitute when one exists. Codex PostToolUse fires on failed Bash, for example, and a Codex Stop hook can notify.

   Done when every hook carries one label and, for the last group, a substitute or "none".

3. **Adapt scripts.** Move each script to `.agents/hooks/` with `lib/hook-io.sh`, and switch its parsing and answers to the helper. Any filtering that lived in `if` moves into the script.
   Done when no script reads `CLAUDE_PROJECT_DIR` directly or emits `ask` without going through `hook_ask`.

4. **Test both shapes.** For each script, run the same cases built from `fixtures/claude/` and `fixtures/codex/` with `scripts/test-hook.py`.
   Done when each decision lands identically in both, or differs only where `runtimes.md` says it must (ask becomes deny on Codex).

5. **Register in the target.** Write the target config (`references/config.md`) in shell form, with the target's path idiom. Keep the source config pointing at the moved scripts.
   Done when the validator passes for both runtimes.

6. **Report** the labels from step 2, the gaps the user is accepting, and the activation step (Codex: trust in `/hooks`).
