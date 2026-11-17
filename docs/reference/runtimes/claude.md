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

On 2026-11-17, Claude Code 2.1.326 accepted scratch adapter output through `claude doctor`, including rendered permission policy and hook registrations. The scratch home had no authenticated account or trusted workspace, so installation and account warnings were expected and allow rules remained inactive. This verifies configuration parsing, not permission enforcement, hook execution, plugin loading, model behavior or MCP connectivity. The [2.1.326 changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) identified no required rendering change from 2.1.325; the existing rendering is retained for older versions.

## Projects

A project checkout receives `AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `GEMINI.md` at its root, shared rules under `.claude/rules/`, skills under `.claude/skills/`, and a `settings.json` only when the project registers hooks of its own.
