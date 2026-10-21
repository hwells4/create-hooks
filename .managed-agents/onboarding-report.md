# Managed Agents onboarding report

## What is ready

This repository now has the baseline files Managed Agents expects. It can boot quickly, load Pi instructions, and use a migrated `create-hook` Pi skill based on the existing Claude hook-manager skill.

## What I changed

- Added Managed Agents setup, start, and stop scripts.
- Added Pi settings for the runtime.
- Added Pi-readable repository instructions.
- Copied the existing `create-hook` skill into `.pi/skills/create-hook` so Managed Agents can use it directly.
- Added a machine-readable onboarding status file.
- Added this plain-language report.
- Added a small `.pi/.gitignore` so generated Pi runtime caches are not accidentally committed.

## What I checked

- Checked for existing Managed Agents hooks and reports.
- Checked existing Pi settings, skills, and extensions.
- Checked the Claude plugin manifest, Claude command, hook skill, templates, helper scripts, and reference documents.
- Looked for Claude/Codex settings folders and repo-local agent instruction files.
- Confirmed this repository does not appear to need an app server, database, build step, or package install for normal use.

## Optional improvements

- Add Pi-native command helpers for analyzing hooks, validating hook settings, showing templates, and reading hook logs. This would make the old Claude slash-command workflow feel more natural in Managed Agents.
- Review which hook safety checks should become automatic Managed Agents guardrails. This can help prevent unsafe shell commands or sensitive-file access, but it should be approved because it changes what agents are allowed to do.
- Decide whether notification, MCP, or environment-variable examples should become real integrations. This can save time later, but it may require secrets or account permissions.

## What still needs a person

A person should review and merge the baseline pull request. Any deeper migration of command helpers, guardrails, MCP behavior, or external integrations should be approved before implementation.
