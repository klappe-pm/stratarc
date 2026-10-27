# AGENTS.md

Project instruction source for `<project>`.

The section order is shared across projects. Empty sections carry no additional project-specific instructions; project rules appear under the relevant section.

## source-and-sync

Edit `<source-root>/projects/roots/<project>/AGENTS.md`. The copies installed in the project checkout are generated and overwritten by synchronization.

stratarc deploys this source to the project checkout, together with this folder's `skills/`, `agents/`, `commands/`, `rules/` and `hooks/` where they exist. Preview the change from the source root before it is deployed:

```bash
stratarc diff --root "<source-root>"
```

## session-start

Read `<source-root>/projects/roots/control-plane.md` before acting. It is hand maintained until stratarc reconcile supports this layout.

## authority-order

Apply project validators, schemas, and CI gates first, this project instruction file second, and common user-scope rules third. Project instructions override common-tier rules; global-tier rules remain binding. Read any applicable plan in full before acting.

## project-context

What `<project>` is, who it serves, and what done means for a change here.

## intake

Where new work arrives and how it is triaged.

## data-strategy

What data the project holds, where it lives, and how sensitive it is.

## layout

The folders that matter and what each holds.

## workflow

How a change moves from branch to merge.

## conventions

Project rules that differ from or add to the common rules.

## validation

The commands that build, test and check this project, each with its own absolute working directory.

## gotchas

Known traps, each with the fix.
