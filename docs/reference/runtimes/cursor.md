# Cursor

This page is the reference for what Stratarc writes into the Cursor target, `~/.cursor/` by default. Cursor receives the selected rules and the hooks. The adapter is `stratarc/adapters/cursor.py`.

## Target

`runtimes.cursor.target` in `stratarc.toml`, default `~/.cursor`.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `rules/<name>.md` | the rules the control plane selects | one file each, README excluded; Cursor has no instruction file to carry the digest |
| `hooks.json` | `hooks/hooks.json` | version 1 with flat entries per event, each `{command, matcher, timeout}` |
| `hooks/` | `hooks/*.sh` | executable bits kept |
| `mcp.json` | selected MCP servers in `components.json` | source-owned entries are reconciled and other entries preserved |

Cursor reads a hook file only when every entry is flat, so a grouped entry is flattened, including one already in the file. Tool names in a matcher are translated the way Cursor translates imported Claude Code hooks: `Bash` becomes `Shell` and `Edit` becomes `Write`.

## Hook Events

| canonical event | Cursor event |
| --- | --- |
| `PreToolUse` | `preToolUse` |
| `PostToolUse` | `postToolUse` |
| `SessionStart` | `sessionStart` |
| `SessionEnd` | `sessionEnd` |

`Stop`, `UserPromptSubmit`, `PostToolUseFailure`, `SubagentStart` and `SubagentStop` are not mapped and are dropped. The adapter lists them in `hook_events` as deliberate drops.

## Not Written

Skills, commands, agents and permissions are not rendered for Cursor.

## Compatibility Evidence

On 2026-11-17, Cursor Agent 2026.11.13-eacade1 discovered scratch-rendered MCP definitions with `cursor-agent mcp list` and exited zero. Every server remained unapproved and no connection was made. This proves MCP discovery only. The CLI exposes no general configuration validator in its help, so hook parsing and execution, rule loading and server connectivity remain unverified at this version. Existing rendering regressions cover the unchanged flat hook format documented in [Cursor Hooks](https://cursor.com/docs/hooks); the earlier event mapping and output remain intact for older versions.
