# Codex

This page is the reference for what Stratarc writes into the Codex target, `~/.codex/` by default. Codex reads different formats from Claude Code for permissions, commands and agents, so those are translated. The adapter is `stratarc/adapters/codex.py`.

## Target

`runtimes.codex.target` in `stratarc.toml`, default `~/.codex`.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `AGENTS.md` | `AGENTS.md` with the rules digest | byte copy |
| `config.toml` | `permissions.json` | sets `approval_policy` from `codexApprovalPolicy` and `default_permissions` to the engine name, and writes a permission profile between `BEGIN` and `END` marker comments; the profile extends `:workspace`, lists the workspace roots, and denies the paths your `deny` list names |
| `config.toml` | `codexNetwork`, `codexShellEnvironment` | network access and the environment variables passed to shell commands |
| `config.toml` | `runtime_settings.codex` | `model` and `subagent_model` |
| `config.toml` | project checkouts under the projects root | each is marked trusted so Codex honours its project configuration |
| `config.toml` | `components.json` MCP servers | `[mcp_servers.<name>]` tables for the servers Stratarc owns |
| `rules/<name>.rules` | the `Bash(...)` entries of `allow`, `deny` and `ask` | `prefix_rule` lines: `allow`, `forbidden` for deny and `prompt` for ask |
| `hooks.json` | `hooks/hooks.json` | the same shape as Claude Code, with script paths pointing into `~/.codex/hooks` |
| `hooks/` | `hooks/*.sh` | executable bits kept |
| `skills/` | `skills/` | the `SKILL.md` format is the same |
| `prompts/` | `commands/*.md` | Codex calls a command a prompt |
| `agents/<name>.toml` | `agents/*.md` | a role file with `name`, `description`, `developer_instructions`, and a `model` mapped through the aliases |

Keys in `config.toml` that Stratarc does not own, such as sections Codex rewrites when you change a setting in its interface, are left as they are. A sandbox mode that would disable the generated deny rules is removed, since permission profiles supersede it.

## Projects

A project checkout receives `AGENTS.md`, `CODEX.md`, and skills under `.agents/skills/`. Hooks registered for the project go to `.codex/hooks.json`.
