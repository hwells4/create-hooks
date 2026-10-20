# Brainstorm Hooks

Produce a short, ranked list of hooks worth building, each backed by evidence from the user's own sessions. A hook earns its place by catching something that has already gone wrong more than once.

## Purposes

| Purpose | Event | Catches |
|---|---|---|
| Guard | PreToolUse | an action that should never run, or needs a human (push to main, writing a secret, editing the hooks themselves) |
| Check | PostToolUse | a result to verify right after the action (lint the edited file, validate the written JSON) |
| Gate | Stop, SubagentStop | a turn that claims done too early (edited code, ran no tests) |
| Context | SessionStart, UserPromptSubmit, PreCompact + SessionStart `compact` | live state the agent lacks (branch, open tasks, the plan it held before compaction) |
| Approve | PermissionRequest | prompts the human always approves (read-only commands) |
| Observe | any event, `async` | facts to record for later (activity log, timings) |
| Notify | Notification (Claude), Stop | moments the human should look up (agent waiting, turn done) |

## Steps

1. **Tools.** Run `command -v cass herdr`. Both are optional.
   - cass (coding agent session search) indexes Claude Code, Codex, and other agents' sessions and keeps them after Claude Code deletes its transcripts (`cleanupPeriodDays`, default 30). With it, history goes back as far as its index; without it, the raw transcripts cover the last 30 days of Claude and whatever Codex has kept.
   - herdr runs the live tests in SKILL.md step 8 interactively.

   Done when you know which are installed and have told the user what each one adds, if missing.

2. **Mine.** Run `python3 scripts/mine-candidates.py --project <repo>`; add `--all` when the hooks will live at user scope. It groups the moments a human or a gate stopped the agent: rejections, interrupts, corrections, classifier denials, existing hook blocks, and saved approvals, each keyed by the action involved.
   Done when you have the report, and every group seen in 2 or more sessions is on a working list.

3. **Widen** (cass installed). For each working-list group and each "never" / "always" rule in CLAUDE.md or AGENTS.md:
   - count it: `cass search "<phrase>" --workspace <repo> --aggregate agent,date --limit 0 --json`;
   - read it: `cass expand <path> --line <n> -C 3` on two samples, using the miner's `path:line` locations or the cass hits.

   A cass count is how often the phrase appears (docs, plans, and rules quoting it count too), not how often it ran or went wrong; only the instances you read are evidence.
   Done when each candidate has a count across agents and you have read two real instances of it.

4. **Ask.** One question to the user: "What do you check by hand after the agent says it's done?" Each answer is a Gate candidate.
   Done when the answers are on the list.

5. **Filter.** Keep a candidate when all three hold:
   - a script can decide it from the payload or a quick file read (otherwise it is a `prompt` hook, or a CLAUDE.md / AGENTS.md line);
   - it recurs: seen in 2 or more sessions, or named by the user;
   - a miss costs more than the hook's latency on every matching call.

   Drop what a gate already catches (auto mode's classifier, an existing permission rule) unless another mode or runtime needs it. A hook the agent keeps hitting ("hook" group) needs its rule stated in CLAUDE.md / AGENTS.md as well, so the agent stops trying.
   Done when every remaining candidate passes all three tests.

6. **Propose.** Give a ranked list, at most five, each with: the purpose from the table, the evidence (count, sessions, one quoted instance), and a draft spec line in the SKILL.md step 2 format.
   Done when the user has picked which to build. Each pick enters SKILL.md at step 2.
