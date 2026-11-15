"""Read the optional canonical project lifecycle and local checkout bindings."""

from __future__ import annotations

import json
import os
import pathlib
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass


class RegistryError(ValueError):
    """A present registry is invalid and must not be treated as absent."""


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    state: str
    repository: str | None


_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MAX_REGISTRY_BYTES = 1_048_576


def _document(path: pathlib.Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RegistryError(f"{path}: cannot read valid JSON ({error})") from None


def _registry_document(root: pathlib.Path) -> dict | None:
    """Read a bounded regular file without following the registry path or parent."""
    path = root / "projects" / "registry.json"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    root_fd = projects_fd = file_fd = None
    try:
        try:
            root_fd = os.open(root, flags | directory)
        except FileNotFoundError:
            return None
        try:
            projects_fd = os.open("projects", flags | directory, dir_fd=root_fd)
            file_fd = os.open("registry.json", flags, dir_fd=projects_fd)
        except FileNotFoundError:
            return None
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > _MAX_REGISTRY_BYTES:
            raise RegistryError(f"{path}: expected a bounded regular file with one link")
        chunks: list[bytes] = []
        remaining = _MAX_REGISTRY_BYTES + 1
        while remaining:
            chunk = os.read(file_fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        body = b"".join(chunks)
        if len(body) > _MAX_REGISTRY_BYTES:
            raise RegistryError(f"{path}: exceeds {_MAX_REGISTRY_BYTES} bytes")
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise RegistryError(f"{path}: invalid JSON ({error})") from None
        if not isinstance(data, dict):
            raise RegistryError(f"{path}: expected a JSON object")
        return data
    except OSError as error:
        raise RegistryError(f"{path}: cannot safely read ({error})") from None
    finally:
        for fd in (file_fd, projects_fd, root_fd):
            if fd is not None:
                os.close(fd)


@contextmanager
def source_write_lock(root: pathlib.Path):
    """Serialize registry state changes and project delivery with the command service."""
    lock = root / "projects" / "roots" / ".control-plane-write-lock"
    if lock.parent.is_symlink():
        raise RegistryError(f"{lock}: lock parent is a symlink")
    try:
        lock.mkdir()
    except OSError as error:
        raise RegistryError(f"{lock}: source write lock unavailable ({error})") from None
    try:
        yield
    finally:
        lock.rmdir()


def _validate_registry_data(data: dict, path: pathlib.Path) -> dict[str, ProjectRecord]:
    if not isinstance(data, dict) or type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1 or type(data.get("revision")) is not int or data["revision"] < 1 or not isinstance(data.get("projects"), list):
        raise RegistryError(f"{path}: expected schemaVersion 1, positive integer revision, and projects array")
    if set(data) - {"schemaVersion", "revision", "projects", "operations"}:
        raise RegistryError(f"{path}: unknown top-level fields")
    if "operations" in data and not isinstance(data["operations"], list):
        raise RegistryError(f"{path}: operations must be an array")
    records: dict[str, ProjectRecord] = {}
    names: set[str] = set()
    repositories: set[str] = set()
    for item in data["projects"]:
        if not isinstance(item, dict) or set(item) != {"id", "name", "state", "repository"}:
            raise RegistryError(f"{path}: each project needs id, name, state, and repository")
        ident, name, state, repository = (item[key] for key in ("id", "name", "state", "repository"))
        if not isinstance(ident, str) or not _ID.fullmatch(ident) or not isinstance(name, str) or not name.strip():
            raise RegistryError(f"{path}: project ids must be lowercase kebab-case and names nonempty")
        if not isinstance(state, str) or state not in {"active", "inactive", "archived"}:
            raise RegistryError(f"{path}: {ident} has invalid state")
        if repository is not None and (not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository)):
            raise RegistryError(f"{path}: {ident} has invalid repository")
        if ident in records or name in names:
            raise RegistryError(f"{path}: duplicate project id or name")
        if repository is not None and repository in repositories:
            raise RegistryError(f"{path}: duplicate project repository")
        records[ident] = ProjectRecord(ident, name, state, repository)
        names.add(name)
        if repository is not None:
            repositories.add(repository)
    return records


def registry_document(root: pathlib.Path) -> dict | None:
    """Return one validated source document for a locked compare-and-swap edit."""
    data = _registry_document(root)
    if data is not None:
        _validate_registry_data(data, root / "projects" / "registry.json")
    return data


def validate_registry_candidate(root: pathlib.Path, data: dict) -> bytes:
    """Validate a proposed complete document and its serialized size before replacement."""
    path = root / "projects" / "registry.json"
    _validate_registry_data(data, path)
    body = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(body) > _MAX_REGISTRY_BYTES:
        raise RegistryError(f"{path}: exceeds {_MAX_REGISTRY_BYTES} bytes")
    return body


def load_registry(root: pathlib.Path) -> dict[str, ProjectRecord] | None:
    """Return records by stable id, or None only when the file is absent."""
    data = _registry_document(root)
    return None if data is None else _validate_registry_data(data, root / "projects" / "registry.json")


def registry_revision(root: pathlib.Path) -> int | None:
    """Return a validated registry revision for compare-and-swap writes."""
    data = registry_document(root)
    return None if data is None else data["revision"]


def load_locations(root: pathlib.Path, projects_root: pathlib.Path, registry: dict[str, ProjectRecord]) -> dict[str, pathlib.Path]:
    """Read local primary checkout paths, refusing aliases and paths outside the projects root."""
    path = root / "local" / "project-locations.json"
    if not path.exists():
        return {}
    data = _document(path)
    if not isinstance(data, dict) or set(data) != {"schemaVersion", "checkouts"} or type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1 or not isinstance(data["checkouts"], list):
        raise RegistryError(f"{path}: expected schemaVersion 1 and checkouts array")
    paths: dict[str, pathlib.Path] = {}
    used: set[pathlib.Path] = set()
    base = projects_root.resolve()
    for item in data["checkouts"]:
        if not isinstance(item, dict) or set(item) != {"projectId", "checkoutId", "path", "primary"} or item["checkoutId"] != "primary" or item["primary"] is not True or not isinstance(item["projectId"], str) or item["projectId"] not in registry:
            raise RegistryError(f"{path}: each checkout must bind a known project to one primary path")
        raw = item["path"]
        if not isinstance(raw, str) or not pathlib.Path(raw).is_absolute():
            raise RegistryError(f"{path}: checkout paths must be absolute")
        checkout = pathlib.Path(raw)
        if checkout.is_symlink() or any(part.is_symlink() for part in [checkout, *checkout.parents]):
            raise RegistryError(f"{path}: symlink checkout path is forbidden")
        resolved = checkout.resolve()
        if not resolved.is_relative_to(base) or resolved == base or resolved in used or item["projectId"] in paths:
            raise RegistryError(f"{path}: checkout path is outside the projects root or ambiguous")
        paths[item["projectId"]] = resolved
        used.add(resolved)
    return paths
