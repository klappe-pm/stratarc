"""The deploy ledger: which runtime paths a write run actually put there.

A runtime directory Stratarc owns (commands/, prompts/, agents/, rules/,
skills/, hooks/) can also hold files a person or another tool put there. The
current source alone cannot tell the two apart: a name it no longer produces
may be something Stratarc deployed and the source then dropped, or something
that was never Stratarc's. The ledger is the evidence. Every write run adds
the paths it rendered into each owned directory, and the reverse pass treats
an entry the ledger never recorded as unmanaged: reported, never pruned.

The ledger only grows on a write run and shrinks when prune deletes a path.
A home with no ledger yet (written by a release before the ledger existed)
records nothing as deployed, so every orphan there is preserved until a write
run has recorded what this source produces; a path the source dropped before
that first recorded run is left for the user to remove by hand.

The file is `<home>/.stratarc/state/deployed.json`:

```json
{"schema_version": 1, "runtimes": {"codex": ["/home/me/.codex/prompts/x.md"]}}
```
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
from typing import Iterable

from stratarc.paths import home

SCHEMA_VERSION = 1


def ledger_path() -> pathlib.Path:
    return home() / ".stratarc" / "state" / "deployed.json"


def load() -> dict[str, set[str]]:
    """Every recorded path, by runtime. A missing or unreadable ledger records nothing."""
    path = ledger_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    runtimes = data.get("runtimes") if isinstance(data, dict) else None
    if not isinstance(runtimes, dict):
        return {}
    return {
        str(name): {str(p) for p in paths if isinstance(p, str)}
        for name, paths in runtimes.items()
        if isinstance(paths, list)
    }


def _save(ledger: dict[str, set[str]]) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": SCHEMA_VERSION,
        "runtimes": {name: sorted(paths) for name, paths in sorted(ledger.items()) if paths},
    }
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".deployed-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def produced_paths(owned_dirs: Iterable) -> set[str]:
    """The paths a write run just rendered: each owned directory's names that exist."""
    found: set[str] = set()
    for od in owned_dirs:
        for name in od.names:
            p = od.path / name
            if p.exists() or p.is_symlink():
                found.add(str(p))
    return found


def record(runtime: str, paths: Iterable[str]) -> None:
    """Add the paths a write run rendered for one runtime."""
    new = set(paths)
    if not new:
        return
    ledger = load()
    current = ledger.setdefault(runtime, set())
    if new <= current:
        return
    current |= new
    _save(ledger)


def forget_everywhere(paths: Iterable[str]) -> None:
    """Drop paths a rollback removed, whichever runtime recorded them."""
    gone = set(paths)
    ledger = load()
    if not gone or not any(recorded & gone for recorded in ledger.values()):
        return
    for name in ledger:
        ledger[name] -= gone
    _save(ledger)


def forget(runtime: str, paths: Iterable[str]) -> None:
    """Drop paths prune deleted, so a later hand-made file at the same path is not taken for Stratarc's."""
    gone = set(paths)
    ledger = load()
    if not gone or not (ledger.get(runtime, set()) & gone):
        return
    ledger[runtime] -= gone
    _save(ledger)
