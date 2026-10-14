# Setup Remembers the Source Root in the Home

## Status

accepted, 2026-10-14. Adds one step to the source root precedence in [the home is dot stratarc](2026-10-09-the-home-is-dot-stratarc-with-an-environment-override.md) and uses the `config.toml` that [home layout and safe writes](2026-10-09-home-layout-and-safe-writes.md) defines.

## Context

A bare `stratarc` now starts a guided setup when it finds no source root, and prints a status summary when it finds one. The source root was found only through `--root`, `STRATARC_SOURCE`, or a `stratarc.toml` at or above the current directory, then the current directory itself. After setup, a user who runs `stratarc` from their home directory would find no source root and be sent through setup again. The fallback to the current directory also let `stratarc sync` run in any directory, where it wrote a `control-plane.md` before failing.

## Decision

`stratarc setup` records the chosen source root as `source_root` in `~/.stratarc/config.toml`, keeping every other key. The source root precedence becomes `--root`, `STRATARC_SOURCE`, the nearest `stratarc.toml` at or above the current directory, the remembered root when it still holds `stratarc.toml`, then the current directory. A command that reads the source refuses the current directory when it holds no `stratarc.toml` (`msg-1009`), so the last step only names the directory in an error. `stratarc doctor` names the step that decided and reports a remembered root that no longer holds `stratarc.toml` (`msg-1013`). Only `setup` writes the key; `init` stays a pure scaffold.

## Alternatives

Printing an `export STRATARC_SOURCE=...` line for the user to add to a shell profile needs no engine change, but a forgotten export sends the user back into setup, and the variable outranks a nearer `stratarc.toml`, which surprises anyone with a second source root. A fixed default location needs no record, but takes the choice of directory away from the user. Writing the key from `init` as well would make a scratch `init` in a test or a tutorial silently change which root every later command reads.

## Consequences

`stratarc` works from any directory after setup, and a source root checked out under the current directory still wins over the remembered one. A remembered root that is moved or deleted is skipped, not followed, and `doctor` says so. Tests must not read the developer's real home, so the test suite redirects the remembered file into each test's temporary home.
