"""Reads `stratarc.toml` from a source root.

The file holds five things: a `[runtimes.<name>]` table per runtime with `enabled` and `target`, a `projects_root` directory, the engine `name` (default `stratarc`), `[validate] gate_private` (default false) and a `[layout]` table naming where the source root keeps its project configuration (`project_config_dir`, default `projects-root`), its control plane (`control_plane`, default `control-plane.md`) and where a project keeps internal work product (`local_dir`, default `.docs`). Layout values are relative paths inside their root. `control_plane_managed = false` marks the control plane as hand maintained, and reconcile then leaves it and the project snapshots alone. A missing file yields the defaults; a malformed one raises `ConfigError` naming the file.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from stratarc.paths import CONFIG_NAME, DEFAULT_NAME, home

_NAME_PATTERN = re.compile(r"[a-z][a-z0-9-]*")


class ConfigError(Exception):
    """`stratarc.toml` exists but cannot be used."""


@dataclass(frozen=True)
class RuntimeConfig:
    enabled: bool = False
    target: Path | None = None


@dataclass(frozen=True)
class Layout:
    project_config_dir: str = "projects-root"
    control_plane: str = "control-plane.md"
    local_dir: str = ".docs"
    control_plane_managed: bool = True


@dataclass(frozen=True)
class Config:
    runtimes: dict[str, RuntimeConfig] = field(default_factory=dict)
    projects_root: Path | None = None
    name: str = DEFAULT_NAME
    gate_private: bool = False
    layout: Layout = field(default_factory=Layout)


def validate_name(value: object) -> bool:
    """True when `value` is a non-empty string matching `^[a-z][a-z0-9-]*$`."""
    return isinstance(value, str) and _NAME_PATTERN.fullmatch(value) is not None


def _expand(value: str) -> Path:
    """Expand a leading `~` against the stratarc home, not the process's."""
    if value == "~":
        return home()
    if value.startswith("~/"):
        return home() / value[2:]
    return Path(value)


def _fail(path: Path, message: str) -> ConfigError:
    return ConfigError(f"{path}: {message}")


def _runtime(path: Path, name: str, table: object) -> RuntimeConfig:
    if not isinstance(table, dict):
        raise _fail(path, f"[runtimes.{name}] must be a table")
    enabled = table.get("enabled", False)
    if not isinstance(enabled, bool):
        raise _fail(path, f"runtimes.{name}.enabled must be true or false")
    target = table.get("target")
    if target is not None and (not isinstance(target, str) or not target):
        raise _fail(path, f"runtimes.{name}.target must be a non-empty string")
    return RuntimeConfig(enabled=enabled, target=_expand(target) if target else None)


_LAYOUT_KEYS = ("project_config_dir", "control_plane", "local_dir", "control_plane_managed")


def _layout(path: Path, table: object) -> Layout:
    if not isinstance(table, dict):
        raise _fail(path, "[layout] must be a table")
    unknown = sorted(set(table) - set(_LAYOUT_KEYS))
    if unknown:
        raise _fail(path, f"layout has unknown key {unknown[0]}")
    values = {}
    for key, value in table.items():
        if key == "control_plane_managed":
            if not isinstance(value, bool):
                raise _fail(path, "layout.control_plane_managed must be true or false")
            values[key] = value
            continue
        parts = value.split("/") if isinstance(value, str) else []
        if not parts or value.startswith("/") or "" in parts or ".." in parts or "." in parts:
            raise _fail(path, f"layout.{key} must be a relative path inside its root, with no `..`")
        values[key] = value
    return Layout(**values)


def load_config(root: Path) -> Config:
    """Read `<root>/stratarc.toml`; return the defaults when the file is absent."""
    path = Path(root) / CONFIG_NAME
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        raise _fail(path, f"cannot read configuration: {exc}") from exc

    runtimes_table = data.get("runtimes", {})
    if not isinstance(runtimes_table, dict):
        raise _fail(path, "runtimes must be a table of tables")
    runtimes = {name: _runtime(path, name, table) for name, table in runtimes_table.items()}

    projects = data.get("projects_root")
    if projects is not None and (not isinstance(projects, str) or not projects):
        raise _fail(path, "projects_root must be a non-empty string")

    name = data.get("name", DEFAULT_NAME)
    if not validate_name(name):
        raise _fail(path, "name must be a non-empty string matching ^[a-z][a-z0-9-]*$")

    validate_table = data.get("validate", {})
    if not isinstance(validate_table, dict):
        raise _fail(path, "[validate] must be a table")
    gate_private = validate_table.get("gate_private", False)
    if not isinstance(gate_private, bool):
        raise _fail(path, "validate.gate_private must be true or false")

    layout = _layout(path, data.get("layout", {}))

    return Config(
        gate_private=gate_private,
        layout=layout,
        name=name,
        runtimes=runtimes,
        projects_root=_expand(projects) if projects else None,
    )
