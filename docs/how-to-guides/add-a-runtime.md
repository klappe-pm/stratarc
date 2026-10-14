# Add a Runtime

Stratarc ships adapters for five runtimes. If you use another agent tool, you add it yourself: a runtime is one Python file in your source root, and it is managed by the same commands as the others. This guide builds one from the generated starting point.

## Generate the Starting Point

```bash
cd ~/stratarc-source && stratarc adapter new acme-agent --target .acme-agent
```

This writes `adapters/acme-agent.py` and adds `~/.acme-agent` to `runtimeDirectories` in `permissions.json`, the list of directories a sync may write into. `--target` is the runtime's directory under your home; leave it out and it defaults to `.<name>`. The name is lowercase letters, digits and hyphens, and must not be one of the five that ship.

The generated adapter already works: it copies `AGENTS.md` into the runtime's directory. Create the directory and try it:

```bash
mkdir -p ~/.acme-agent && cd ~/stratarc-source && stratarc sync --only acme-agent
```

The control plane gains a `runtime:acme-agent` row on the next `reconcile` or `sync`, and `stratarc.toml` needs no entry unless you want a different `target` or `enabled = false`.

## The File Contract

An adapter file has a literal `RUNTIME` dict and two functions. [Adapter Files](../reference/adapter-files.md) is the full reference; this is the shape:

```python
from pathlib import Path

from stratarc.adapters._common import OwnedDir

RUNTIME = {
    "name": "acme-agent",
    "target": ".acme-agent",
    "hook_registry": None,
    "hook_events": ["PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop",
                    "UserPromptSubmit", "SessionStart", "SubagentStart", "SubagentStop"],
}


def sync(source: Path, target: Path, dry_run: bool = False) -> list[str]:
    ...


def owned_outputs(source: Path, target: Path) -> list[OwnedDir]:
    ...
```

`source` is the staged output for the user-level scope: `AGENTS.md`, `rules/`, `skills/`, `commands/`, `agents/`, `hooks/` and `permissions.json`, holding only the items the control plane selected. `target` is the runtime directory. `sync` writes what the runtime needs and returns one line per change it makes, or would make when `dry_run` is true. It must write nothing when `dry_run` is true.

## Translate More of the Source

Edit `sync` to render the other kinds. Look at a shipped adapter for the format work: `stratarc/adapters/gemini.py` turns commands into TOML and renames hook events, `stratarc/adapters/opencode.py` writes a permission object. Helpers in `stratarc.adapters._common` copy files while preserving the executable bit and mirror a directory, deleting nothing unless asked.

## Tell Stratarc What You Own

`owned_outputs` returns the directories your adapter fills and the names it puts there. `check` uses it to tell a file you wrote from one the runtime or the user put there, and `prune` removes only files in an owned directory that the source no longer produces:

```python
def owned_outputs(source, target):
    commands = frozenset(p.name for p in (source / "commands").glob("*.md"))
    return [OwnedDir("command", target / "commands", commands)]
```

## Declare the Hook Events

`hook_events` lists every canonical event your adapter handles, and a deliberate drop counts. A sync refuses to run a runtime that is missing an event your `hooks/hooks.json` registers, so list all eight even if you drop some.

## Keep It Honest

- `stratarc validate --strict` fails if `stratarc.toml` has a `[runtimes.<name>]` table with no adapter.
- `stratarc diff --only acme-agent` and `stratarc check --only acme-agent` give you the same preview and drift report as the shipped runtimes.
- A test for your adapter can call `sync` against a temporary directory, as `tests/test_runtime_extension.py` in the Stratarc repository does.

An adapter file runs Python from your source root during every sync, so treat the source root like code you trust.
