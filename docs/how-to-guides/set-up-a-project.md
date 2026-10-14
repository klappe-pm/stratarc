# Set Up a Project

Most of your configuration is user-wide. This guide shows how to give one project checkout its own instructions and rules, choose which shared items reach it, and keep a project out of the way. Stratarc calls the project-specific part the project-local configuration, and it lives in `projects-root/<project>/` in your source root.

## Tell Stratarc Where Your Projects Are

Set `projects_root` in `stratarc.toml` to the directory that holds your checkouts:

```toml
projects_root = "~/code"
```

Every directory under it that has a `.git` entry is a project. The checkouts can sit directly in that directory (a flat layout), or inside status folders named `active`, `new`, `inactive`, `archived` and `external`. In a flat layout every checkout is active. With status folders, only `active` projects receive configuration, so moving a project to `archived/` stops delivery to it. A checkout can also sit one grouping folder down, such as `~/code/work/api`. The default is `~/projects`. You can override it for one command with `--projects-root`.

## Add Project-Local Files

Create a directory named exactly like the checkout:

```bash
mkdir -p ~/stratarc-source/projects-root/notes-cli/rules
```

It mirrors the source root's own layout for the pieces that apply to that project only:

| path | holds |
| --- | --- |
| `projects-root/<project>/AGENTS.md` | the project's instructions |
| `projects-root/<project>/rules/` | rules only this project follows |
| `projects-root/<project>/skills/`, `commands/`, `agents/` | items only this project has |
| `projects-root/<project>/hooks/hooks.json` | hooks for this project |

Rules follow the same format as top-level rules: an H1 equal to the filename stem and a `## binding` section.

## Choose What Else Reaches the Project

```bash
cd ~/stratarc-source && stratarc reconcile
```

`reconcile` finds the checkout and gives the project a column in every table of `control-plane.md`. A shared skill, command or agent starts off in a project's column, and a rule follows its tier: `global` and `common` rules are on, `project` rules are off. Put an `x` in a cell to opt the project in to a shared item, or clear it to opt out of a `common` rule. See [Use the Control Plane](use-the-control-plane.md).

## Deploy

```bash
cd ~/stratarc-source && stratarc sync
```

```bash
cd ~/stratarc-source && stratarc projects --check
```

`sync` renders the user-level runtimes and then every active project. Inside a project it writes `AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `GEMINI.md` at the checkout root, rules and skills under `.claude/`, and skills under `.agents/`. Rules the user-level instructions already carry arrive as their binding section only, so a session does not read them twice. `projects --check` reports files that disagree with what delivery would write.

## Narrow a Project's Permissions

A project can carry its own `permissions.json` with a `projectScope` key that names the exact checkout and any worktrees it applies to:

```json
{
  "schemaVersion": 1,
  "policyVersion": 1,
  "defaultMode": "default",
  "projectScope": {
    "root": "/home/you/code/notes-cli",
    "worktrees": []
  },
  "allow": ["Read(/home/you/code/notes-cli/**)", "Edit(/home/you/code/notes-cli/**)"],
  "deny": ["Read(**/notes.db)"],
  "ask": ["Bash(git push *)"]
}
```

Paths must be absolute, the root's final component must be the project name, and the file cannot grant extra shared directories or bypass approvals. Shared denials still apply. `stratarc sync` rewrites the runtime permission files a project already has, such as `.claude/settings.json`, so they state this policy; it never creates one for an ordinary project.

## Keep a Repository Out

Some repositories should receive nothing, for example one you publish. List them in `projects-root/public-targets.json`, by directory name or `owner/repo`:

```json
{
  "targets": ["my-published-tool", "someone/their-repo"]
}
```

A listed checkout, or a linked worktree of one, gets no control-plane column, no delivered files and no permission rewrites. A file that exists but cannot be read stops the run instead of being treated as empty.
