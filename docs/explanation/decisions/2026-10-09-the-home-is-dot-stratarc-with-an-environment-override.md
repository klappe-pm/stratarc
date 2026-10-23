# The Home Is Dot Stratarc with an Environment Override

## Status

accepted, 2026-10-09. Settles the open point in [home layout and safe writes](2026-10-09-home-layout-and-safe-writes.md).

## Context

The home layout record left open whether the XDG configuration path should be the primary home. The tool should install as a dot directory named after the product, and the code already resolves the home through one function.

## Decision

The home is `~/.stratarc`. `STRATARC_HOME` replaces the parent directory the dot directory lives in, which is how tests and containers redirect it. The tool does not read `XDG_CONFIG_HOME`. Source roots stay ordinary directories the user can commit anywhere.

## Alternatives

XDG as the primary home was rejected because one fixed location is easier to document, back up and find from an error message. Reading XDG only when set was rejected because two valid locations make every support question start with which one is in use.

## Consequences

The location is predictable on every platform. Users who keep dotfiles in XDG directories must set `STRATARC_HOME`. A later move to XDG would need a migration and a new record.
