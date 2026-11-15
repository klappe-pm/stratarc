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

Cursor reads a hook file only when every entry is flat, so a grouped entry is flattened, including one already in the file. Tool names in a matcher are translated the way Cursor translates imported Claude Code hooks: `Bash` becomes `Shell` and `Edit` becomes `Write`.

## Hook Events

| canonical event | Cursor event |
| --- | --- |
| `PreToolUse` | `preToolUse` |
| `PostToolUse` | `postToolUse` |
| `SessionStart` | `sessionStart` |

`Stop`, `UserPromptSubmit`, `PostToolUseFailure`, `SubagentStart` and `SubagentStop` are not mapped and are dropped. The adapter lists them in `hook_events` as deliberate drops.

## Not Written

Skills, commands, agents, permissions and MCP servers are not rendered for Cursor. A sync names a selected MCP server it cannot render instead of dropping it silently.
