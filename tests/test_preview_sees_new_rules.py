"""check and diff report a rule added since the last sync, before any sync embeds it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stratarc.cli import main


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    source = tmp_path / "source"
    monkeypatch.delenv("STRATARC_SOURCE", raising=False)
    assert main(["--home", str(home), "init", str(source)]) == 0
    return home, source


def run(home: Path, source: Path, *command: str) -> int:
    return main(["--home", str(home), "--root", str(source), *command])


def add_rule(source: Path, name: str, text: str) -> None:
    (source / "rules" / f"{name}.md").write_text(f"# {name}\n\n## binding\n\n{text}\n", encoding="utf-8")
    tiers = json.loads((source / "rules" / "tiers.json").read_text(encoding="utf-8"))
    tiers["global"].append(f"{name}.md")
    (source / "rules" / "tiers.json").write_text(json.dumps(tiers), encoding="utf-8")


def test_a_new_rule_is_drift_until_it_is_synced(world, capsys):
    home, source = world
    add_rule(source, "greet-the-user", "Greet the user by name.")
    assert run(home, source, "reconcile") == 0

    assert run(home, source, "check") == 6
    capsys.readouterr()
    assert run(home, source, "diff") == 0
    assert "would copy ~/.claude/AGENTS.md" in capsys.readouterr().out
    assert "greet-the-user" not in (source / "AGENTS.md").read_text(encoding="utf-8")

    assert run(home, source, "sync") == 0
    assert "Greet the user by name." in (home / ".claude" / "AGENTS.md").read_text(encoding="utf-8")
    assert run(home, source, "check") == 0


def test_an_edited_rule_is_drift_too(world):
    home, source = world
    add_rule(source, "keep-answers-short", "Keep answers under five sentences.")
    assert run(home, source, "reconcile") == 0
    assert run(home, source, "sync") == 0
    assert run(home, source, "check") == 0

    (source / "rules" / "keep-answers-short.md").write_text("# keep-answers-short\n\n## binding\n\nKeep answers under three sentences.\n", encoding="utf-8")
    assert run(home, source, "check") == 6
