# Configuration

This page documents `stratarc.toml`, the file in a source root that names the enabled runtimes, their target directories, the projects root, the source root's layout and the optional workflow module, together with the environment variables that override them and the JSON Schemas that validate the other files in a source root. The environment variables are also listed in [CLI](cli.md).

## Stratarc.toml

`stratarc init` writes this file at the root of the source root with every key present and commented. A missing file yields the defaults; a malformed one stops the command with a message naming the file.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `name` | string | `"stratarc"` | the name put on what Stratarc generates: marker comments, permission profile names, the deploy stamp file and the MCP ledger; lowercase letters, digits and hyphens, starting with a letter |
| `projects_root` | string | `"~/projects"` | the directory that holds your project checkouts; `~` expands to your home directory |
| `validate.gate_private` | boolean | `false` | whether the deploy gate also runs the checks in `scripts/private/validate_checks.py`; false gates a deploy on the built-in checks only, true makes a failing or broken extra check block the sync and names the file |
| `runtimes.<name>.enabled` | boolean | `false` for a table that omits it; a runtime with no table is enabled | whether `sync`, `check`, `diff` and `prune` act on this runtime |
| `runtimes.<name>.target` | string | the runtime's conventional directory | the directory the runtime reads its configuration from; `~` expands to your home directory |
| `layout.project_config_dir` | string | `"projects-root"` | the directory in the source root that holds one folder of project configuration per project; `stratarc init` writes `"projects/roots"` |
| `layout.control_plane` | string | `"control-plane.md"` | the control plane file, relative to the source root; `stratarc init` writes `"projects/roots/control-plane.md"` |
| `layout.local_dir` | string | `".docs"` | the folder in each project checkout that holds internal work product; `stratarc init` writes `"local"` |
| `layout.control_plane_managed` | boolean | `true` | false marks the control plane as maintained by hand, and `reconcile` then leaves it and the project snapshots alone |
| `workflows` | table | absent, the module is off | the optional workflow module; see [The Workflows Table](#the-workflows-table) |

The `layout` values are relative paths inside their root and may not contain `..`. An unknown `layout` key is an error. The defaults in the table are what a source root with no `[layout]` table gets, which is the layout Stratarc 0.3 scaffolded; a source root `stratarc init` writes today names the `projects/roots` layout explicitly. Every guide in these docs names the project configuration directory and the control plane by these keys' values, so read `projects/roots/` and `projects/roots/control-plane.md` as `projects-root/` and `control-plane.md` in a 0.3 source root.

The recognised runtime names and their default targets are `claude` (`~/.claude`), `codex` (`~/.codex`), `gemini` (`~/.gemini`), `cursor` (`~/.cursor`) and `opencode` (`~/.config/opencode`), plus any runtime with an adapter in `adapters/` in the source root. A `runtimes` table whose name matches no adapter is an error. See [Runtimes](runtimes/README.md) for what each receives.

## The Workflows Table

`[workflows]` in `stratarc.toml` sets the control plane defaults of the optional workflow module, and a project overrides them in `<layout.project_config_dir>/<project>/workflows.toml`, table by table. The module is off unless a layer sets `enabled = true`. `stratarc workflows check` validates both layers and `stratarc workflows show` prints the effective configuration. An unknown key is a problem.

| key | values | default |
| --- | --- | --- |
| `enabled` | `true` or `false` | `false` |
| `paths.plan`, `paths.handoff`, `paths.backlog`, `paths.reports` | non-empty strings | `PLAN.md`, `local/handoff.md`, `local/backlog.md`, `local/reports` |
| `claims.mode` | `plan`, `files` or `off` | `plan` |
| `gates.<action>` | `G0` to `G3`, never below the action's standing floor or, in a project, below the control plane's value | the floor: `local-edit` G0; `push-branch`, `open-pr`, `release-candidate` G1; `create-issue`, `merge-default-branch`, `deploy`, `publish`, `delete`, `external-repo-write` G2; `bypass-guard`, `settle-decision` G3 |
| `decision-records.enabled` | `true` or `false` | `false` |
| `decision-records.root`, `decision-records.index` | non-empty strings | `docs/decision-records`, `docs/decision-records/index.json` |
| `decision-records.domains` | list of non-empty strings | `architecture`, `content`, `design`, `data`, `integrations` |
| `decision-records.target-words` | positive integer | `300` |
| `decision-records.check` | `report`, `enforce` or `off` | `report` |
| `tickets.backend` | `github`, `backlog` or `off` | `backlog` |
| `automation.session-start`, `automation.session-stop`, `automation.ci` | `true` or `false` | `false` |
| `automation.pre-commit` | `report`, `enforce` or `off` | `report` |
| `automation.triage` | `on-demand`, `weekly` or `off` | `on-demand` |

## How Values Are Resolved

Everything is read when a command runs, never when the module is imported, so a flag or a test can redirect it.

| value | order |
| --- | --- |
| home | `STRATARC_HOME`, then `HOME`, then the platform home |
| source root | `--root`, then `STRATARC_SOURCE`, then the nearest directory at or above the current one that holds `stratarc.toml`, then `source_root` in `~/.stratarc/config.toml` when that directory still holds `stratarc.toml`, then the current directory; a command that reads the source refuses the current directory when it holds no `stratarc.toml` |
| projects root | `--projects-root`, then `STRATARC_PROJECTS_DIR`, then `projects_root` in `stratarc.toml`, then `~/projects` |
| name | `STRATARC_NAME`, then `name` in `stratarc.toml`, then `stratarc` |

## Environment Variables

| variable | effect |
| --- | --- |
| `STRATARC_HOME` | replaces the directory that `~` and the `.stratarc` home live under |
| `STRATARC_SOURCE` | the source root |
| `STRATARC_PROJECTS_DIR` | the projects root |
| `STRATARC_NAME` | the generated-name override |
| `STRATARC_HELD_PROJECTS` | the projects this machine holds, for a machine that has fewer checkouts than the shared control plane lists |
| `STRATARC_LOG` | `1` turns on the change log database; the human-readable log is always on |

## The Home Directory

Stratarc keeps machine state, not project state, in `~/.stratarc`: `config.toml` (settings such as `logging`, and `source_root`, the source root `stratarc setup` recorded), `adapters/` (registered adapter manifests), `state/` (including `deployed.json`, the deploy ledger `prune` reads), `backups/` (including `backups/prune/`, a copy of every file `prune` deleted, which `doctor --clean` keeps), `logs/` and `cache/`. Directories are mode 0700 and files 0600. A file written by a newer Stratarc is never rewritten by an older one. `stratarc doctor --clean` removes only old backups and the cache.

## Schemas

Three JSON Schemas ship with the package under `stratarc/data/schema/` and validate the JSON files in a source root.

| schema | validates |
| --- | --- |
| `hooks.schema.json` | `hooks/hooks.json`, the hook registry: each canonical event maps to a list of hook groups with an optional tool matcher and command hooks |
| `permissions.schema.json` | `permissions.json`, the single permission policy every runtime adapter translates |
| `components.schema.json` | `components.json`, the manifest of external components |

See [Source Layout](source-layout.md) for the keys of `permissions.json` and `components.json`.
