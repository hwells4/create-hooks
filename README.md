# Create Hooks

A skill for building lifecycle hooks that run in both Claude Code and Codex.

Hooks are scripts the agent runtime runs at fixed points: before a tool call, after a file edit, when a session starts, when the agent tries to stop. Each one reads a JSON payload on stdin and answers with an exit code or one JSON object. That's how you enforce rules, inject live context, auto-approve safe commands, and keep an agent working until the job is done.

Codex adopted Claude Code's hook contract almost field for field, which makes one script for both runtimes realistic. The catch is the gaps:

- Codex reports file edits as `apply_patch` with a patch string.
- Codex has no `ask` decision.
- Codex silently ignores `if` and `args`.

This skill handles those gaps for you.

## Install

Claude Code:

```
/plugin marketplace add https://github.com/hwells4/hwells4-marketplace.git
/plugin install create-hooks@hwells4-plugins
```

Codex:

```
codex plugin marketplace add hwells4/hwells4-marketplace
codex plugin add create-hooks@hwells4-plugins
```

Then ask for what you want: "block force-pushes to main", "remind the agent to run tests before it stops", "make my Claude hooks work in Codex". The skill also answers to `/create-hook`.

## What it does

| Ask | What happens |
|---|---|
| Create a hook | Inventories existing hooks, writes a one-line spec, picks the cheapest mechanism, writes the script from a template, tests it against both runtimes' payloads, registers it, validates |
| Debug a hook | Walks the chain from registered to matched, started, answered, and understood, stopping at the first broken link |
| Audit hooks | Gives a per-hook verdict: purpose, latency, overlaps, and runtime soundness |
| Consolidate | Merges several hooks on one event into a dispatcher with a `checks/` directory |
| Port | Moves hooks between Claude Code and Codex, labeling each one portable, adaptable, or no equivalent |

## What's inside

```
skills/create-hook/
  SKILL.md              routing, the create steps, rules every hook follows
  references/           events, handlers, I/O, runtime differences, config, performance, security
  workflows/            brainstorm, debug, audit, consolidate, port
  templates/            bash + jq hook scripts and prompt/agent handler configs
  templates/lib/hook-io.sh   parses stdin once and emits answers both runtimes accept
  fixtures/claude|codex/     real-shaped payloads for each event
  scripts/test-hook.py       runs a hook against fixtures; reports outcome and median latency
  scripts/validate-hooks.py  inventories and lints every hook a project runs, both runtimes
  scripts/hook-log.py        reads the debug-wrap.sh log (exit codes, durations)
  scripts/mine-candidates.py finds hook candidates in past Claude and Codex sessions
  scripts/live-test.py       proves a hook fires in a real session, in a throwaway repo copy
```

## Optional tools

The skill checks for these and builds on them when they're installed. Everything works without them.

- **[cass](https://github.com/Dicklesworthstone/coding_agent_session_search)** (coding agent session search) indexes sessions from Claude Code, Codex, and other agents, and keeps them after Claude Code deletes its transcripts (30 days by default). The brainstorm workflow uses it to count how often a candidate recurs and to read real instances of it.
- **[herdr](https://herdr.dev)** runs agents in managed terminal panes. `live-test.py --herdr` uses it to test decisions that only show in an interactive session: `ask` dialogs, permission prompts, notifications.

## Finding and proving hooks

`mine-candidates.py` groups the moments a human or a gate stopped the agent (rejected tool calls, interrupts, corrections like "no, don't...", auto mode denials, existing hook blocks, saved approvals) by the action involved, so the hooks worth building are the ones your history already asks for.

`live-test.py` copies the repo into a scratch git repo whose origin is a local bare repo, then runs one headless session (`claude -p` or `codex exec`) per case. Hooks built on `lib/hook-io.sh` append a trace line when `HOOK_TRACE` is set, so the result is the hook's actual decision in a real session, in either runtime.

## Templates

| Template | Does | Runtimes |
|---|---|---|
| `guard-bash.sh` | denies destructive commands, sends risky ones to a human | both |
| `guard-files.sh` | protects `.env`, keys, `.git/`, lockfiles (reads `apply_patch` paths too) | both |
| `post-edit-check.sh` | runs a fast per-file check after edits and hands failures back to the agent | both |
| `inject-context.sh` | adds branch and dirty files at session start | both |
| `track-activity.sh` + `stop-gate.sh` | keeps the agent working if it edited code without running tests | both |
| `approve-safe.sh` | approves plain read-only commands at the permission prompt | both |
| `notify.sh` | desktop notification | both |
| `failure-hint.sh` | turns known tool failures into a next step | Claude |
| `dispatcher.sh` | one hook running every script in `checks/` | both |
| `stop-check.prompt.json`, `stop-verify.agent.json` | model-judged stop conditions | Claude |

## Speed

A synchronous hook adds its runtime to every call it matches, so the templates are built for the hot path:

- one `jq` parse
- built-in regex matching
- no interpreter startup

A typical template runs in about 10ms. The same logic in Python takes about 19ms, and a bare Node process takes about 26ms. Claude's `if` field and `async` hooks avoid most of the cost; `references/performance.md` has the details.

## Tests

```
tests/templates.sh   # every template against both runtimes' fixtures, under macOS /bin/bash 3.2
tests/validator.sh   # validate-hooks.py against a project seeded with known-bad and known-good configs
tests/miner.sh       # mine-candidates.py against synthetic Claude and Codex transcripts
tests/live.sh        # live-test.py's scratch builder; LIVE=1 also runs real sessions in each runtime
```

## License

MIT
