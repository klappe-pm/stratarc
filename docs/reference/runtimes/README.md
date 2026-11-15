# Runtimes

The agent runtimes Stratarc ships adapters for, with the default directory it deploys each one to and a page per runtime describing the files it writes. Each page is a reference: file names, formats and which part of the source root feeds each one. To manage a runtime that is not listed, see [Add a Runtime](../../how-to-guides/add-a-runtime.md).

| runtime | default target | page |
| --- | --- | --- |
| Claude Code | `~/.claude/` | [Claude](claude.md) |
| Codex | `~/.codex/` | [Codex](codex.md) |
| Cursor | `~/.cursor/` | [Cursor](cursor.md) |
| Gemini CLI | `~/.gemini/` | [Gemini](gemini.md) |
| OpenCode | `~/.config/opencode/` | [OpenCode](opencode.md) |
| Antigravity CLI | `~/.gemini/antigravity-cli/` | [Antigravity CLI](agy.md) |

The target for each runtime is set in `stratarc.toml`; see [Configuration](../configuration.md).

## What Each Runtime Receives

| source | Claude Code | Codex | Gemini CLI | Cursor | OpenCode | Antigravity CLI |
| --- | --- | --- | --- | --- | --- | --- |
| instructions and rules digest | `AGENTS.md`, `CLAUDE.md`, `CODEX.md` | `AGENTS.md` | `GEMINI.md` | not deployed | `AGENTS.md` | not deployed, reads `~/.gemini/GEMINI.md` |
| rules as files | project scope only | not deployed | not deployed | `rules/` | `rules/` | not deployed |
| permissions | `settings.json` | `config.toml` and `rules/` | `settings.json` and `policies/` | not deployed | `opencode.jsonc` | not deployed |
| hooks | `settings.json` and `hooks/` | `hooks.json` and `hooks/` | `settings.json` and `hooks/` | `hooks.json` and `hooks/` | `hooks/` and a plugin | not deployed |
| skills | `skills/` | `skills/` | `skills/` | not deployed | `skill/` | `skills/` |
| commands | `commands/` | `prompts/` | `commands/` | not deployed | `commands/` | not deployed |
| agents | `agents/` | `agents/` | `agents/` | not deployed | `agents/` | not deployed |
| MCP servers | not rendered, see below | `config.toml` | `settings.json` | not rendered | `opencode.jsonc` | not rendered |

Claude Code keeps user-level MCP servers in `~/.claude.json`, outside its configuration directory, and the MCP configuration of Cursor and Antigravity CLI is not rendered yet, so a sync names those servers in its output instead of writing them. Antigravity CLI also receives the default model, written to the `model` key of `settings.json` from `runtime_settings.agy`. A source adapter decides its own column.
