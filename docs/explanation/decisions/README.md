# Decisions

This folder holds Stratarc's design decisions: one page per choice that shaped the code, so a later contributor can see what was decided, what was considered instead and why. A record is not rewritten once it is accepted; a reversal is a new record that names the one it supersedes, and a narrow correction is noted at the top of the record it amends. Read the records that touch a part of the code before proposing to change it.

## Format

Each record is a file named `YYYY-MM-DD-short-title.md` with these sections: Status, Context (the situation and the forces at play), Decision (what was chosen), Alternatives (what else was considered and why it lost) and Consequences (what follows, good and bad). Add a record to the list below when it is accepted.

## Records

### Source Root and Deployment

- [A Runtime Is One Adapter File in the Source Root](2026-10-14-a-runtime-is-one-adapter-file-in-the-source-root.md)
- [Private Extensions Live in the Source Root](2026-10-09-private-extensions-live-in-the-source-root.md)
- [Private Checks Gate Deploy Only When the Source Root Opts In](2026-10-09-private-checks-gate-deploy-only-when-the-source-root-opts-in.md)
- [Projects Root from Config](2026-10-09-projects-root-from-config.md)
- [Diff Is a Read-Only Full Render](2026-10-09-diff-is-a-read-only-full-render.md)
- [Verify Defines Drift as a Dry Run](2026-10-09-verify-defines-drift-as-a-dry-run.md)
- [Sync Verifies and Rolls Back on Drift](2026-10-09-sync-verifies-and-rolls-back-on-drift.md)
- [Rollback Places Every Adapter Action Line](2026-10-10-rollback-places-every-adapter-action-line.md), which refines the verify and rollback record
- [Sync Records Changes at Its Write Points](2026-10-09-sync-records-changes-at-its-write-points.md)

### Registries and State

- [Adapter Registry and Support Ranges](2026-10-09-adapter-registry-and-support-ranges.md)
- [Version Detection Runs in an Isolated Home](2026-10-09-version-detection-runs-in-an-isolated-home.md)
- [Home Layout and Safe Writes](2026-10-09-home-layout-and-safe-writes.md)
- [The Home Is Dot Stratarc with an Environment Override](2026-10-09-the-home-is-dot-stratarc-with-an-environment-override.md), which settles the home location left open in the home layout record
- [Source Root Files Keep Their Mode and the Home Stays Private](2026-10-10-source-root-files-keep-their-mode-and-the-home-stays-private.md), which refines the file modes in the home layout record
- [Optional Change Log](2026-10-09-optional-change-log.md)
- [Setup Remembers the Source Root in the Home](2026-10-14-setup-remembers-the-source-root-in-the-home.md), which adds a step to the source root precedence

### Command Line

- [Exit Code Map](2026-10-09-exit-code-map.md)
- [Message Catalog with IDs](2026-10-09-message-catalog-with-ids.md)
