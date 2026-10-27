"""Tests for `stratarc projects --new` and `--registry-check`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stratarc import projects, projects_new, staging
from stratarc.control_plane import ControlPlane

PLANE = """# control-plane

Prose that must survive untouched.

## projects

| project | status | tier | root | origin |
|---|---|---|---|---|
| alpha | active | normal | [alpha/](alpha/AGENTS.md) | acme/alpha |
| zulu | inactive | normal | [zulu/](zulu/AGENTS.md) | acme/zulu |

## instruction-file

| option | global | alpha |
|---|---|---|
| [AGENTS.md](../../AGENTS.md) | x | x |

## rules

| option | tier | global | alpha |
|---|---|---|---|
| [rule:common-one](../../rules/common-one.md) | common | x | x |
| [rule:project-one](../../rules/project-one.md) | project | x |  |

## project-local-configuration

| option | global | alpha |
|---|---|---|
| [project:AGENTS.md](alpha/AGENTS.md) |  | x |

## runtimes

| option | global |
|---|---|
| [runtime:claude](../../stratarc.toml) | x |
"""

GITIGNORE = """# local: private work.
/local/
*.local.*

# machine: caches.
.env
.DS_Store

# Generated.
/AGENTS.md
/CLAUDE.md
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Fixture:
    def __init__(self, root: Path, projects_dir: Path):
        self.root = root
        self.projects = projects_dir
        self.config = root / "projects" / "roots"
        self.plane = self.config / "control-plane.md"

    def run(self, *args: str) -> int:
        return projects.main([*args, "--root", str(self.root)])

    def tree(self) -> dict[str, bytes]:
        return {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in sorted(self.root.rglob("*"))
            if p.is_file()
        }

    def make_checkout(self, name: str, status: str = "active") -> Path:
        path = self.projects / status / name
        (path / ".git").mkdir(parents=True)
        return path


@pytest.fixture
def bare(tmp_path, monkeypatch, stratarc_home):
    root = tmp_path / "source"
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    write(
        root / "stratarc.toml",
        '[layout]\nproject_config_dir = "projects/roots"\ncontrol_plane = "projects/roots/control-plane.md"\nlocal_dir = "local"\ncontrol_plane_managed = false\n',
    )
    config = root / "projects" / "roots"
    write(config / "control-plane.md", PLANE)
    write(config / "alpha" / "AGENTS.md", "# alpha\n")
    write(config / "zulu" / "AGENTS.md", "# zulu\n")
    write(config / "remotes.json", json.dumps({"alpha": "acme/alpha", "stratarc-lib": "acme/lib", "zulu": "acme/zulu"}, indent=2) + "\n")
    write(config / "public-targets.json", json.dumps({"$comment": "public", "targets": ["stratarc-lib"]}, indent=2) + "\n")
    template = root / "templates" / "project"
    write(template / "roots" / "AGENTS.md", "# <project>\n\nThe <project> project.\n")
    write(template / "checkout" / ".gitignore", GITIGNORE)
    write(template / "checkout" / "local" / "README.md", "# local\n")
    monkeypatch.setenv("STRATARC_PROJECTS_DIR", str(projects_dir))
    monkeypatch.setenv("STRATARC_SOURCE", str(root))
    for name in ("ROOT", "PROJECTS_SRC", "RETIRED_RULES", "RETIRED_HOOKS", "_ROOT_CONFIGURED"):
        monkeypatch.setattr(projects, name, getattr(projects, name))
    monkeypatch.setattr(projects, "RENDERERS", {})
    yield Fixture(root, projects_dir)
    staging.cleanup_all()


@pytest.fixture
def world(bare, monkeypatch):
    """The same source root with the final project checks stubbed out, so each test sees only its own step."""
    monkeypatch.setattr(projects_new, "project_findings", lambda root, name, public: ([], []))
    return bare


def test_a_dry_run_writes_nothing_and_says_what_it_would_do(world, capsys):
    world.make_checkout("bravo")
    before = world.tree()
    assert world.run("--new", "bravo", "--remote", "acme/bravo", "--check") == 0
    assert world.tree() == before
    out = capsys.readouterr().out
    assert "would:" in out
    for part in ("root: add projects/roots/bravo/AGENTS.md", "control plane: add the row and column", "remotes.json: add bravo", ".gitignore: create", "local/README.md"):
        assert part in out
    assert world.run("--new", "bravo", "--dry-run") == 0
    assert world.tree() == before


