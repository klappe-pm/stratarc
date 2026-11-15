"""The public-target reader.

hooks/lib/public-targets.py (imported through stratarc.public_targets) is the one definition of which checkouts are public. These tests run it on fixtures: a plain checkout named after the target, a linked worktree of a target repository, a checkout whose origin slug matches owner/repo, a non-target, and a present but unreadable list.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from stratarc import public_targets


def _git(*args: str) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        env=environment,
    )


def _checkout(path: Path, origin: str | None = None) -> Path:
    _git("init", "-q", str(path))
    if origin:
        _git("-C", str(path), "remote", "add", "origin", origin)
    return path


class Fixture:
    def __init__(self, tmp: Path, source: Path):
        self.tmp = tmp
        self.source = source
        (source / "projects-root").mkdir(parents=True, exist_ok=True)
        self.projects = tmp / "projects"
        self.projects.mkdir()

    def write_list(self, text: str) -> None:
        (self.source / "projects-root" / "public-targets.json").write_text(text, encoding="utf-8")

    def engine(self, file: Path) -> bool:
        """The answer of hooks/lib/public-targets.py for a file inside a checkout."""
        return public_targets.is_public_checkout(file.parent, public_targets.load_public_targets(self.source))

    def checkouts(self) -> dict[str, tuple[Path, bool]]:
        """Each fixture: a file path inside a checkout, and whether {"stratarc", "owner/repo"} makes it public."""
        plain = _checkout(self.projects / "stratarc", "https://github.com/someone/other.git")
        _git("-C", str(plain), "commit", "-q", "--allow-empty", "-m", "base")
        worktree = self.projects / "stratarc-feature-wt"
        _git("-C", str(plain), "worktree", "add", "-q", "-b", "feature", str(worktree))
        slug = _checkout(self.projects / "renamed-clone", "git@github.com:Owner/Repo.git")
        slug_worktree_base = _checkout(self.projects / "other-name", "https://github.com/owner/repo")
        _git("-C", str(slug_worktree_base), "commit", "-q", "--allow-empty", "-m", "base")
        slug_worktree = self.projects / "slug-wt"
        _git("-C", str(slug_worktree_base), "worktree", "add", "-q", "-b", "feature", str(slug_worktree))
        private = _checkout(self.projects / "demo", "https://github.com/fixture/demo.git")
        for directory in (plain, worktree, slug, slug_worktree, private):
            (directory / "docs").mkdir(exist_ok=True)
        return {
            "plain checkout named after the target": (plain / "docs" / "note.md", True),
            "linked worktree of the target repository": (worktree / "docs" / "note.md", True),
            "checkout whose origin slug matches": (slug / "docs" / "note.md", True),
            "linked worktree of a slug-matching repository": (slug_worktree / "docs" / "note.md", True),
            "non-target": (private / "docs" / "note.md", False),
        }


@pytest.fixture
def fx(tmp_path, source_root, monkeypatch) -> Fixture:
    monkeypatch.delenv("STRATARC_PUBLIC", raising=False)
    return Fixture(tmp_path.resolve(), source_root)


def test_the_reader_resolves_the_identity_of_every_fixture(fx):
    fx.write_list('{"targets": ["stratarc", "OWNER/repo"]}\n')
    for label, (file, expected) in fx.checkouts().items():
        assert fx.engine(file) == expected, label


def test_a_linked_worktree_is_public_only_through_its_main_worktree_name(fx):
    """The worktree directory is not named in the list; its main worktree is. Reading only the toplevel's own name would call it private in both readers."""
    fx.write_list('["stratarc"]\n')
    worktree_file = fx.checkouts()["linked worktree of the target repository"][0]
    assert worktree_file.parent.parent.name not in {"stratarc"}
    assert fx.engine(worktree_file)
    names, _slug = public_targets.checkout_identity(worktree_file.parent)
    assert names == frozenset({"stratarc-feature-wt", "stratarc"})


@pytest.mark.parametrize(
    "label",
    ["checkout whose origin slug matches", "linked worktree of a slug-matching repository"],
)
def test_the_slug_comparison_ignores_case(fx, label):
    fx.write_list('["owner/REPO"]\n')
    file = fx.checkouts()[label][0]
    assert fx.engine(file)


def test_a_missing_list_declares_nothing(fx):
    for label, (file, _expected) in fx.checkouts().items():
        assert not fx.engine(file), label


@pytest.mark.parametrize("broken", ["{not json", '"stratarc"', '{"targets": "stratarc"}', '{"targets": [1]}', "[1]", '[""]'])
def test_an_unreadable_list_raises(fx, broken):
    fx.write_list(broken)
    with pytest.raises(public_targets.PublicTargetsUnreadable, match="public-targets.json"):
        public_targets.load_public_targets(fx.source)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads a mode 0 file")
