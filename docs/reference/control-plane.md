# Control Plane

The control plane is `control-plane.md` at the root of a source root. It is a Markdown file made of tables, written by `stratarc reconcile` and read by every adapter and every project delivery, that records which source item reaches which scope. This page describes its format. For using it, see [Use the Control Plane](../how-to-guides/use-the-control-plane.md).

## Scopes

A scope is a column. The first is `global`, which stands for the user-level runtime directories (`~/.claude` and the rest). Every other column is a project, named like its checkout. A project gets a column when it has a checkout under the projects root and is not a public target.

## Tables

After the introduction, a `projects` table and a short `configuration` note, the file holds one table per kind of item. A table's heading is its kind, and its first column, `option`, holds a link to the source file whose text is the row id.

| table | row ids | one row per |
| --- | --- | --- |
| `instruction-file` | `AGENTS.md` | the instruction file |
| `rules` | `rule:<name>` | file in `rules/`; this table also has a `tier` column |
| `hooks-<event>` | `hook:<name>` | hook script registered for that event; an event with no script has no table |
| `skills` | `skill:<name>` | directory in `skills/` with a `SKILL.md` |
| `commands` | `command:<name>` | file in `commands/` |
| `agents` | `agent:<name>` | file in `agents/` |
| `mcp-servers`, `plugins` | `mcp:<name>`, `plugin:<name>` | wanted MCP server or plugin in `components.json`; absent until one is declared |
| `project-local-configuration` | `project:AGENTS.md`, `project:rules`, and so on | project-local item under `projects-root/` |
| `runtimes` | `runtime:<name>` | adapter, shipped or in `adapters/` |

```markdown
## rules

| option | tier | global | notes-cli |
|---|---|---|---|
| [rule:never-commit-local-databases](rules/never-commit-local-databases.md) | global | x | x |
| [rule:conventional-commit-messages](rules/conventional-commit-messages.md) | common | x | x |
| [rule:tests-use-a-temporary-directory](rules/tests-use-a-temporary-directory.md) | project |  | x |
```

## Cells

An `x` in a cell opts the item in for that scope. Any other content, including an empty cell, opts it out. Reconcile never changes a cell that already exists. A new row gets its defaults:

| item | `global` | project |
| --- | --- | --- |
| rule in the `global` tier | on | on |
| rule in the `common` tier | on | on |
| rule in the `project` tier | off | off |
| skill, command, agent, hook | on | off |
| MCP server, plugin | off | off |
| runtime | on | off |
| project-local item | off | on for its own project |

## The Projects Table

```markdown
| project | status | tier | template | origin |
|---|---|---|---|---|
| notes-cli | active | normal | base | example-owner/notes-cli |
```

`status` comes from where the checkout sits: `active` for a checkout directly under the projects root or under `active/`, and the folder name (`new`, `inactive`, `archived`, `external`) otherwise. Only `active` projects receive configuration. `tier` is `low` for `archived` and `external` and `normal` for the rest. `origin` is the `owner/repo` of the checkout's `origin` remote when it is a GitHub URL.

## Per-Project Snapshots

Each active project also gets `.docs/stratarc-control-plane.md`, a generated copy of its own column, so a session inside the project can read what it was given. Reconcile writes it only from the primary checkout of the source root, never from a linked worktree. The file is rewritten on every reconcile and is not meant to be edited.

## Staleness

`stratarc reconcile --check` exits 6 when the file differs from what reconcile would write. A sync, a diff and a check print `control-plane: stale` when they find it out of date, and a sync fixes it before it renders.
