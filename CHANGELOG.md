# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 0.2.0 - 2026-10-14

The first release to carry the product as specified. Versions 0.1.0 and 0.1.1 were withdrawn and are not available.

### Added

- `stratarc init`, `doctor`, `sync`, `check`, `diff`, `prune`, `reconcile`, `validate`, `projects`, `gen-rules-digest`, `components` and `adapter`.
- Adapters for Claude Code, Codex, Gemini CLI, Cursor and OpenCode, rendering instructions, rules, hooks, skills, commands, agents, permissions, MCP servers and plugins from one source root.
- Your own runtimes: `stratarc adapter new <name>` writes `adapters/<name>.py` in the source root, and sync, check, diff and prune manage it like the shipped ones. A `[runtimes.<name>]` table with no adapter is now an error, where it used to be ignored.
- A control plane (`control-plane.md`) recording which source item reaches which scope, maintained by `stratarc reconcile`.
- Project delivery for checkouts that sit directly under the projects root, or under `active/`, `new/`, `inactive/`, `archived/` and `external/` status folders.
- Verified deploys: `sync --verify` and `sync --verify --rollback-on-drift`, and a stamp that refuses to write an older permission policy over a newer one.
- `check` and `diff` report a rule added or edited since the last sync, before any sync re-embeds the rules digest.
- A sync adds and updates files and never deletes; `prune` removes what the source no longer produces.
- A worked example in `examples/notes-cli/` and documentation in `docs/`, arranged by Diátaxis quadrant.
