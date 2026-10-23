# A Runtime Is One Adapter File in the Source Root

## Status

accepted, 2026-10-14

## Context

The promise of the tool is one configuration for any runtime, and five runtimes ship with it. A sixth runtime appears every few months, and a user should not have to wait for a release or fork the package to manage one. Before this record the registry listed only the adapters inside the package, so enabling `[runtimes.acme]` in `stratarc.toml` made `validate` and `sync` pass and write nothing.

## Decision

A runtime is one Python file, `adapters/<name>.py` in the source root, with the same contract as a packaged adapter: a literal `RUNTIME` dict naming the runtime, its target directory under the home, its hook registry file and the canonical hook events it handles, plus `sync(source, target, dry_run)` and `owned_outputs(source, target)`. The registry reads the `RUNTIME` constant of every file without importing it, then sync imports the file by path. `stratarc adapter new <name>` writes a working starting point and lists the new directory in `permissions.json`. The directory is read only when the source root has a `stratarc.toml`, so an unrelated `adapters/` folder is never treated as one.

Two refusals keep the failure loud. A `[runtimes.<name>]` table that no adapter provides stops `sync` and `validate --strict` with a message naming the missing file, and a source adapter that reuses a packaged runtime name is refused.

## Alternatives

- Python entry points. Rejected: a source root is a directory of configuration, not an installable package.
- A plugin directory in the home. Rejected: it would make the same source root behave differently on two machines.
- Registering a manifest only, as `adapter register` does. Rejected as the mechanism: it records version ranges for an adapter but loads nothing, so it cannot add a runtime.
- Silently ignoring an enabled runtime without an adapter. This was the defect.

## Consequences

- A new runtime travels with the source root and is reviewed in the same commit as the files it renders.
- A source adapter runs arbitrary Python at sync time, so owning the source root is a trust decision, the same as for private extensions.
- The runtime's directory must be listed in `permissions.json`, which `adapter new` does and `sync` enforces.
