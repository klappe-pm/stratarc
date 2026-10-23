# Sync Verifies and Rolls Back on Drift

## Status

accepted, 2026-10-09

## Context

A sync that writes files and exits 0 says only that the writes did not fail. It does not say that the deployed result equals what the source describes. The [verify](2026-10-09-verify-defines-drift-as-a-dry-run.md) command can answer that, and the [change log](2026-10-09-optional-change-log.md) can hold the answer next to the change that caused it. The open question was how much of this a single sync run should do on its own, and what a failed check may undo.

## Decision

`stratarc sync --verify` runs verification for the change it just made, using the shared cause id of the run, and records `verified` or `drift` in the log. `--rollback-on-drift` adds a restore: before the write the run backs up the files each adapter will change and each runtime's deploy stamp, and on drift it puts them back, removes files the run created and exits 6. If a backup is missing it exits 5 and says which. Rollback covers runtime targets and stamps only; project checkouts are verified but never rolled back. Both flags are refused together with `--only`, `--check`, `--diff`, `--dry-run`, `--prune` and `--list`.

## Alternatives

Verifying on every sync by default was rejected because it doubles the render cost for the common case. Rolling back project checkouts too was rejected because those are working trees that may hold uncommitted edits, and restoring over them could lose work. Leaving rollback to the user and the home backups was rejected because the backups exist to make the automatic path possible.

## Consequences

A run can promise that what is deployed matches the source, or that nothing changed. The cost is a second render when the flag is on. A drift in a project checkout is reported but left for the user to resolve, which keeps the working tree safe.
