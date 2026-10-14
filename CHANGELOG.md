# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `stratarc` with no command starts a guided setup the first time: it creates or adopts a source root, enables the runtimes it finds installed, previews the first deploy and deploys only on an explicit yes. Once set up, it prints where the source root is and the commands to run next. Outside a terminal it prints the help.
- `stratarc setup`, the same guided setup on demand. It records the source root in `~/.stratarc/config.toml`, so later commands find it from any directory.
- `stratarc help [COMMAND]`, and examples in the help of every command.
- A mistyped command names the closest one (`stratarc synk` suggests `stratarc sync`).
- Every error line ends with a link to its entry in the error reference.

### Changed

- An argument a command does not take is reported against that command's usage, not the top-level one, and with `--json` every usage error prints one envelope (`msg-1010`, `msg-1011`, `msg-1014`).
- `init` ends by printing the commands to run next.

### Fixed

- A command run in a directory with no `stratarc.toml` at or above it, and no other source root configured, is refused with `msg-1009`. It used to treat that directory as a source root, and `sync` wrote a `control-plane.md` into it before failing. A source root you run commands from without `--root` or `STRATARC_SOURCE` now needs a `stratarc.toml`; an empty one uses the defaults.
- `stratarc doctor` reports that case as a problem, and reports a remembered source root that no longer holds `stratarc.toml` (`msg-1013`).
- The generated command reference shows a required option without brackets in its usage line, so `adapter deprecate` no longer presents `--reason` and `--end-date` as optional.

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
