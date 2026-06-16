# Repository instructions for hwells4/create-hooks

This repository packages guidance and templates for creating Claude Code hooks. Keep changes focused on hook-manager documentation, templates, validation scripts, and migration support.

## Important conventions

- Analyze existing hook configuration before creating or changing hooks.
- Prefer a dispatcher pattern when multiple hooks target the same event. Add new checks under a dispatcher's `checks/` directory instead of adding many standalone hooks.
- For standalone Claude hooks, include a debug wrapper unless the user explicitly opts out.
- Always ask where a newly created Claude hook should be installed: project, user, or local-only.
- Validate hook scripts and settings after changes with `skills/create-hook/scripts/validate-hook.py` when applicable.
- Treat hooks as security-sensitive because they execute commands automatically. Validate inputs, quote shell variables, use absolute paths in settings, and protect secrets such as `.env`, credentials, keys, and private Git data.
- Avoid implementing command-blocking guardrails, external integrations, deployment behavior, destructive Git behavior, or secret handling unless the user has explicitly approved that migration work.

## Pi usage

- Use the `create-hook` skill when a user asks to create, analyze, debug, validate, or migrate Claude Code hooks.
- The original Claude command `/create-hook` is represented in Pi by the `create-hook` skill under `.pi/skills/create-hook`.
- There is no application server for this repository. Managed Agents startup should remain fast and launch-only.
