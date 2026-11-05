#!/usr/bin/env python3
"""Which checkouts are public repositories, decided one way everywhere.

``public-targets.json`` in the source root's project configuration directory
(``layout.project_config_dir``, ``projects-root`` by default) names the repositories published from
this source tree. A public target receives nothing from the source root: no
manifest row, column or snapshot, no delivered file and no permission sweep.
Every one of those reads the list and judges a checkout through this module.

The file is a JSON list, or an object whose ``targets`` key holds one (the
shape that lets it carry a ``$comment``). An entry is a project directory
name (``stratarc``) or a GitHub ``owner/repo`` slug (``owner/repo``).
A missing file declares nothing. One that exists and cannot be read, or
that has any other shape, raises PublicTargetsUnreadable: every reader
fails closed on it, since reading a broken list as empty would treat the one
checkout the file exists to protect as private.

A checkout is public when any of these is listed: the directory name of its
git toplevel, the directory name of its main worktree, or its origin
remote's ``owner/repo`` slug. The main worktree and the origin are read from
the filesystem, never from a git subprocess, because the file it judges may
not exist yet. A linked
worktree's ``.git`` is a file whose ``gitdir:`` line names
``<main>/.git/worktrees/<name>``; the ``commondir`` file inside that
directory names the shared ``.git``, whose parent is the main worktree and
whose ``config`` carries the origin. A ``.git`` directory is its own common
directory. Slugs compare case-insensitively, as GitHub does; names compare
exactly, as the filesystem does.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

RELATIVE_PATH = Path("projects-root") / "public-targets.json"

_GITHUB_ORIGINS = (
    re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?"),
    re.compile(r"git@github\.com:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?"),
    re.compile(r"ssh://git@github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?"),
)


class PublicTargetsUnreadable(Exception):
    """A public-targets.json exists and cannot be trusted."""


FILE_NAME = "public-targets.json"
_LAYOUT_KEY = re.compile(r'^\s*project_config_dir\s*=\s*"([^"]+)"\s*(?:#.*)?$', re.MULTILINE)


def project_config_dir(root: Path) -> str:
    """``layout.project_config_dir`` from ``<root>/stratarc.toml``, or ``projects-root``.

    The engine's own reader is stratarc.config, which this file cannot import
    when a deployed hook runs it under a bare python3; tomllib is used when
    the interpreter has it, a narrow line match otherwise. A stratarc.toml
    that exists and cannot be parsed raises PublicTargetsUnreadable, since
    guessing the directory could miss the list.
    """
    config = Path(root) / "stratarc.toml"
    if not config.is_file():
        return RELATIVE_PATH.parent.as_posix()
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        raise PublicTargetsUnreadable(f"stratarc.toml cannot be read ({type(error).__name__}: {error})") from None
    try:
        import tomllib
    except ImportError:  # Python before 3.11, as a deployed hook may run under
        match = _LAYOUT_KEY.search(text)
        return match.group(1) if match else RELATIVE_PATH.parent.as_posix()
    try:
        layout = tomllib.loads(text).get("layout", {})
    except tomllib.TOMLDecodeError as error:
        raise PublicTargetsUnreadable(f"stratarc.toml cannot be read ({error})") from None
    value = layout.get("project_config_dir") if isinstance(layout, dict) else None
    return value if isinstance(value, str) and value else RELATIVE_PATH.parent.as_posix()


def target_files(root: Path) -> list[Path]:
    """Every file the list is read from: the one in the configured project configuration directory, and the 0.3 location when that differs."""
    configured = Path(project_config_dir(root)) / FILE_NAME
    relatives = [configured] if configured == RELATIVE_PATH else [configured, RELATIVE_PATH]
    return [Path(root) / relative for relative in relatives]


def load_public_targets(root: Path) -> frozenset[str]:
    """The entries of ``public-targets.json`` in the source root's project configuration directory.

    The directory is ``layout.project_config_dir`` in ``stratarc.toml``
    (``projects-root`` when unset). A list left at the 0.3 location,
    ``projects-root/public-targets.json``, is read as well, since a list
    that protects a checkout is never safe to skip. A missing file is an
    empty declaration. An unreadable or malformed one raises
    PublicTargetsUnreadable naming the file, so the caller refuses rather
    than reads it as empty.
    """
    entries: set[str] = set()
    for path in target_files(root):
        label = path.relative_to(Path(root)).as_posix()
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PublicTargetsUnreadable(f"{label} cannot be read ({type(error).__name__}: {error})") from None
        targets = document.get("targets") if isinstance(document, dict) else document
        if not isinstance(targets, list) or not all(isinstance(entry, str) and entry.strip() for entry in targets):
            raise PublicTargetsUnreadable(
                f"{label} must hold a list of project directory names or owner/repo slugs, bare or under a targets key"
            )
        entries.update(entry.strip() for entry in targets)
    return frozenset(entries)


def origin_slug(url: str | None) -> str | None:
    """``owner/repo`` for a GitHub origin URL in any of its three spellings, else None."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    for pattern in _GITHUB_ORIGINS:
        match = pattern.fullmatch(url)
        if match:
            return match.group(1)
    return None


