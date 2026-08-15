# Agent compatibility

This repository follows the portable Agent Skills layout: a directory named
`agy-image` containing an exact-case `SKILL.md` with `name` and `description`
frontmatter. The skill body and relative resources are shared by every client;
no client-specific prompt fork is required.

## Install

Run the bundled installer from a clone of this repository:

```bash
python3 scripts/install_skill.py --agent all
```

Use `--scope project --project-root <path>` for a repository-local installation.
Use `--dry-run` to inspect destinations and `--force` only to replace an existing
copy of this same skill.

The installer copies files instead of creating symlinks so file watchers and
Windows clients behave consistently.

## Discovery locations

| Client | User scope | Project scope |
|---|---|---|
| Codex | `~/.codex/skills/agy-image/` | `.agents/skills/agy-image/` |
| Claude Code | `~/.claude/skills/agy-image/` | `.claude/skills/agy-image/` |
| Universal Agent Skills | `~/.agents/skills/agy-image/` | `.agents/skills/agy-image/` |
| Gemini CLI | `~/.gemini/skills/agy-image/` | `.gemini/skills/agy-image/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/agy-image/` | `.github/skills/agy-image/` |
| OpenClaw | `~/.openclaw/skills/agy-image/` | `.openclaw/skills/agy-image/` |

Restart the client or reload skills after installation. Gemini CLI can also use
`gemini skills link <clone-path>` during development.

Clients that understand the Agent Skills standard can load the root directory
directly even if they are not listed above. For older agents that only understand
`AGENTS.md`, instruct the agent to read this repository's `SKILL.md` when an osu!
storyboard task requires a missing visual asset; automatic metadata-based triggering
is only available in native Agent Skills clients.

## Portability rules

- Keep only `name` and `description` in `SKILL.md` frontmatter.
- Keep the folder name equal to `agy-image`.
- Preserve the exact uppercase filename `SKILL.md`.
- Resolve bundled scripts and references relative to the skill directory.
- Run `scripts/runtime_probe.py` before generation; obey its selected launcher,
  absolute `agy` path, and translated path domain instead of assuming the agent
  host and generator host are the same.
- Do not assume an agent-specific shell. The generation wrapper itself must run
  in the Linux/WSL environment where `agy` is installed.

## Upstream documentation

- Agent Skills specification: <https://agentskills.io/specification>
- Claude Code skills: <https://code.claude.com/docs/en/skills>
- Codex skills: <https://developers.openai.com/codex/skills>
- Gemini CLI skills: <https://geminicli.com/docs/cli/using-agent-skills/>
- VS Code/Copilot skills: <https://code.visualstudio.com/docs/agent-customization/agent-skills>
