# Configure Runtimes

This guide shows how to choose which runtimes receive your configuration, move a runtime's target directory, and keep a runtime out of a sync. A runtime is any agent tool Stratarc has an adapter for: the five that ship with it, plus any you add in [Add a Runtime](add-a-runtime.md).

## See What Is Available

```bash
cd ~/stratarc-source && stratarc sync --list
```

The list names every runtime, its target directory and whether that directory exists. A sync writes only into a target that exists, so a runtime you have not installed is skipped without an error.

## Enable or Disable a Runtime

Each runtime has a table in `stratarc.toml`:

```toml
[runtimes.claude]
enabled = true
target = "~/.claude"

[runtimes.codex]
enabled = false
target = "~/.codex"
```

`enabled = false` keeps the runtime out of `sync`, `check`, `diff` and `prune`. A runtime with no table at all is treated as enabled, as long as its target exists. A table for a runtime that has no adapter is an error, not a silent skip: `stratarc sync` stops and `stratarc validate --strict` exits 1, naming the missing adapter file.

## Move a Target

Set `target` to the directory the runtime reads its configuration from. `~` expands to your home directory.

```toml
[runtimes.opencode]
enabled = true
target = "~/dotfiles/opencode"
```

A target must also appear in `runtimeDirectories` in `permissions.json`, the list of directories a sync may write into. A sync refuses a target that is missing from it and names the runtime:

```json
{
  "runtimeDirectories": ["~/.claude", "~/dotfiles/opencode"]
}
```

## Deploy to One Runtime

```bash
cd ~/stratarc-source && stratarc sync --only codex
```

`--only` also works with `check`, `diff` and `prune`. It skips project delivery, so it is a quick way to try a single adapter.

## Choose Per Scope in the Control Plane

The control plane has a `runtime:<name>` row for each runtime. The `global` column decides whether the runtime receives anything at all; an empty cell skips it the way `enabled = false` does. See [Use the Control Plane](use-the-control-plane.md).

## Try a Runtime Against a Scratch Home

Point `--home` at an empty directory to see exactly what a runtime would receive, without touching your real directories:

```bash
cd ~/stratarc-source && mkdir -p /tmp/try/.codex && stratarc --home /tmp/try sync --only codex
```

Then look in `/tmp/try/.codex`. [Runtimes](../reference/runtimes/README.md) lists what each one receives.
