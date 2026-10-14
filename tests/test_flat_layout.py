"""A project checkout that sits directly under the projects root receives its configuration."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from stratarc.cli import main


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    code = tmp_path / "code"
    checkout = code / "notes"
    checkout.mkdir(parents=True)
    subprocess.run(["git", "-C", str(checkout), "init", "-q"], check=True)
    source = tmp_path / "source"
    monkeypatch.delenv("STRATARC_SOURCE", raising=False)
    assert main(["--home", str(home), "init", str(source)]) == 0
    project = source / "projects-root" / "notes"
    project.mkdir(parents=True)
    (project / "AGENTS.md").write_text("# Notes\n\nKeep entries dated.\n", encoding="utf-8")
    return home, source, code, checkout


def run(home: Path, source: Path, code: Path, *command: str) -> int:
    return main(["--home", str(home), "--root", str(source), "--projects-root", str(code), *command])


def test_a_flat_checkout_is_discovered_and_receives_its_instructions(world, capsys):
    home, source, code, checkout = world
    assert run(home, source, code, "sync") == 0
    assert "Keep entries dated." in (checkout / "AGENTS.md").read_text(encoding="utf-8")
    assert "notes" in (source / "control-plane.md").read_text(encoding="utf-8")
    capsys.readouterr()
    assert run(home, source, code, "check") == 0
