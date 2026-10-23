# Adapter Files

An adapter translates the staged source into one runtime's native files. Five ship in the package, and a source root adds its own in `adapters/<name>.py`. Both kinds use the same file contract, described here. For a walkthrough, see [Add a Runtime](../how-to-guides/add-a-runtime.md).

## Where They Are Found

The registry reads the packaged adapters, then every `*.py` file in the source root's `adapters/` directory whose name does not start with an underscore or end in `.test.py`. The directory is considered only when the source root has a `stratarc.toml`. A source adapter that reuses the name of a packaged runtime is refused.

The registry reads the `RUNTIME` constant of each file with `ast.literal_eval`, without importing it, so listing runtimes costs no import. A file whose `RUNTIME` is missing or malformed stops the command with a message naming the file. Sync imports a source adapter by file path when it needs it.

## RUNTIME

A module-level dict literal:

| key | type | meaning |
| --- | --- | --- |
| `name` | string | the runtime name; must equal the file name without `.py`, and is lowercase letters, digits and hyphens |
| `target` | string | the runtime's directory relative to the home, such as `.claude` or `.config/opencode`; no leading `/` or `~`, no `..` |
| `hook_registry` | string or `None` | the file under the target that holds hook registrations, such as `settings.json`, or `None` when the runtime has no JSON registry |
| `hook_events` | list of strings | the canonical hook events the adapter handles, a deliberate drop included |

Any other key is an error. A sync refuses a runtime that is missing an event the staged `hooks/hooks.json` registers.

## Sync

```python
def sync(source: Path, target: Path, dry_run: bool = False) -> list[str]:
```

`source` is the staged tree for the user-level scope. It holds only what the control plane selected, laid out as the source root is: `AGENTS.md`, `rules/` (with `tiers.json`), `hooks/` (with `hooks.json` rewritten for the claude path prefix and `lib/`), `skills/`, `commands/`, `agents/`, `permissions.json`, and `components.json` reduced to the selected MCP servers and plugins. `target` is the runtime directory.

The function writes what the runtime needs and returns one human-readable line per change. When `dry_run` is true it must write nothing and return the lines it would have produced, because `diff`, `check`, `--verify` and rollback all depend on that. It should be idempotent: a second run on an unchanged tree returns no lines.

Helpers in `stratarc.adapters._common` copy a file while keeping the executable bit, mirror a directory without deleting extra files by default, and rewrite the Claude hook path prefix for a runtime. The shipped adapters are the reference for format work.

## Owned_outputs

```python
def owned_outputs(source: Path, target: Path) -> list[OwnedDir]:
```

Returns the target directories the adapter owns and the names it puts in them, computed the same way `sync` computes them. `OwnedDir(kind, path, names)` takes a label such as `"command"`, the absolute directory and the set of file names (or, for per-item directories such as skills, directory names). `check` reports anything else in an owned directory as an orphan, and `prune` deletes it. A function that returns `[]` owns nothing, and `check` then reports nothing about the runtime's directories.

## Optional: External_inventory

An adapter may also define `external_inventory(target)` returning a list of `Item` records describing what the runtime holds that the source does not own: MCP servers, plugins, skills, foreign hook groups. `check` and `prune` use it to report items as declared, undeclared or returned against `components.json`. See `stratarc/adapters/_inventory.py` for the record type.

## Manifests

Each adapter also has a manifest used for version support: the runtime versions it supports, the newest one it was tested on, and a deprecation record. The packaged adapters carry theirs in `stratarc/adapters/_supports.py`, and a source adapter gets a permissive one derived from its file. `stratarc adapter register` stores a stricter manifest under `~/.stratarc/adapters/<name>/manifest.json`, and `stratarc adapter status` compares every manifest with the installed runtime. A manifest never adds a runtime; only an adapter file does.
