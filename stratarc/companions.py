"""User configuration beside a runtime directory, deployed only by the orchestrator.

Claude Code's user MCP mapping is in .claude.json beside .claude. Keeping
this out of adapter.sync lets scratch renders stay entirely inside their
target. Sync preflights, backs up and verifies these two explicit paths.
"""

from __future__ import annotations

import os
from pathlib import Path

from stratarc.adapters import _components as components
from stratarc import paths


def files(runtime: str, source: Path, target: Path) -> tuple[Path, ...]:
    if runtime != "claude":
        return ()
    servers, _notes = components.selected_servers(source, runtime)
    if not servers and not components._read_ledger(target, source, strict=True):
        return ()
    if target.is_symlink() or target.resolve() != (paths.home() / ".claude").resolve():
        raise components.RenderRefused("Claude user MCP delivery requires the default .claude target; custom target and user configuration were left unchanged")
    return target.parent / ".claude.json", target / components.ledger_name(source)


def sync(runtime: str, source: Path, target: Path, dry_run: bool = False) -> list[str]:
    outputs = files(runtime, source, target)
    if not outputs:
        return []
    for path in outputs:
        if path.is_symlink():
            raise components.RenderRefused(f"{path.name} is a symlink; companion configuration was left unchanged")
    servers, _notes = components.selected_servers(source, runtime)
    desired = {name: components.claude_server(entry) for name, entry in servers.items()}
    return components._render_json(outputs[0], "mcpServers", desired, target, dry_run, source=source, private=True)


def preflight(runtime: str, source: Path, target: Path, *, read_only: bool) -> None:
    sync(runtime, source, target, dry_run=True)
    if read_only:
        return
    for path in files(runtime, source, target):
        parent = path.parent
        while not parent.exists():
            parent = parent.parent
        if not os.access(parent, os.W_OK | os.X_OK) or (path.exists() and not os.access(path, os.W_OK)):
            raise components.RenderRefused(f"{path.name} or its parent is not writable; companion configuration was left unchanged")
