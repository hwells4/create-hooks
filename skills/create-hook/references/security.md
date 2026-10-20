# Hook Security

Hooks run with the user's full permissions, on input the model wrote. Treat every payload field as untrusted.

## Script rules

- **Quote every expansion.** `"$path"`, never `$path`. Pass values to commands as arguments, and never build a command string from payload text for `eval`, `sh -c`, or `bash -c`.
- **Parse JSON with jq.** grep and sed miss escaped quotes and multi-line strings, and that gap is a bypass.
- **Resolve paths before deciding.** Compare absolute paths built from `cwd`; reject `..` segments and symlinks pointing outside the project when the decision depends on location.
- **Approve narrowly.** An auto-approver allows an explicit list of complete, single commands, and anything with `;`, `&`, `|`, `>`, `<`, backticks, `$(`, or a newline falls through to the human (`approve-safe.sh`).
- **Treat pattern blocklists as guardrails.** `rm -rf /` has endless spellings. Use them to catch mistakes, and back real boundaries with permission deny rules, `onFailure: "block"`, the Codex sandbox, or OS-level permissions.
- **Keep secrets out of output.** stdout and stderr reach the model and the transcript, and Claude replays injected context on resume.

## Configuration rules

- **Review before you run.** Project hooks execute for anyone who opens the repo: Claude after workspace trust, and in `claude -p` with no trust dialog at all. Codex runs them only after per-hook trust. Read `.claude/settings.json`, `.codex/hooks.json`, and the scripts they call before running an agent in a repo you didn't write.
- **Put personal hooks in personal files.** Use `.claude/settings.local.json` or user settings, so they stay out of commits.
- **Allowlist HTTP hooks.** Claude's `allowedHttpHookUrls` limits where payloads can be posted, and `httpHookAllowedEnvVars` limits which variables reach headers.
- **Pin shared policy centrally.** In an organization, managed settings (`allowManagedHooksOnly` in both runtimes) keep project and user hooks from overriding it.
