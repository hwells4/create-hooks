# Audit Hooks

Produce a verdict on every hook a project runs: what it does, what it costs, and whether it is sound in each runtime it's registered for.

## Steps

1. **Inventory.** Run `python3 scripts/validate-hooks.py --project <repo>`. This covers user, project, and local scopes in both runtimes.
   Done when every row of the inventory maps to a script or handler you have opened and read.

2. **Overlaps.** Group the hooks by event and matcher. Note:
   - two hooks on the same event and matcher that could disagree (Claude applies deny over defer over ask over allow);
   - three or more command hooks on one event, which is a candidate for `workflows/consolidate.md`;
   - the same logic registered at user and project scope.

   Done when each overlap is listed with the hooks involved.

3. **Cost.** For each hot-path hook, take a fixture from `fixtures/` and run `python3 scripts/test-hook.py --repeat 10`.
   Done when every synchronous hot-path hook has a median, and each over 50ms has a fix from `references/performance.md`.

4. **Soundness.** Check each script against the rules in SKILL.md and each config against `references/runtimes.md` for the runtimes it's registered in.
   Done when every validator WARN and ERROR has a fix or a stated reason to keep it.

5. **Report.** Give a table with one row per hook: event, matcher, runtime, scope, purpose, median ms, and findings. Below it, list proposed changes in priority order: broken first, then fail-open guardrails, then slow, then style.
