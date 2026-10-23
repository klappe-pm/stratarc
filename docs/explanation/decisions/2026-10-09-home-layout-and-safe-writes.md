# Home Layout and Safe Writes

## Status

accepted, 2026-10-09

settled 2026-10-09 by [the home is `.stratarc`](2026-10-09-the-home-is-dot-stratarc-with-an-environment-override.md).

## Context

The tool keeps machine state (settings, adapter manifests, backups, logs, cache) apart from any project. That state is edited by commands and by hand, survives upgrades and can be written by a newer or older version of the tool. Losing or silently downgrading it would be costly. See [home_layout.py](../../../stratarc/home_layout.py).

## Decision

The `.stratarc` home holds `config.toml`, `adapters/`, `state/`, `backups/`, `logs/` and `cache/`. Directories are mode 0700 and files 0600, and every file carries a schema version. A file with a newer schema is never rewritten and the command exits 5. Every write first copies the file it replaces into `backups/`. A clean removes only backups and cache, and only with `--yes`; it keeps the newest 20 versions of each file plus anything under 30 days old.

## Alternatives

- Write in place with no backup. Simplest, but a bad write is unrecoverable.
- Silently migrate a newer file down. It would corrupt data written by a newer release.
- Let clean remove any state. It risks deleting user data such as registered adapter manifests, so only disposable directories are candidates.
- Use the XDG path only. Standard on some systems, but it splits the layout across platforms.

## Consequences

- A downgrade is safe: the old tool refuses to touch what it cannot understand.
- Backups grow until a clean runs, bounded by the keep rules.
- Secrets never live in the home; configuration refers to them by `secret://` reference.
