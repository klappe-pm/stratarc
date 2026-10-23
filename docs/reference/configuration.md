# Configuration

This page documents `stratarc.toml`, the file in a source root that names the enabled runtimes, their target directories and the projects root, together with the environment variables that override them and the JSON Schemas that validate the other files in a source root. The environment variables are also listed in [CLI](cli.md).

## Stratarc.toml

`stratarc init` writes this file at the root of the source root with every key present and commented. A missing file yields the defaults; a malformed one stops the command with a message naming the file.

| key | type | default | meaning |
| --- | --- | --- | --- |
| `name` | string | `"stratarc"` | the name put on what Stratarc generates: marker comments, permission profile names, the deploy stamp file and the MCP ledger; lowercase letters, digits and hyphens, starting with a letter |
| `projects_root` | string | `"~/projects"` | the directory that holds your project checkouts; `~` expands to your home directory |
| `validate.gate_private` | boolean | `false` | whether the deploy gate also runs the checks in `scripts/private/validate_checks.py`; false gates a deploy on the built-in checks only, true makes a failing or broken extra check block the sync and names the file |
| `runtimes.<name>.enabled` | boolean | `false` for a table that omits it; a runtime with no table is enabled | whether `sync`, `check`, `diff` and `prune` act on this runtime |
| `runtimes.<name>.target` | string | the runtime's conventional directory | the directory the runtime reads its configuration from; `~` expands to your home directory |

The recognised runtime names and their default targets are `claude` (`~/.claude`), `codex` (`~/.codex`), `gemini` (`~/.gemini`), `cursor` (`~/.cursor`) and `opencode` (`~/.config/opencode`), plus any runtime with an adapter in `adapters/` in the source root. A `runtimes` table whose name matches no adapter is an error. See [Runtimes](runtimes/README.md) for what each receives.

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

Stratarc keeps machine state, not project state, in `~/.stratarc`: `config.toml` (settings such as `logging`, and `source_root`, the source root `stratarc setup` recorded), `adapters/` (registered adapter manifests), `state/`, `backups/`, `logs/` and `cache/`. Directories are mode 0700 and files 0600. A file written by a newer Stratarc is never rewritten by an older one. `stratarc doctor --clean` removes only old backups and the cache.

## Schemas

Three JSON Schemas ship with the package under `stratarc/data/schema/` and validate the JSON files in a source root.

| schema | validates |
| --- | --- |
| `hooks.schema.json` | `hooks/hooks.json`, the hook registry: each canonical event maps to a list of hook groups with an optional tool matcher and command hooks |
| `permissions.schema.json` | `permissions.json`, the single permission policy every runtime adapter translates |
| `components.schema.json` | `components.json`, the manifest of external components |

See [Source Layout](source-layout.md) for the keys of `permissions.json` and `components.json`.
