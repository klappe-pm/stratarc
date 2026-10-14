"""The guided setup a bare `stratarc` starts, driven through scripted answers so no test needs a terminal."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from stratarc import paths, setup
from stratarc.messages import INTERRUPTED


def scripted(*answers: str):
    queue = list(answers)
    asked: list[str] = []

    def ask(prompt: str) -> str:
        asked.append(prompt)
        if not queue:
            raise EOFError
        return queue.pop(0)

    ask.asked = asked  # type: ignore[attr-defined]
    return ask


@pytest.fixture
def home(stratarc_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.delenv("STRATARC_SOURCE", raising=False)
    monkeypatch.chdir(tmp_path)
    (stratarc_home / ".claude").mkdir()
    return stratarc_home


def enabled(root: Path) -> set[str]:
    data = tomllib.loads((root / "stratarc.toml").read_text(encoding="utf-8"))
    return {name for name, table in data["runtimes"].items() if table["enabled"]}


def test_setup_scaffolds_enables_installed_runtimes_and_remembers_the_root(home: Path):
    out: list[str] = []
    code = setup.run(ask=scripted("", "", "n"), say=out.append)
    root = (home / "stratarc-source").resolve()
    assert code == 0
    assert (root / "stratarc.toml").is_file()
    assert enabled(root) == {"claude"}
    assert "# One table per supported runtime." in (root / "stratarc.toml").read_text(encoding="utf-8")
    assert paths.remembered_source() == root
    assert paths.discover_source() == (root, paths.ORIGIN_REMEMBERED)
    assert "Not deployed. Run `stratarc sync` when you are ready." in out
    assert not (home / ".claude" / "CLAUDE.md").exists()


def test_setup_deploys_only_on_yes(home: Path):
    code = setup.run(ask=scripted(str(home / "src"), "claude", "y"), say=lambda _line: None)
    assert code == 0
    assert (home / ".claude" / "CLAUDE.md").is_file()


def test_declining_the_deploy_leaves_project_checkouts_untouched(home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STRATARC_PROJECTS_DIR", raising=False)
    demo = home / "projects" / "active" / "demo"
    demo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(demo)], check=True)
    assert setup.run(ask=scripted(str(home / "src"), "claude", "n"), say=lambda _line: None) == 0
    assert (home / "src" / "control-plane.md").is_file()
    assert [path.name for path in demo.iterdir()] == [".git"]


def test_setup_warns_that_a_deploy_writes_into_project_checkouts(home: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STRATARC_PROJECTS_DIR", raising=False)
    for name in ("alpha", "beta"):
        checkout = home / "projects" / "active" / name
        checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    out: list[str] = []
    assert setup.run(ask=scripted(str(home / "src"), "claude", "n"), say=out.append) == 0
    assert any("also writes into 2 project checkouts: alpha, beta" in line for line in out)


def test_setup_names_no_projects_when_there_are_none(home: Path):
    out: list[str] = []
    assert setup.run(ask=scripted(str(home / "src"), "claude", "n"), say=out.append) == 0
    assert not any("project checkout" in line for line in out)


def test_setup_warns_about_existing_files_and_backs_up_what_it_replaces(home: Path):
    claude = home / ".claude"
    (claude / "CLAUDE.md").write_text("my own instructions\n", encoding="utf-8")
    (claude / ".other-deploy.json").write_text("{}\n", encoding="utf-8")
    out: list[str] = []
    assert setup.run(ask=scripted(str(home / "src"), "claude", "y"), say=out.append) == 0
    assert any("already hold configuration stratarc did not write: claude" in line for line in out)
    assert (claude / "CLAUDE.md").read_text(encoding="utf-8") != "my own instructions\n"
    backups = list((home / ".stratarc" / "backups").rglob("*"))
    assert any(path.is_file() and path.read_text(encoding="utf-8") == "my own instructions\n" for path in backups)


def test_setup_asks_again_for_a_non_empty_directory_and_an_unknown_runtime(home: Path):
    taken = home / "taken"
    taken.mkdir()
    (taken / "notes.txt").write_text("mine\n", encoding="utf-8")
    out: list[str] = []
    ask = scripted(str(taken), str(home / "src"), "clawd", "none")
    assert setup.run(ask=ask, say=out.append) == 0
    assert any("exists and is not empty" in line for line in out)
    assert any("Not a runtime stratarc knows: clawd" in line for line in out)
    assert enabled(home / "src") == set()
    assert (taken / "notes.txt").read_text(encoding="utf-8") == "mine\n"


def test_setup_adopts_an_existing_source_root(home: Path):
    root = home / "existing"
    setup.scaffold(root)
    setup.set_enabled(root / "stratarc.toml", {"codex"})
    assert setup.run(ask=scripted(str(root), "y", "n"), say=lambda _line: None) == 0
    assert enabled(root) == {"codex"}
    assert paths.remembered_source() == root.resolve()


def test_stopping_setup_reports_what_was_written(home: Path):
    out: list[str] = []
    assert setup.run(ask=scripted(str(home / "src")), say=out.append) == INTERRUPTED
    assert any(line.startswith("Setup stopped. Already written: ") for line in out)


def test_remembering_keeps_other_keys(home: Path):
    config = paths.remembered_config()
    config.parent.mkdir(parents=True)
    config.write_text("logging = true\n", encoding="utf-8")
    setup.remember(home / "somewhere")
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert data["logging"] is True
    assert data["source_root"] == str(home / "somewhere")


def test_a_dangling_remembered_root_is_skipped(home: Path, tmp_path: Path):
    setup.remember(home / "gone")
    assert paths.remembered_source() == (home / "gone").resolve()
    assert paths.discover_source() == (tmp_path.resolve(), paths.ORIGIN_CURRENT)


def test_a_nearer_stratarc_toml_beats_the_remembered_root(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    remembered = home / "remembered"
    setup.scaffold(remembered)
    setup.remember(remembered)
    local = tmp_path / "local"
    setup.scaffold(local)
    monkeypatch.chdir(local)
    assert paths.discover_source() == (local.resolve(), paths.ORIGIN_NEAREST)
