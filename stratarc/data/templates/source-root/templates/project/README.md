# project

Scaffolding for a new project. It is part of the framework that becomes the stratarc 0.4.0 init default: nothing in it names a person, a machine or a path, and `<source-root>` stands for the source root (here `$HOME/projects/active/agent-runtime-config`). A project has two halves: its configuration source in this repo under `projects/roots/<project>/`, and its checkout under `~/projects/active/<project>/`, which receives generated instruction files and agent config from that source.

## steps

1. Copy `templates/project/roots/` to `projects/roots/<project>/` and replace every `<project>` in its `AGENTS.md`. Fill in the sections from `project-context` on and leave any that do not apply empty; keep `source-and-sync`, `session-start` and `authority-order` as they are.
2. Add the project's own skills, agents, commands, rules or hooks under `projects/roots/<project>/skills/`, `agents/`, `commands/`, `rules/` and `hooks/` only when it has them. Shared content stays in the root `skills/` and `rules/`.
3. Copy `templates/project/checkout/.gitignore` and `templates/project/checkout/local/` into the new checkout. The `.gitignore` applies the visibility model and keeps the generated instruction files out of the project's git.
4. Register the project: add its row to the projects table and its column to the deployment tables in `projects/roots/control-plane.md`, and its GitHub slug to `projects/roots/remotes.json`. A public repository also goes in `projects/roots/public-targets.json`, which keeps all private configuration out of it.
5. Preview with `stratarc diff --root "<source-root>"`, then deploy with `stratarc sync` when the operator asks.
6. Optional drift checks. Run `stratarc drift` to compare every checkout against the control plane. If the project keeps instruction files below its root, list them under `"nested"` in `projects/roots/<project>/surfaces.json`. To check the repository in its own CI, copy `templates/project/checkout/.github/workflows/agent-drift.yml` into the checkout. A finding that is intentional is waived in `projects/roots/drift-waivers.json` with a reason and an expiry date.

## generated-in-the-checkout

`AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `GEMINI.md` at the checkout root, and the project's agent config under the runtime folders (`.claude/`, `.agents/`, `.codex/`, `.cursor/`, `.gemini/`). Edit the source in `projects/roots/<project>/`, never these copies.