def test_a_full_run_sets_up_root_plane_registry_and_checkout(world, capsys):
    checkout = world.make_checkout("bravo")
    assert world.run("--new", "bravo", "--remote", "acme/bravo") == 0
    assert (world.config / "bravo" / "AGENTS.md").read_text() == "# bravo\n\nThe bravo project.\n"
    cp = ControlPlane.load(world.plane)
    assert list(cp.manifest) == ["alpha", "bravo", "zulu"]
    assert cp.manifest["bravo"] == {"status": "active", "tier": "normal", "root": "[bravo/](bravo/AGENTS.md)", "origin": "acme/bravo"}
    assert cp.enabled("bravo", "AGENTS.md") and cp.enabled("bravo", "project:AGENTS.md")
    assert cp.enabled("bravo", "rule:common-one") and not cp.enabled("bravo", "rule:project-one")
    assert json.loads((world.config / "remotes.json").read_text())["bravo"] == "acme/bravo"
    assert (checkout / ".gitignore").read_text() == GITIGNORE
    assert (checkout / "local" / "README.md").is_file()
    out = capsys.readouterr().out
    assert "stratarc sync" in out and "bravo is clean" in out


def test_the_control_plane_keeps_every_other_byte_and_sorts_the_new_entries(world):
    world.make_checkout("bravo")
    world.run("--new", "bravo")
    new = world.plane.read_text().splitlines()
    old = PLANE.splitlines()
    assert "| bravo | active | normal | [bravo/](bravo/AGENTS.md) | - |" in new
    assert new.index("| bravo | active | normal | [bravo/](bravo/AGENTS.md) | - |") == new.index(old[old.index("| alpha | active | normal | [alpha/](alpha/AGENTS.md) | acme/alpha |")]) + 1
    assert "Prose that must survive untouched." in new
    assert "| option | global | alpha | bravo |" in new
    assert "| option | tier | global | alpha | bravo |" in new
    assert "| option | global | bravo |" in new  # the table without project columns takes it after global
    # Dropping the new row and the new cell of every table line gives the original file back.
    rows = [line for line in new if line != "| bravo | active | normal | [bravo/](bravo/AGENTS.md) | - |"]
    assert len(rows) == len(old)
    for before, after in zip(old, rows):
        if before == after:
            continue
        a_parts, b_parts = before.split("|"), after.split("|")
        assert len(b_parts) == len(a_parts) + 1
        assert any(b_parts[:i] + b_parts[i + 1 :] == a_parts for i in range(len(b_parts)))


def test_a_second_run_changes_nothing_and_says_so(world, capsys):
    world.make_checkout("bravo")
    world.run("--new", "bravo", "--remote", "acme/bravo")
    after = world.tree()
    capsys.readouterr()
    assert world.run("--new", "bravo", "--remote", "acme/bravo") == 0
    assert world.tree() == after
    assert "nothing to change, already set up" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["Bravo", "two_words", "-lead", "trail-", "a--b", "has space", ""])
def test_a_bad_name_is_refused_with_status_2(world, capsys, name):
    before = world.tree()
    assert world.run(f"--new={name or 'x y'}") == 2
    assert world.tree() == before
    assert "kebab-case" in capsys.readouterr().err


def test_a_bad_remote_is_refused(world, capsys):
    assert world.run("--new", "bravo", "--remote", "not-a-slug") == 2
    assert "OWNER/REPO" in capsys.readouterr().err


def test_a_root_the_control_plane_does_not_list_is_refused(world, capsys):
    write(world.config / "stray" / "AGENTS.md", "# stray\n")
    before = world.tree()
    assert world.run("--new", "stray") == 2
    assert world.tree() == before
    assert "does not list" in capsys.readouterr().err


def test_an_incomplete_root_is_completed_without_replacing_files(world):
    write(world.config / "bravo" / "notes.md", "keep me\n")
    assert world.run("--new", "bravo") == 0
    assert (world.config / "bravo" / "notes.md").read_text() == "keep me\n"
    assert (world.config / "bravo" / "AGENTS.md").is_file()


def test_a_public_project_goes_in_public_targets_and_gets_no_config(world):
    world.make_checkout("pubrepo")
    before_plane = world.plane.read_text()
    assert world.run("--new", "pubrepo", "--public", "--remote", "acme/pubrepo") == 0
    assert not (world.config / "pubrepo").exists()
    assert world.plane.read_text() == before_plane
    assert json.loads((world.config / "public-targets.json").read_text()) == {"$comment": "public", "targets": ["pubrepo", "stratarc-lib"]}
    assert json.loads((world.config / "remotes.json").read_text())["pubrepo"] == "acme/pubrepo"
    assert not (world.projects / "active" / "pubrepo" / ".gitignore").exists()
    assert world.run("--registry-check") == 0


def test_a_project_with_a_root_cannot_be_added_as_public(world):
    assert world.run("--new", "alpha", "--public") == 2


