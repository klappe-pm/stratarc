# Add a Skill, Command or Agent

Skills, commands and agents are the three shared items a runtime loads on demand. This guide shows the file each one is, how to register it and how each runtime receives it.

## Skills

A skill is packaged instructions an agent loads when a task matches. Create `skills/<kebab-name>/SKILL.md`:

```markdown
---
name: write-changelog-entry
description: Draft a changelog entry from the current diff. Use when a change is ready to commit.
---

# write-changelog-entry

## steps

1. Run `git diff` to see what changed.
2. Write one line in the past tense that a user would understand.
```

`name` must equal the directory name. `description` matters most: runtimes match tasks against it, so say what the skill does and when to use it. Supporting files, such as references or scripts, sit beside `SKILL.md` in the same directory. A skill directory with no `SKILL.md` is an error unless `skills/sync-exclude.json` lists it.

## Commands

A command is a prompt a user invokes by name, as `/<kebab-name>`. Create `commands/<kebab-name>.md`:

```markdown
---
description: Run the test suite and summarize any failures.
argument-hint: "[test path or -k expression]"
allowed-tools: Bash, Read
---

Run the tests and report the result in a few plain sentences.
```

`description` is required. `argument-hint` and `allowed-tools` are optional, and a runtime that has no equivalent drops them.

## Agents

An agent is a subagent definition a session can delegate to. Create `agents/<kebab-name>.md`:

```markdown
---
name: diff-reviewer
description: Review the uncommitted changes for mistakes. Use when a change is ready.
tools: Read, Grep, Glob
model: sonnet
---

You review a diff; you do not edit files.
```

`name` must equal the filename stem. `tools` is a comma separated list from the runtime's own tool vocabulary, and `model` is a short alias such as `opus`, `sonnet` or `haiku`; `stratarc validate` checks the tool names. Map the aliases to each runtime's model names with `runtime_settings.<runtime>.aliases` in `components.json`.

## Register and Deploy

```bash
cd ~/stratarc-source && stratarc reconcile
```

`reconcile` adds a `skill:`, `command:` or `agent:` row to `control-plane.md` with the `global` column on and every project off. Put an `x` in a project's column to give that project the item as well, see [Use the Control Plane](use-the-control-plane.md). Then:

```bash
cd ~/stratarc-source && stratarc diff
```

```bash
cd ~/stratarc-source && stratarc sync
```

## What Each Runtime Receives

Where a runtime reads a different format, the file is translated rather than copied.

| item | Claude Code | Codex | Gemini CLI | Cursor | OpenCode |
| --- | --- | --- | --- | --- | --- |
| skill | `skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` | not deployed | `skill/<name>/SKILL.md` |
| command | `commands/<name>.md` | `prompts/<name>.md` | `commands/<name>.toml` | not deployed | `commands/<name>.md` |
| agent | `agents/<name>.md` | `agents/<name>.toml` | `agents/<name>.md` | not deployed | `agents/<name>.md` |

[Runtimes](../reference/runtimes/README.md) has one page per runtime with the details.
