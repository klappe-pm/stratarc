# OpenCode

This page is the reference for what Stratarc writes into the OpenCode target, `~/.config/opencode/` by default. OpenCode has no hook registry of its own, so hooks run through a small plugin that Stratarc deploys. OpenCode validates its configuration strictly: an unknown top-level key makes it refuse the whole file, so the adapter writes only keys the schema knows. The adapter is `stratarc/adapters/opencode.py`.

## Target

`runtimes.opencode.target` in `stratarc.toml`, default `~/.config/opencode`.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `AGENTS.md` | `AGENTS.md` with the rules digest | byte copy |
| `opencode.jsonc`, `permission` | `permissions.json` | an object keyed by tool (`read`, `edit`, `bash`, `external_directory`) with `allow`, `ask` and `deny` values, and `*` set to `ask` |
| `opencode.jsonc`, `model` and `provider` | `runtime_settings.opencode` | `provider` is a custom OpenAI-compatible provider, passed through |
| `opencode.jsonc`, `mcp` | `components.json` MCP servers | the servers Stratarc owns |
| `rules/` | the rules outside the `common` tier | kept for inspection; the digest in `AGENTS.md` carries the rest |
| `hooks/` | `hooks/*.sh` | executable bits kept |
| `hooks/hooks.json` | `hooks/hooks.json` | the registry the plugin reads, with script paths pointing into `~/.config/opencode/hooks` |
| `plugins/stratarc-hooks.ts` | the packaged bridge | runs the registered commands on OpenCode's events |
| `skill/` | `skills/` | the `SKILL.md` format is the same |
| `commands/` | `commands/*.md` | `argument-hint` and `allowed-tools` are dropped |
| `agents/` | `agents/*.md` | `mode: subagent`; tools not listed are denied |

## The Hook Plugin

`plugins/stratarc-hooks.ts` reads `hooks/hooks.json` and, for each OpenCode event, runs every command registered for the matching canonical event, with the payload on standard input in Claude Code's shape. OpenCode's lower-case tool names are mapped to the registry's (`bash` to `Bash`, `edit` and `write` to `Edit` and `Write`). A command that exits non-zero, or prints a JSON object with `hookSpecificOutput.permissionDecision` set to `deny`, blocks the tool call with the reason it gives. A command whose script was not deployed exits 127 and is skipped, so a missing optional hook never blocks a call. `session.created` runs `SessionStart`, and a child session is a subagent: it runs `SubagentStart` and `SubagentStop`.

The plugin runs inside OpenCode's own runtime and needs nothing extra installed. Other files in `plugins/` are yours and are never touched.
