# Gemini

This page is the reference for what Stratarc writes into the Gemini CLI target, `~/.gemini/` by default. Gemini CLI names hook events differently, writes commands as TOML and enforces permissions through a policy file. The adapter is `stratarc/adapters/gemini.py`.

## Target

`runtimes.gemini.target` in `stratarc.toml`, default `~/.gemini`.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `GEMINI.md` | `AGENTS.md` with the rules digest | byte copy |
| `settings.json`, `general.defaultApprovalMode` | `permissions.json` | the approval mode derived from `defaultMode` |
| `settings.json`, `model.name` | `runtime_settings.gemini.model` | Gemini CLI has no runtime-wide subagent model, so `subagent_model` is named in the sync output and not written |
| `settings.json`, `mcpServers` | `components.json` MCP servers | the servers Stratarc owns |
| `settings.json`, `hooks` | `hooks/hooks.json` | merged with hooks you added by hand |
| `policies/<name>-permissions.toml` | `permissions.json` | one `[[rule]]` per tool and decision, with priorities, generated from `allow`, `deny` and `ask` |
| `hooks/` | `hooks/*.sh` | executable bits kept |
| `skills/` | `skills/` | the `SKILL.md` format is the same |
| `commands/<name>.toml` | `commands/*.md` | the body becomes `prompt` and the description becomes `description` |
| `agents/<name>.md` | `agents/*.md` | frontmatter rewritten to Gemini CLI's schema, with tool names translated |

## Hook Events

| canonical event | Gemini CLI event |
| --- | --- |
| `PreToolUse` | `BeforeTool` |
| `PostToolUse` | `AfterTool` |
| `SessionStart` | `SessionStart` |
| `Stop` | `AfterAgent` |
| `UserPromptSubmit` | `BeforeAgent` |

`SubagentStart`, `SubagentStop` and `PostToolUseFailure` have no Gemini equivalent and are dropped with a note. A timeout in seconds becomes milliseconds.

## Projects

A project checkout receives `GEMINI.md` at its root.