def test_a_list_that_cannot_be_opened_raises(fx):
    fx.write_list('["stratarc"]\n')
    path = fx.source / "projects-root" / "public-targets.json"
    path.chmod(0)
    try:
        with pytest.raises(public_targets.PublicTargetsUnreadable):
            public_targets.load_public_targets(fx.source)
    finally:
        path.chmod(0o644)


def test_a_list_object_may_carry_a_comment_key(fx):
    fx.write_list(json.dumps({"$comment": "fixture", "targets": ["stratarc"]}))
    assert public_targets.load_public_targets(fx.source) == frozenset({"stratarc"})


def test_the_module_loads_the_reader_from_package_data():
    """The implementation is the packaged hooks/lib file, found through importlib.resources and not through the module's own location."""
    assert Path(public_targets._module.__file__).as_posix().endswith("stratarc/data/hooks/lib/public-targets.py")
    for name in public_targets.__all__:
        assert hasattr(public_targets, name)


# ----- the list follows the source root's layout -----

_INIT_LAYOUT = '[layout]\nproject_config_dir = "projects/roots"\ncontrol_plane = "projects/roots/control-plane.md"\n'


def test_the_list_is_read_from_the_configured_project_config_dir(tmp_path: Path) -> None:
    """The layout `stratarc init` writes keeps the list in projects/roots/, where `stratarc projects new --public` puts it."""
    source = tmp_path / "source"
    (source / "projects" / "roots").mkdir(parents=True)
    (source / "stratarc.toml").write_text(_INIT_LAYOUT)
    (source / "projects" / "roots" / "public-targets.json").write_text('["published"]\n')
    assert public_targets.load_public_targets(source) == frozenset({"published"})


def test_a_list_left_at_the_old_location_still_counts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "projects" / "roots").mkdir(parents=True)
    (source / "projects-root").mkdir()
    (source / "stratarc.toml").write_text(_INIT_LAYOUT)
    (source / "projects" / "roots" / "public-targets.json").write_text('["new-one"]\n')
    (source / "projects-root" / "public-targets.json").write_text('["old-one"]\n')
    assert public_targets.load_public_targets(source) == frozenset({"new-one", "old-one"})


def test_a_broken_list_in_the_configured_directory_names_its_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "projects" / "roots").mkdir(parents=True)
    (source / "stratarc.toml").write_text(_INIT_LAYOUT)
    (source / "projects" / "roots" / "public-targets.json").write_text("{nope")
    with pytest.raises(public_targets.PublicTargetsUnreadable, match="projects/roots/public-targets.json"):
        public_targets.load_public_targets(source)


def test_an_unparseable_stratarc_toml_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "stratarc.toml").write_text("[layout\n")
    with pytest.raises(public_targets.PublicTargetsUnreadable, match="stratarc.toml"):
        public_targets.load_public_targets(source)


def test_without_tomllib_the_layout_line_is_still_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployed hook may run under a python3 older than 3.11."""
    import builtins

    source = tmp_path / "source"
    (source / "projects" / "roots").mkdir(parents=True)
    (source / "stratarc.toml").write_text(_INIT_LAYOUT)
    real_import = builtins.__import__

    def no_tomllib(name, *args, **kwargs):
        if name == "tomllib":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_tomllib)
    assert public_targets._module.project_config_dir(source) == "projects/roots"


def test_reconcile_in_a_scaffolded_root_gives_a_public_checkout_no_column(tmp_path: Path) -> None:
    """End to end from `stratarc init`: a checkout listed in projects/roots/public-targets.json receives no row, column or snapshot."""
    import sys

    home = tmp_path / "home"
    home.mkdir()
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "STRATARC_"))}
    environment.update(HOME=str(home), STRATARC_HOME=str(home))
    source = home / "stratarc-source"

    def stratarc(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "stratarc", *args], capture_output=True, text=True, env=environment, cwd=home, timeout=120)

    assert stratarc("init", str(source)).returncode == 0
    projects = home / "projects"
    for name in ("published", "private-one"):
        _checkout(projects / name)
    (source / "projects" / "roots" / "public-targets.json").write_text('["published"]\n')
    result = stratarc("--root", str(source), "reconcile")
    assert result.returncode == 0, result.stdout + result.stderr
    plane = (source / "projects" / "roots" / "control-plane.md").read_text()
    assert "private-one" in plane
    assert "published" not in plane
    assert not (projects / "published" / "local").exists()
