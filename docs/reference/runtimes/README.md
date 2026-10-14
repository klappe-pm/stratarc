# Runtimes

The agent runtimes Stratarc ships adapters for, with the default directory it deploys each one to and a page per runtime describing the files it writes. Each page is a reference: file names, formats and which part of the source root feeds each one. To manage a runtime that is not listed, see [Add a Runtime](../../how-to-guides/add-a-runtime.md).

| runtime | default target | page |
| --- | --- | --- |
| Claude Code | `~/.claude/` | [Claude](claude.md) |
| Codex | `~/.codex/` | [Codex](codex.md) |
| Cursor | `~/.cursor/` | [Cursor](cursor.md) |
| Gemini CLI | `~/.gemini/` | [Gemini](gemini.md) |
| OpenCode | `~/.config/opencode/` | [OpenCode](opencode.md) |

The target for each runtime is set in `stratarc.toml`; see [Configuration](../configuration.md).

## What Each Runtime Receives

| source | Claude Code | Codex | Gemini CLI | Cursor | OpenCode |
| --- | --- | --- | --- | --- | --- |
| instructions and rules digest | `AGENTS.md`, `CLAUDE.md`, `CODEX.md` | `AGENTS.md` | `GEMINI.md` | not deployed | `AGENTS.md` |
| rules as files | project scope only | not deployed | not deployed | `rules/` | `rules/` |
| permissions | `settings.json` | `config.toml` and `rules/` | `settings.json` and `policies/` | not deployed | `opencode.jsonc` |
| hooks | `settings.json` and `hooks/` | `hooks.json` and `hooks/` | `settings.json` and `hooks/` | `hooks.json` and `hooks/` | `hooks/` and a plugin |
| skills | `skills/` | `skills/` | `skills/` | not deployed | `skill/` |
| commands | `commands/` | `prompts/` | `commands/` | not deployed | `commands/` |
| agents | `agents/` | `agents/` | `agents/` | not deployed | `agents/` |
| MCP servers | not rendered, see below | `config.toml` | `settings.json` | not rendered | `opencode.jsonc` |

Claude Code keeps user-level MCP servers in `~/.claude.json`, outside its configuration directory, and Cursor's MCP configuration is not rendered yet, so a sync names those servers in its output instead of writing them. A source adapter decides its own column.
