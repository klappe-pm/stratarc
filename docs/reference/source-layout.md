# Source Layout

This page describes the source root that `stratarc init` creates: each file and directory, what it holds, which runtimes read it and the keys of the two JSON files that have many. The bundled template under `stratarc/data/templates/source-root/` is the authority for the shape, and [examples/notes-cli](../../examples/notes-cli/README.md) shows a populated one.

## Files

| path | holds | read by |
| --- | --- | --- |
| `AGENTS.md` | the instructions every agent session starts from, with a marked block where the rules digest is written | every runtime |
| `stratarc.toml` | the enabled runtimes, their targets and the projects root; see [Configuration](configuration.md) | Stratarc itself |
| `permissions.json` | the single permission policy, translated into each runtime's native allow, deny and ask lists | every runtime with a permission model |
| `components.json` | external components: MCP servers, plugins, foreign hook groups, third-party skills and dependencies | every runtime that supports the component |
| `control-plane.md` | generated tables of which item reaches which scope; see [Control Plane](control-plane.md) | Stratarc itself |

## Directories

| path | holds | format |
| --- | --- | --- |
| `rules/` | one Markdown file per standing rule, and `tiers.json` naming each rule's tier | an H1 equal to the filename stem and a `## binding` section |
| `hooks/` | `hooks.json`, the hook registry, and the scripts it names | [Add a Hook](../how-to-guides/add-a-hook.md) |
| `skills/` | one directory per skill | a `SKILL.md` with `name` and `description` frontmatter |
| `commands/` | one Markdown file per slash command | `description` frontmatter, optional `argument-hint` and `allowed-tools` |
| `agents/` | one Markdown file per subagent | `name` and `description` frontmatter, optional `tools` and `model` |
| `projects-root/` | one directory per project holding its project-local configuration | [Set Up a Project](../how-to-guides/set-up-a-project.md) |
| `adapters/` | one Python file per runtime of your own | [Adapter Files](adapter-files.md) |
| `scripts/private/` | optional extra validator checks and project renderers | `validate_checks.py` declares `VALIDATE_CHECKS`; `project_renderers.py` declares `register` |

Each directory the template creates holds a `README.md` describing the files that belong in it. A `README.md` is documentation and is never treated as a rule, command or agent.

## Permissions.json

| key | meaning |
| --- | --- |
| `schemaVersion` | always `1` |
| `policyVersion` | an integer you raise when a change must not be undone by an older checkout; a deploy refuses to write a lower version over a higher one |
| `defaultMode` | the runtime's default permission mode; `default` asks, anything that suppresses prompts is passed through |
| `codexApprovalPolicy` | `on-request` or `never` |
| `blockReadsOutsideWorkingDirectories` | passed to Claude Code's permissions object |
| `additionalDirectories` | directories outside the working directory the policy treats as yours |
| `runtimeDirectories` | the runtime configuration roots a sync may write into and that stay writable to agents; every enabled runtime's target must be listed |
| `codexNetwork` | `{"enabled": bool, "domains": {...}}` for Codex |
| `codexShellEnvironment` | `{"passthrough": [names]}`, the environment variables Codex passes to shell commands |
| `allow`, `deny`, `ask` | rule strings in Claude Code syntax, such as `Read(~/projects/**)`, `Bash(git status)` or `Edit(**/.env)` |
| `autoMode` | Claude Code's auto-mode guidance block, passed through whole |

## Components.json

A `version` of `1`, an optional `runtime_settings` object, and five sections, each a list of entries (or `null`):

| section | an entry declares |
| --- | --- |
| `mcp_servers` | an MCP server: `command` with `args`, `env` and `cwd`, or a `url` with `transport`, or `hosted: true` for a connector another account runs |
| `plugins` | a plugin: its `marketplace`, or a `path` for an OpenCode file plugin |
| `foreign_hooks` | a hook group another tool registers: the `match` text that finds it, and optionally a `registration` Stratarc renders |
| `third_party_skills` | skills another tool installs: its `installer`, and the directory names when one install makes several |
| `dependencies` | a command-line tool: `command`, `install`, a pinned `version`, and optionally `version_command` and `platform` |

Every entry carries `name`, `runtimes` (a list of runtime names), `owner` and `wanted`, and optionally `description`. An entry whose `owner` is the engine name (`stratarc` unless you changed it) is rendered into each listed runtime that supports it. Any other owner means another tool installs the component, so Stratarc only records that it is expected. `wanted: false` declares a component known and deliberately unwanted: `check` reports it as returned, and `prune` can remove it. A key an entry may not have is an error, and so is a literal that looks like a credential; write secrets as `secret://namespace/key`.

`runtime_settings.<runtime>` holds `model`, `subagent_model`, `aliases` (short names to the runtime's model names), `settings` (passed through into the runtime's own settings) and, for OpenCode, `provider`.

## Rules/tiers.json

```json
{
  "global": ["never-commit-local-databases.md"],
  "common": ["conventional-commit-messages.md"],
  "project": ["tests-use-a-temporary-directory.md"]
}
```

A rule that no tier names is not rendered. See [Add a Rule](../how-to-guides/add-a-rule.md).
