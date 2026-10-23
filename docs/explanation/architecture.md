# Architecture

This page explains how Stratarc turns one source root into a configuration for each enabled runtime, for a contributor who needs the shape of the pipeline before changing a stage of it. The [source layout](../reference/source-layout.md) describes the input; the [runtimes](../reference/runtimes/README.md) pages describe the outputs.

## The Idea

Every agent runtime wants the same few things in its own words: standing instructions, permissions, hooks, skills, commands and agents. Maintained by hand, five runtimes drift apart. Stratarc keeps one source root, a directory you put in git, and treats each runtime directory as generated output. Nothing in the runtime directories is authoritative, which is why a sync may overwrite what it owns.

## The Stages

1. Read and validate. Load `stratarc.toml`, resolve the registry of adapters, and run the validator over the source root. A sync stops here on an error.
2. Reconcile. Refresh `control-plane.md`, the table of which item reaches which scope, and re-embed the rules digest in `AGENTS.md`.
3. Stage. For each scope, build a staging directory that holds only the items the control plane selects: the instruction file, the selected rules, hooks, skills, commands and agents, the permission policy, and the MCP servers and plugins chosen. The whole output of the user-level scope exists before any of it is deployed.
4. Render. For each enabled runtime whose directory exists, call the adapter with the staging directory and the target. An adapter translates the staged tree into the runtime's native files and returns one line per change. In `check`, `diff` and `--verify` it is called in dry-run mode, which writes nothing.
5. Write. A real sync lets the adapters write, stamps each target with the policy version it deployed, and then delivers the active projects.

`prune` runs the reverse pass instead: it asks each adapter which directories it owns, lists what those directories hold that the current source does not produce, and removes it.

## The Pieces

- Adapters, one per runtime, in `stratarc/adapters/`, plus the ones a source root adds. They share helpers for copying with the executable bit, mirroring a directory, merging JSON and TOML without disturbing keys they do not own, and tracking what they own. See [Adapter Files](../reference/adapter-files.md).
- The registry, `stratarc/registry.py`, which holds a manifest for each adapter: the runtime versions it supports, the newest it was tested on and any deprecation. A deploy through an adapter that does not support the installed runtime stops before writing.
- The control plane, `stratarc/control_plane.py` and `stratarc/reconcile.py`. Reconcile owns the inventory and the defaults; the `x` cells belong to the user and are never overwritten.
- Staging, `stratarc/staging.py`, which makes the per-scope trees and renders the `${STRATARC_SOURCE}` token in rule pointers into a real path.
- The deploy stamp, `stratarc/deploy_guard.py`, which refuses to write an older permission policy over a newer one.
- The home, `~/.stratarc`, for backups, logs and registered manifests, written through one function that keeps a copy of anything it replaces.

## What Is Deliberately Not Here

Stratarc does not launch agents, resolve secrets, run a server or schedule anything. It reads a directory and writes directories. Anything outside that, such as a tool that injects a secret at launch, belongs to a runtime or to your own scripts, which is why configuration refers to secrets by name only. See the [Security Model](security-model.md).
