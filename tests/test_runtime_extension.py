"""A user adds a runtime of their own: one adapter file in the source root's adapters directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stratarc.adapters._common import RegistryError, runtime_registry
from stratarc.cli import main


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    (home / ".acme").mkdir(parents=True)
    source = tmp_path / "source"
    monkeypatch.delenv("STRATARC_SOURCE", raising=False)
    assert main(["--home", str(home), "init", str(source)]) == 0
    return home, source


def run(home: Path, source: Path, *command: str) -> int:
    return main(["--home", str(home), "--root", str(source), *command])


def test_adapter_new_writes_a_working_adapter_and_allows_its_directory(world, capsys):
    home, source = world
    assert run(home, source, "adapter", "new", "acme", "--target", ".acme") == 0
    assert (source / "adapters" / "acme.py").is_file()
    assert "~/.acme" in json.loads((source / "permissions.json").read_text())["runtimeDirectories"]
    assert "acme" in runtime_registry(root=source)
    capsys.readouterr()


def test_sync_check_diff_and_prune_cover_the_new_runtime(world, capsys):
    home, source = world
    assert run(home, source, "adapter", "new", "acme", "--target", ".acme") == 0
    (source / "AGENTS.md").write_text("# Instructions\n\nBe brief.\n", encoding="utf-8")

    assert run(home, source, "diff") == 0
    assert not (home / ".acme" / "AGENTS.md").exists()

    assert run(home, source, "sync") == 0
    assert (home / ".acme" / "AGENTS.md").read_text(encoding="utf-8").endswith("Be brief.\n")

    assert run(home, source, "check") == 0

    (source / "AGENTS.md").write_text("# Instructions\n\nBe thorough.\n", encoding="utf-8")
    assert run(home, source, "check") != 0
    capsys.readouterr()
    assert run(home, source, "sync") == 0
    assert run(home, source, "prune", "--dry-run") == 0


def test_a_runtime_table_without_an_adapter_is_an_error_not_a_silent_skip(world, capsys):
    home, source = world
    with (source / "stratarc.toml").open("a", encoding="utf-8") as handle:
        handle.write('\n[runtimes.acme-agent]\nenabled = true\n')
    assert run(home, source, "sync") == 2
    err = capsys.readouterr().err
    assert "acme-agent" in err and "no adapter" in err
    assert run(home, source, "validate", "--strict") == 1
    assert "acme-agent" in capsys.readouterr().out


def test_a_source_adapter_cannot_reuse_a_packaged_name(world, capsys):
    home, source = world
    assert run(home, source, "adapter", "new", "claude") != 0
    assert "already has an adapter" in capsys.readouterr().err
    (source / "adapters").mkdir(exist_ok=True)
    (source / "adapters" / "claude.py").write_text(
        'RUNTIME = {"name": "claude", "target": ".claude2", "hook_registry": None, "hook_events": []}\n', encoding="utf-8"
    )
    with pytest.raises(RegistryError, match="already provided by a packaged adapter"):
        runtime_registry(root=source)


def test_a_directory_without_stratarc_toml_contributes_no_adapters(tmp_path):
    (tmp_path / "adapters").mkdir()
    (tmp_path / "adapters" / "stray.py").write_text("print('not an adapter')\n", encoding="utf-8")
    assert "stray" not in runtime_registry(root=tmp_path)


def test_a_new_adapter_declares_every_hook_event_the_packaged_runtimes_handle(world):
    home, source = world
    assert run(home, source, "adapter", "new", "acme") == 0
    registry = runtime_registry(root=source)
    assert registry["acme"].hook_events == registry["claude"].hook_events
    assert registry["acme"].relative == ".acme"
