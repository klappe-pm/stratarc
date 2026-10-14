# Use the Control Plane

The control plane is `control-plane.md` in your source root. It is a set of tables that records, for every item you author, which scope it reaches: the user-level runtimes (the `global` column) and each project. This guide shows how to read it, how to change what reaches where, and how to keep it current. The file format is in [Control Plane](../reference/control-plane.md).

## Read It

Each table is one kind of item, one row per item, one column per scope:

```markdown
## commands

| option | global | notes-cli |
|---|---|---|
| [command:test-summary](commands/test-summary.md) | x |  |
| [command:release-checklist](commands/release-checklist.md) | x | x |
```

An `x` means the item is on for that scope. Anything else, including an empty cell, means it is off. Here `/test-summary` is deployed to the user-level runtimes only, and `/release-checklist` also reaches the `notes-cli` project. The first cell of a row links to the source file.

## Change What Reaches Where

Edit a cell and save. The `x` marks are the one part of the file you edit by hand.

```bash
cd ~/stratarc-source && stratarc diff
```

```bash
cd ~/stratarc-source && stratarc sync
```

Clearing the `x` in a project's column removes that item from the project on the next sync, and clearing it in the `global` column removes it from the user-level runtimes. `diff` shows the removal before it happens.

## Keep It Current

Run `reconcile` after you add, rename or delete a source file or project:

```bash
cd ~/stratarc-source && stratarc reconcile
```

Reconcile adds a row for each new item with its default, drops the row of a deleted one, adds a column for a project it found and keeps every `x` you set. Defaults: a new skill, command, agent or hook is on for `global` and off for projects, and a rule follows its tier. `stratarc sync` runs the same step first, so a sync never works from a stale table. `stratarc reconcile --check` reports whether the file is stale without writing, and exits 6 if it is.

## Choose a Runtime Per Scope

The `runtimes` table has a `runtime:<name>` row for each adapter, including ones you added yourself. Clearing the `global` cell of a runtime keeps it out of the sync without touching `stratarc.toml`.

## Add a Project Column

A project gets a column when it has a checkout under your projects root and is not listed in `public-targets.json`. See [Set Up a Project](set-up-a-project.md). Each active project also receives a generated copy of its own column as `.docs/stratarc-control-plane.md`, a record of what the project was given. Do not edit it.

## What Not to Do

Do not add rows by hand. A row you type has no source file behind it, and the next reconcile removes it.
