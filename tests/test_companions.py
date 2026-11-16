"""Companion files participate in sync without escaping adapter scratch renders."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from stratarc import companions, setup, sync, verify
from stratarc.adapters import _components as components
from tests.conftest import tree_snapshot


@pytest.fixture
def selected(tmp_path, stratarc_home, monkeypatch):
    root = tmp_path / "source"
    setup.scaffold(root)
    (root / "stratarc.toml").write_text('[runtimes.claude]\nenabled = true\n[layout]\ncontrol_plane_managed = false\n')
    (root / "control-plane.md").write_text('| option | global |\n|---|---|\n| runtime:claude | x |\n| mcp:example | x |\n')
    (root / "components.json").write_text(json.dumps({
        "version": 1,
        "mcp_servers": [{"name": "example", "wanted": True, "owner": "stratarc", "runtimes": ["claude"], "command": "echo", "args": ["fixture"]}],
    }))
    monkeypatch.delenv("STRATARC_SOURCE", raising=False)
    monkeypatch.delenv("STRATARC_PROJECTS_DIR", raising=False)
    target = stratarc_home / ".claude"
    target.mkdir()
    return root, target


def test_companion_preview_preserves_all_files_and_sync_preserves_other_keys(selected):
    root, target = selected
    path = target.parent / ".claude.json"
    target.parent.chmod(0o755)
    path.write_text(json.dumps({"preferences": {"theme": "dark"}, "mcpServers": {"own": {"command": "mine"}}}))
    before = tree_snapshot(target.parent)
    assert companions.sync("claude", root, target, dry_run=True)
    assert tree_snapshot(target.parent) == before
    assert companions.sync("claude", root, target)
    data = json.loads(path.read_text())
    assert data["preferences"] == {"theme": "dark"}
    assert data["mcpServers"]["own"] == {"command": "mine"}
    assert data["mcpServers"]["example"] == {"command": "echo", "args": ["fixture"], "type": "stdio"}
    assert path.stat().st_mode & 0o777 == 0o600
    assert target.parent.stat().st_mode & 0o777 == 0o755
    assert companions.sync("claude", root, target) == []
    (root / "components.json").write_text('{"mcp_servers": []}')
    companions.sync("claude", root, target)
    assert json.loads(path.read_text())["mcpServers"] == {"own": {"command": "mine"}}


@pytest.mark.parametrize("content", ["{", "[]", '{"mcpServers": []}'])
def test_invalid_companion_configuration_is_refused_without_writes(selected, content):
    root, target = selected
    path = target.parent / ".claude.json"
    path.write_text(content)
    before = tree_snapshot(target.parent)
    with pytest.raises(components.RenderRefused):
        companions.preflight("claude", root, target, read_only=False)
    assert tree_snapshot(target.parent) == before


@pytest.mark.parametrize("linked", ["config", "ledger"])
def test_companion_symlinks_are_refused(selected, tmp_path, linked):
    root, target = selected
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    path = target.parent / ".claude.json" if linked == "config" else target / components.ledger_name(root)
    path.symlink_to(outside)
    with pytest.raises(components.RenderRefused, match="symlink"):
        companions.sync("claude", root, target)
    assert outside.read_text() == "{}"


def test_scratch_adapter_render_cannot_write_a_companion_beside_its_target(selected, tmp_path):
    root, _target = selected
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    adapter = importlib.import_module("stratarc.adapters.claude")
    adapter.sync(root, scratch)
    assert not (scratch.parent / ".claude.json").exists()


def test_full_sync_check_and_verify_include_companion_drift(selected):
    root, target = selected
    args = ["--root", str(root), "--only", "claude"]
    assert sync.main(args) == 0
    path = target.parent / ".claude.json"
    assert path.is_file()
    assert sync.main(args + ["--check"]) == 0
    assert verify.run("all", root=root).exit_code == 0
    data = json.loads(path.read_text())
    data["mcpServers"]["example"]["args"] = ["changed"]
    path.write_text(json.dumps(data))
    before = tree_snapshot(target.parent)
    assert sync.main(args + ["--check"]) == 1  # the CLI maps the module's stale result to exit 6
    report = verify.run("all", root=root)
    assert report.exit_code == 6
    assert any(e["file"] == ".claude.json" and e["status"] == "drift" for e in report.files)
    assert path.read_bytes() == before[".claude.json"]


def test_malformed_companion_stops_sync_before_runtime_writes(selected):
    root, target = selected
    (target.parent / ".claude.json").write_text("{broken")
    before = tree_snapshot(target)
    assert sync.main(["--root", str(root), "--only", "claude"]) != 0
    assert tree_snapshot(target) == before


def test_companion_backup_restores_configuration_and_ownership(selected):
    root, target = selected
    path = target.parent / ".claude.json"
    path.write_text('{"preferences": "keep"}')
    original = path.read_bytes()
    state = sync.DeployState()
    sync._back_up_planned(importlib.import_module("stratarc.adapters.claude"), "claude", root, target, root, state)
    companions.sync("claude", root, target)
    assert sync._roll_back(state)
    assert path.read_bytes() == original
    assert not (target / components.ledger_name(root)).exists()


def test_a_custom_target_cannot_modify_the_live_user_configuration(selected):
    root, target = selected
    custom = target.with_name(".claude-preview")
    custom.mkdir()
    live = target.parent / ".claude.json"
    live.write_text('{"preferences": "live"}')
    with pytest.raises(components.RenderRefused, match="default .claude target"):
        companions.sync("claude", root, custom)
    assert live.read_text() == '{"preferences": "live"}'
    (root / "stratarc.toml").write_text(
        f'[runtimes.claude]\nenabled = true\ntarget = "{custom.as_posix()}"\n[layout]\ncontrol_plane_managed = false\n'
    )
    report = verify.run("all", root=root)
    assert any(e["file"] == ".claude.json" and e["status"] == "skipped" for e in report.files)
    assert live.read_text() == '{"preferences": "live"}'


@pytest.mark.parametrize("content", ["{", "[]", '{"mcp_servers": null}'])
def test_a_corrupt_ownership_ledger_is_not_replaced(selected, content):
    root, target = selected
    ledger = target / components.ledger_name(root)
    ledger.write_text(content)
    with pytest.raises(components.RenderRefused, match="ledger"):
        companions.sync("claude", root, target)
    assert ledger.read_text() == content
    assert not (target.parent / ".claude.json").exists()


def test_unowned_server_collision_preserves_its_environment_and_configuration(selected):
    root, target = selected
    path = target.parent / ".claude.json"
    original = {"mcpServers": {"example": {"command": "my-wrapper", "env": {"MODE": "personal"}}}}
    path.write_text(json.dumps(original))
    with pytest.raises(components.RenderRefused, match="unowned MCP server collisions"):
        companions.sync("claude", root, target)
    assert json.loads(path.read_text()) == original
    assert not (target / components.ledger_name(root)).exists()


def test_an_identical_unowned_server_is_not_claimed_or_removed(selected):
    root, target = selected
    path = target.parent / ".claude.json"
    original = {"mcpServers": {"example": {"command": "echo", "args": ["fixture"], "type": "stdio"}}}
    path.write_text(json.dumps(original))
    assert companions.sync("claude", root, target) == []
    assert not (target / components.ledger_name(root)).exists()
    (root / "components.json").write_text('{"mcp_servers": []}')
    companions.sync("claude", root, target)
    assert json.loads(path.read_text()) == original