def test_a_missing_checkout_is_reported_and_everything_else_is_done(world, capsys):
    assert world.run("--new", "bravo") == 0
    out = capsys.readouterr().out
    assert "does not exist" in out
    assert (world.config / "bravo" / "AGENTS.md").is_file()
    assert not (world.projects / "active" / "bravo").exists()


def test_the_checkout_flag_names_a_checkout_elsewhere(world):
    elsewhere = world.make_checkout("bravo", "new")
    assert world.run("--new", "bravo", "--checkout", str(elsewhere)) == 0
    assert (elsewhere / "local" / "README.md").is_file()
    cp = ControlPlane.load(world.plane)
    assert cp.status("bravo") == "new"
    assert "| option | global | alpha |" in world.plane.read_text() and "bravo |" not in world.plane.read_text().split("## instruction-file")[1]


def test_the_gitignore_merge_adds_missing_lines_and_deletes_none(world):
    checkout = world.make_checkout("bravo")
    existing = "node_modules/\n.env\n/local/\ncustom-line\n"
    write(checkout / ".gitignore", existing)
    local = write(checkout / "local" / "README.md", "mine\n")
    assert world.run("--new", "bravo") == 0
    merged = (checkout / ".gitignore").read_text()
    assert merged.startswith(existing)
    lines = merged.splitlines()
    for wanted in ("*.local.*", ".DS_Store", "/AGENTS.md", "/CLAUDE.md"):
        assert lines.count(wanted) == 1
    assert lines.count(".env") == 1 and lines.count("/local/") == 1
    assert local.read_text() == "mine\n"
    again = merged
    world.run("--new", "bravo")
    assert (checkout / ".gitignore").read_text() == again


def test_workflows_template_is_copied_only_when_it_exists(world):
    assert world.run("--new", "bravo", "--workflows") == 0
    assert not (world.config / "bravo" / "workflows.toml").exists()
    write(world.root / "templates" / "project" / "workflows.toml", "[workflows]\n")
    assert world.run("--new", "charlie", "--workflows") == 0
    assert (world.config / "charlie" / "workflows.toml").read_text() == "[workflows]\n"
    assert world.run("--new", "delta") == 0
    assert not (world.config / "delta" / "workflows.toml").exists()


def test_the_template_flags_need_new(world, capsys):
    assert world.run("--remote", "acme/x") == 2
    assert "needs --new" in capsys.readouterr().err


def test_a_project_that_is_not_clean_exits_1(world, monkeypatch, capsys):
    monkeypatch.setattr(projects_new, "project_findings", lambda root, name, public: (["an error"], ["a pending"]))
    assert world.run("--new", "bravo") == 1
    out = capsys.readouterr().out
    assert "problem: an error" in out and "pending: a pending" in out and "not clean" in out


def test_the_real_checks_run_on_a_fresh_project(bare, capsys):
    bare.make_checkout("bravo")
    assert bare.run("--new", "bravo", "--remote", "acme/bravo") in (0, 1)
    out = capsys.readouterr().out
    assert "stratarc sync" in out
    assert "bravo is" in out


# registry check


def test_the_registry_check_passes_on_agreeing_files(world, capsys):
    write(world.config / "remotes.json", json.dumps({"alpha": "a/a", "zulu": "a/z", "stratarc-lib": "a/l"}))
    assert world.run("--registry-check") == 0
    assert "agree" in capsys.readouterr().out


def test_the_registry_check_reports_one_problem_per_line(world, capsys):
    (world.config / "zulu" / "AGENTS.md").unlink()
    (world.config / "zulu").rmdir()
    write(world.config / "remotes.json", json.dumps({"zulu": "a/z"}))
    write(world.config / "stray" / "AGENTS.md", "# stray\n")
    write(world.config / "public-targets.json", json.dumps(["alpha", "gone-public"]))
    before = world.tree()
    assert world.run("--registry-check") == 1
    assert world.tree() == before
    lines = capsys.readouterr().out.splitlines()
    assert "registry: zulu: in the control plane but has no root folder" in lines
    assert "registry: gone-public: in public-targets.json but has no remotes.json entry" in lines
    assert "registry: stray: has a root folder but is not in the control plane" in lines
    assert "registry: alpha: is in public-targets.json but also has a control plane row" in lines
    assert all(line.startswith("registry: ") for line in lines)


def test_the_registry_check_reports_a_missing_remote(world, capsys):
    write(world.config / "remotes.json", json.dumps({"alpha": "a/a", "stratarc-lib": "a/l"}))
    assert world.run("--registry-check") == 1
    assert capsys.readouterr().out.splitlines() == ["registry: zulu: in the control plane but has no remotes.json entry"]
