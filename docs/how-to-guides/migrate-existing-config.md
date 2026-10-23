# Migrate Existing Config

You already have runtime directories you maintain by hand: a `~/.claude/CLAUDE.md`, some commands, a hook or two, MCP servers. This guide moves that into one source root without losing what you have, in an order that lets you check each step before anything is overwritten.

## Start from a Scaffold

```bash
stratarc init ~/stratarc-source
```

Put the directory in git before you start. Everything below is a normal edit you can review and undo.

## Move the Instructions

Copy the contents of your main instruction file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` or similar) into `~/stratarc-source/AGENTS.md`, above the `RULES-DIGEST` markers. Leave the markers alone; `sync` fills the block between them. Split standing instructions that should be followed everywhere into rules, one file each: [Add a Rule](../how-to-guides/add-a-rule.md).

## Move Commands, Agents, Skills and Hooks

Copy each file into the matching source directory, in the format described in [Add a Skill, Command or Agent](add-a-skill-command-or-agent.md) and [Add a Hook](add-a-hook.md). A command or agent file written for one runtime usually works as is for Claude Code, and Stratarc translates it for the others. Register hook scripts in `hooks/hooks.json`.

## Move Permissions

`permissions.json` holds one policy in Claude Code's rule syntax, which every adapter translates into its runtime's own enforcement. Copy your `allow`, `deny` and `ask` lists in, and list every runtime directory you deploy to under `runtimeDirectories`.

## Declare What Other Tools Installed

MCP servers, plugins, hook groups and skills that another tool installs are not yours to author, but Stratarc should know about them so it does not treat them as strays. List them in `components.json`: an `mcp_servers` entry per server, a `plugins` entry per plugin, a `foreign_hooks` entry with a `match` for each hook group another tool registers, and a `third_party_skills` entry for each skill directory it installs. Reference secrets as `secret://namespace/key`, never as values; Stratarc refuses a token-shaped literal.

## Check Before You Write

```bash
cd ~/stratarc-source && stratarc validate --strict
```

```bash
cd ~/stratarc-source && stratarc diff
```

`validate` catches a misspelled tool name, a bad registry entry or a rule with no binding section. `diff` shows every change to every runtime. Read it. Then:

```bash
cd ~/stratarc-source && stratarc check
```

`check` lists what each runtime holds that your source does not own, under headings such as orphan, undeclared and foreign hook group. Each line is either something to move into the source, something to declare in `components.json`, or something to leave alone.

## Deploy

```bash
cd ~/stratarc-source && stratarc sync --verify --rollback-on-drift
```

The first deploy writes only files the source produces and merges into your settings files without removing entries it does not own. With `--rollback-on-drift` the runtime directories are put back if the result does not match. From here on, edit the source and not the runtime directory: a later sync overwrites a hand edit to a file Stratarc owns.
