"""Guard a deploy of the shared configuration against a stale source.

Every runtime root and every project runtime directory that receives the
permission policy also receives a stamp file, `.<name>-deploy.json` (`<name>` is the engine name, `stratarc` by default),
naming the policy version, the source checkout, its branch and commit, and
the time of the write. Before a deploy writes anything, the stamp already
there is compared with the incoming policy: a deploy that would replace a
newer policy version with an older one is refused.

The stamp exists because a sync deploys whatever the checkout it runs in
holds. With several checkouts alive, the last one to write won, silently,
and a newer permission change could be reverted by an older checkout. The
stamp turns that silent loss into a refusal that names both versions.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path

from stratarc.paths import engine_name


def stamp_name(root: Path | None = None) -> str:
    """The stamp file name, `.<engine name>-deploy.json`."""
    return f".{engine_name(root)}-deploy.json"


def read_stamp(target: Path, root: Path | None = None) -> dict | None:
    """The parsed stamp under target, or None when absent or unreadable."""
    path = target / stamp_name(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def deployed_version(target: Path, root: Path | None = None) -> int:
    """The policy version the stamp under target records; 0 when there is none."""
    stamp = read_stamp(target, root)
    if not stamp:
        return 0
    version = stamp.get("policyVersion", 0)
    return version if isinstance(version, int) and version >= 0 else 0


def refusal(target: Path, version: int, root: Path | None = None) -> str | None:
    """A message when the deployed policy under target is newer than version, else None."""
    current = deployed_version(target, root)
    if current > version:
        stamp = read_stamp(target, root) or {}
        origin = stamp.get("source", "an unknown checkout")
        return (
            f"deployed policy version {current} (from {origin}) is newer than the "
            f"source's version {version}; refusing to write an older policy over it"
        )
    return None


def _git(root: Path, *args: str) -> str | None:
    """The stripped output of a git command at root, None when it fails or prints nothing."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def source_branch(root: Path) -> str | None:
    """The branch checked out at root, None when root is not a git checkout or is detached."""
    return _git(root, "symbolic-ref", "--short", "-q", "HEAD")


def source_commit(root: Path, *, full: bool = False) -> str | None:
    """The commit checked out at root, None when root is not a git checkout."""
    return _git(root, "rev-parse", "HEAD") if full else _git(root, "rev-parse", "--short", "HEAD")


def is_git_checkout(root: Path) -> bool:
    """Whether root is inside a git work tree at all."""
    return _git(root, "rev-parse", "--is-inside-work-tree") == "true"


def write_stamp(target: Path, version: int, source: Path) -> Path:
    """Write the stamp under target and return its path."""
    target.mkdir(parents=True, exist_ok=True)
    payload = {
        "policyVersion": version,
        "source": str(source),
        "branch": source_branch(source),
        "commit": source_commit(source),
        "written": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    path = target / stamp_name(source)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
