"""Where stratarc finds the home directory, the source root and the projects root.

This module and `stratarc.config` are the only places that read `STRATARC_HOME`, `STRATARC_SOURCE`, `STRATARC_PROJECTS_DIR` and `STRATARC_NAME`. Every function reads the environment when it is called, never at import, so a test or a command line flag can redirect them after the module is loaded.
"""

from __future__ import annotations

import os
from pathlib import Path

CONFIG_NAME = "stratarc.toml"
HOME_VARIABLE = "STRATARC_HOME"
SOURCE_VARIABLE = "STRATARC_SOURCE"
PROJECTS_VARIABLE = "STRATARC_PROJECTS_DIR"
NAME_VARIABLE = "STRATARC_NAME"
DEFAULT_NAME = "stratarc"
# The machine state directory under the home; `stratarc.home_layout` owns its layout.
STATE_DIRECTORY = ".stratarc"
# The key in the home's config.toml that records the source root `stratarc setup` chose.
REMEMBERED_KEY = "source_root"

ORIGIN_ENVIRONMENT = SOURCE_VARIABLE
ORIGIN_NEAREST = f"nearest {CONFIG_NAME}"
ORIGIN_REMEMBERED = f"{STATE_DIRECTORY}/config.toml"
ORIGIN_CURRENT = "current directory"


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def home() -> Path:
    """The home directory every runtime target and `~` expansion hangs under.

    `STRATARC_HOME` wins when set and non-empty, then `HOME`, then the home directory the platform reports. The override lets a test or a clean-room run redirect every target without touching the real home.
    """
    for name in (HOME_VARIABLE, "HOME"):
        value = _env(name)
        if value:
            return Path(value).expanduser()
    return Path.home()


def remembered_config() -> Path:
    """The home file `stratarc setup` records the chosen source root in: `<home>/.stratarc/config.toml`."""
    return home() / STATE_DIRECTORY / "config.toml"


def remembered_source() -> Path | None:
    """The source root `stratarc setup` recorded, as written; None when there is none or the file cannot be read.

    The path is returned whether or not it still holds `stratarc.toml`, so `doctor` can report a dangling one. `source_root` uses it only when it does.
    """
    import tomllib

    try:
        data = tomllib.loads(remembered_config().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(REMEMBERED_KEY)
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser().resolve()


def discover_source() -> tuple[Path, str]:
    """The source root when no explicit one is given, and what decided it.

    Precedence: `STRATARC_SOURCE`, then the nearest directory at or above the current directory that holds `stratarc.toml`, then the source root `stratarc setup` remembered when it still holds `stratarc.toml`, then the current directory. The second value is one of the `ORIGIN_` constants.
    """
    value = _env(SOURCE_VARIABLE)
    if value:
        return Path(value).expanduser().resolve(), ORIGIN_ENVIRONMENT
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate, ORIGIN_NEAREST
    remembered = remembered_source()
    if remembered is not None and (remembered / CONFIG_NAME).is_file():
        return remembered, ORIGIN_REMEMBERED
    return cwd, ORIGIN_CURRENT


def source_root(explicit: Path | None = None) -> Path:
    """The source root to read from.

    Precedence: the explicit argument, then `discover_source`: `STRATARC_SOURCE`, the nearest `stratarc.toml` at or above the current directory, the source root `stratarc setup` remembered, then the current directory.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    return discover_source()[0]


def projects_root(explicit: Path | None = None, root: Path | None = None) -> Path:
    """The directory that holds project checkouts.

    Precedence: the explicit argument (a command line flag), then `STRATARC_PROJECTS_DIR`, then `projects_root` in the source root's `stratarc.toml`, then `<home>/projects`.
    """
    if explicit is not None:
        return Path(explicit).expanduser()
    value = _env(PROJECTS_VARIABLE)
    if value:
        return Path(value).expanduser()
    from stratarc.config import load_config

    configured = load_config(source_root(root)).projects_root
    if configured is not None:
        return configured
    return home() / "projects"


def projects_dir(root: Path | None = None, explicit: Path | None = None) -> Path:
    """The directory that holds the project checkouts: the projects root.

    Its children are either the checkouts themselves (a flat layout) or status directories (`active/`, `inactive/`, `archived/`, and so on) that hold them. Note the argument order differs from `projects_root`: the source root comes first.
    """
    return projects_root(explicit, root)


def engine_name(root: Path | None = None) -> str:
    """The name the engine puts on everything it generates and records.

    Precedence: `STRATARC_NAME`, then `name` in the source root's `stratarc.toml`, then `stratarc`. Marker comments, permission profile names, ledger and stamp file names and git config keys are all derived from it. A malformed `STRATARC_NAME` raises `ConfigError`.
    """
    from stratarc.config import ConfigError, load_config, validate_name

    value = _env(NAME_VARIABLE)
    if value:
        if not validate_name(value):
            raise ConfigError(f"{NAME_VARIABLE}: name must match ^[a-z][a-z0-9-]*$")
        return value
    return load_config(source_root(root)).name



def project_config_dir(root: Path | None = None) -> Path:
    """The directory under the source root that holds each project's own configuration (`layout.project_config_dir`)."""
    from stratarc.config import load_config

    base = source_root(root)
    return base / load_config(base).layout.project_config_dir


def control_plane_file(root: Path | None = None) -> Path:
    """The control plane file under the source root (`layout.control_plane`)."""
    from stratarc.config import load_config

    base = source_root(root)
    return base / load_config(base).layout.control_plane


def local_dir_name(root: Path | None = None) -> str:
    """The folder name inside a project that holds internal work product (`layout.local_dir`)."""
    from stratarc.config import load_config

    return load_config(source_root(root)).layout.local_dir