def git_toplevel(path: Path) -> Path | None:
    """The nearest directory at or above *path* holding a ``.git`` entry (a directory, or the file a linked worktree carries), else None."""
    current = Path(os.path.normpath(os.path.abspath(str(path))))
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def git_common_dir(toplevel: Path) -> Path | None:
    """The shared ``.git`` directory of the checkout at *toplevel*, else None."""
    entry = Path(toplevel) / ".git"
    if entry.is_dir():
        gitdir = entry
    elif entry.is_file():
        try:
            first = entry.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, ValueError, IndexError):
            return None
        if not first.startswith("gitdir:"):
            return None
        gitdir = Path(os.path.normpath(os.path.join(str(toplevel), first[len("gitdir:"):].strip())))
    else:
        return None
    common = gitdir / "commondir"
    if common.is_file():
        try:
            relative = common.read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            return None
        if relative:
            gitdir = Path(os.path.normpath(os.path.join(str(gitdir), relative)))
    return gitdir


def origin_url(common_dir: Path) -> str | None:
    """The ``url`` of ``[remote "origin"]`` in ``<common dir>/config``, else None."""
    try:
        lines = (Path(common_dir) / "config").read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    in_origin = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_origin = re.fullmatch(r'\[\s*remote\s+"origin"\s*\]', stripped) is not None
            continue
        if in_origin and "=" in stripped:
            key, value = (part.strip() for part in stripped.split("=", 1))
            if key == "url":
                return value
    return None


def checkout_identity(path: Path) -> tuple[frozenset[str], str | None] | None:
    """(directory names, origin slug) for the checkout holding *path*, or None outside any checkout.

    The names are the toplevel's own directory name and the main worktree's;
    for a primary checkout they are the same name. The slug is the origin's
    ``owner/repo`` when the origin is on GitHub, else None.
    """
    toplevel = git_toplevel(path)
    if toplevel is None:
        return None
    names = {toplevel.name}
    common = git_common_dir(toplevel)
    slug = None
    if common is not None:
        if common.name == ".git":
            names.add(common.parent.name)
        slug = origin_slug(origin_url(common))
    return frozenset(names), slug


def is_public_checkout(path: Path | None, targets: frozenset[str]) -> bool:
    """True when the checkout holding *path* is listed in *targets* by name or by origin slug."""
    if path is None or not targets:
        return False
    identity = checkout_identity(path)
    if identity is None:
        return False
    names, slug = identity
    if names & targets:
        return True
    if slug is None:
        return False
    slugs = {entry.casefold() for entry in targets if "/" in entry}
    return slug.casefold() in slugs
