# Private Checks Gate Deploy Only When the Source Root Opts In

## Status

accepted, 2026-10-09. Settles the open point in [private extensions live in the source root](2026-10-09-private-extensions-live-in-the-source-root.md).

## Context

A source root can load its own validator checks from `scripts/private/validate_checks.py`. The deploy gate runs the generic checks only, so a source root's own checks run under `stratarc validate` and never block a sync. A user who relies on their own checks to keep a deploy safe needs a way to make them block.

## Decision

The deploy gate runs the source root's private checks when `stratarc.toml` sets `[validate] gate_private = true`. The default is false, so a deploy depends only on the generic checks the package ships. A private check that raises or fails to load is an error finding, and under the gate it blocks the deploy with a message naming the file.

## Alternatives

Always gating on private checks was rejected because a stale or broken extension would block every sync for a reason outside the package. Never gating was rejected because it leaves a user's own safety checks advisory. A command-line flag only was rejected because the choice belongs to the source root and should not depend on who runs the sync.

## Consequences

A source root can turn its private checks into a gate with one line. The setting is part of `stratarc.toml`, so it is reviewed with the source it protects.
