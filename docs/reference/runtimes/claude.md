# Claude

This page is the reference for what Stratarc writes into the Claude Code target, `~/.claude/` by default. Claude Code is the native format for the source, so most of this is a structured copy. The adapter is `stratarc/adapters/claude.py`.

## Target

`runtimes.claude.target` in `stratarc.toml`, default `~/.claude`. Claude Code is the one runtime `stratarc init` enables.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `AGENTS.md`, `CLAUDE.md`, `CODEX.md` | `AGENTS.md` with the rules digest | three identical copies |
| `settings.json`, `permissions` | `permissions.json` | the allow, deny and ask lists, `defaultMode`, `blockReadsOutsideWorkingDirectories`, and `additionalDirectories` joined with `runtimeDirectories`; `autoMode` is copied whole |
| `settings.json`, `hooks` | `hooks/hooks.json` | merged: groups that name a script Stratarc ships are replaced, groups from plugins or other tools are kept |
| `settings.json`, `enabledPlugins` | `components.json` plugins | an entry is true only when the `global` column selects it; plugins Stratarc did not enable are left as they were |
| `settings.json`, `model` and others | `runtime_settings.claude` in `components.json` | `model`, `subagent_model` and the `settings` object are passed through |
| `hooks/` | `hooks/*.sh` and `hooks/lib/` | executable bits kept |
| `skills/` | `skills/` | one directory per skill |
| `commands/` | `commands/*.md` | copied as written |
| `agents/` | `agents/*.md` | copied as written; a `model` alias is mapped through `runtime_settings.claude.aliases` |

## Not Written

User-level MCP servers live in `~/.claude.json`, outside the target. The sync orchestrator renders selected servers into that companion file, preserving entries it does not own; calling the adapter directly does not write the companion. Rules are not written as files at user scope, because the digest in `AGENTS.md` already carries them; inside a project, rules are written under `.claude/rules/`.

## Compatibility Evidence

On 2026-11-19, Claude Code 2.1.328 loaded real source policy rendered into a scratch home through `claude doctor` without an `Invalid settings` diagnostic. An invalid `permissions.defaultMode` control produced that diagnostic despite also exiting zero, so exit status alone does not establish acceptance. Synthetic `claude mcp get stratarc-fixture` discovered a local echo fixture and reported the expected closed connection. No authenticated session, real MCP connection, hook execution, permission enforcement, plugin loading or model behavior was verified.

The [2.1.328 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.328), [settings reference](https://code.claude.com/docs/en/settings-reference), [hook reference](https://code.claude.com/docs/en/hooks) and installed CLI help identify no required rendering change from 2.1.327. Existing rendering and support bounds are retained. The reviewed surface covers permission lists and mode, directory access, auto-mode guidance, sandbox disablement, hook registrations, plugin enablement, model and environment passthrough, MCP companions and instruction, skill, command and agent paths.

The release changes runtime behavior: Code Mode output no longer runs `UserPromptSubmit` hooks, managed `PostToolUse` hooks no longer run for calls refused before execution, sandbox startup failures are reported differently, and third-party providers gain auto-mode defaults. The existing `deniedMcpServers` passthrough also gains scope: `claude.ai <name>` denials now apply in cloud and self-hosted runner sessions. Rendering is retained; connector enforcement in those sessions remains unverified. These changes do not rename the adapter's keys. Native parsing does not verify those behaviors; in particular, a prompt hook must not be assumed to redact Code Mode output. See the [hook reference](https://code.claude.com/docs/en/hooks#userpromptsubmit) for the new boundary.

## Projects

A project checkout receives `AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `GEMINI.md` at its root, shared rules under `.claude/rules/`, skills under `.claude/skills/`, and a `settings.json` only when the project registers hooks of its own.
