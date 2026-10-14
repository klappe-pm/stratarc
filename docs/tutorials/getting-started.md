# Getting Started

This tutorial takes you from an empty machine to a first deployment. You install the command, scaffold a source root, add one rule, preview the change and deploy it. It follows one path and explains only what that path needs. For every command see the [CLI reference](../reference/cli.md), and for every key in `stratarc.toml` see [Configuration](../reference/configuration.md).

## What You Need

- Python 3.11 or newer.
- `pipx`, or a virtual environment you are willing to install into.
- At least one supported runtime installed and run once, so its directory exists: Claude Code, Codex, Gemini CLI, Cursor or OpenCode.

## Install the Command

```bash
pipx install stratarc
```

```bash
stratarc --version
```

The [install guide](../how-to-guides/install.md) covers other install methods and upgrading.

## Scaffold a Source Root

Pick a directory that does not exist yet, or is empty:

```bash
stratarc init ~/stratarc-source
```

`init` writes the bundled template: `AGENTS.md`, `stratarc.toml`, `permissions.json`, `components.json`, `control-plane.md`, and the `rules/`, `hooks/`, `skills/`, `commands/`, `agents/` and `projects-root/` directories, each with a short README that says what belongs in it. It refuses to write into a directory that already holds files. This directory is your source of truth. Put it in git.

## Choose Your Runtimes

Open `~/stratarc-source/stratarc.toml`. There is one table per runtime. Set `enabled = true` for each runtime you use and leave the rest at `false`. A runtime is deployed to only when its directory already exists, so one you have not installed is skipped.

```bash
cd ~/stratarc-source && stratarc sync --list
```

The list shows each runtime and whether its target directory is present.

## Add a Rule

A rule is a short standing instruction. Create `~/stratarc-source/rules/greet-the-user.md`:

```markdown
# greet-the-user

## binding

Start each session by greeting the user by name.
```

List it in `~/stratarc-source/rules/tiers.json` so it is selected. The `global` tier applies everywhere:

```json
{
  "global": ["greet-the-user.md"],
  "common": [],
  "project": []
}
```

Tell Stratarc a source file was added:

```bash
cd ~/stratarc-source && stratarc reconcile
```

`reconcile` adds a row for the rule to `control-plane.md`, the table that records which items reach which scope. See [Use the Control Plane](../how-to-guides/use-the-control-plane.md) for how to read it.

## Preview the Change

```bash
cd ~/stratarc-source && stratarc diff
```

`diff` shows what a deployment would change in every enabled runtime and writes nothing. `stratarc check` runs the same comparison and exits 6 when anything is out of date, which is what a script wants.

## Deploy

```bash
cd ~/stratarc-source && stratarc sync
```

`sync` renders the source into each enabled runtime. It writes only the files it owns and leaves everything else in a runtime directory alone. Open the runtime's instruction file, for example `~/.claude/AGENTS.md`, and the rule is in the rules digest.

## Next Steps

- Move an existing configuration in: [Migrate Existing Config](../how-to-guides/migrate-existing-config.md).
- Add skills, commands, agents and hooks: [Add a Skill, Command or Agent](../how-to-guides/add-a-skill-command-or-agent.md) and [Add a Hook](../how-to-guides/add-a-hook.md).
- Give one project its own instructions: [Set Up a Project](../how-to-guides/set-up-a-project.md).
- See a complete source root: the [notes-cli example](../../examples/notes-cli/README.md).
- Understand what Stratarc protects: [Security Model](../explanation/security-model.md).
