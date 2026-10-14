# Diff Is a Read-Only Full Render

## Status

accepted, 2026-10-09

## Context

A user about to deploy wants to see what a sync would change before it changes anything. A summary that guessed at changes from file timestamps or a list of inputs could disagree with the real result, and a preview that wrote to the runtime directories would not be a preview.

## Decision

`stratarc diff`, and `sync --dry-run` without `--prune`, stage the source and run every adapter in check mode, which is the same render a sync performs, and print what would change. Deployed paths are shown with `~` for the home directory and never as staging paths, so the output is the same on every run. The command writes nothing and exits 0 even when it finds drift, because a diff reports a difference and is not a test. `stratarc check` is the command that gates: it exits 6 on drift. The flag handling is in [sync.py](../../../stratarc/sync.py) and the exit codes are listed in the [command reference](../../reference/cli.md).

## Alternatives

- Compare file timestamps or input hashes. Rejected: it can disagree with the real render and cannot show what a file would contain.
- Make `diff` exit non-zero on drift. Rejected: a script that only wants to read the preview would need to ignore the status, and `check` already gates.
- Combine `--dry-run` with `--prune` into the diff. Rejected: a prune lists what it would delete, which is a different report, so that pair keeps its own meaning and the combination of `--diff` with `--prune` is refused.

## Consequences

- The preview and the sync cannot drift apart, because they share the render.
- The cost of a diff is the cost of a full render, with no shortcut.
- Drift handling is split by command: `diff` reads, `check` decides, and a CI job that wants to fail on drift runs `check`.
