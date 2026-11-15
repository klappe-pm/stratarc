"""SessionEnd is a declared hook event: a registry that names it stages for every
runtime, each adapter delivers it under its native name or drops it on purpose,
and an event no adapter declares is still refused."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from stratarc import sync

SCRIPTS = ("session-start", "session-end")
REGISTRY = {
    "SessionStart": [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/session-start.sh", "timeout": 10}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/session-end.sh", "timeout": 60}]}],
}


@pytest.fixture(autouse=True)
def _isolated_home(stratarc_home: Path) -> Path:
    """Every test reads the home through STRATARC_HOME, never the real one."""
    return stratarc_home


@pytest.fixture
def stage(tmp_path: Path) -> Path:
    """A stage holding the two session hooks and their registry."""
    root = tmp_path / "stage"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "hooks.json").write_text(json.dumps(REGISTRY, indent=2) + "\n")
    for name in SCRIPTS:
        script = root / "hooks" / f"{name}.sh"
        script.write_text("#!/usr/bin/env bash\nexit 0\n")
        script.chmod(0o755)
    return root


def deploy(name: str, stage: Path, home: Path) -> Path:
    """Sync the stage into one runtime, then require a second pass to find nothing to do."""
    module, target = sync.load_runtimes()[name]
    adapter = importlib.import_module(module)
    adapter.sync(stage, target, dry_run=False)
    pending = [action for action in adapter.sync(stage, target, dry_run=True) if "hook" in action.lower() or "settings" in action.lower()]
    assert pending == [], pending
    return target


def commands(groups: list) -> list[str]:
    """Every command in a list of hook groups or flat hook entries."""
    found = []
    for group in groups:
        for entry in group.get("hooks", [group]):
            found.append(entry["command"])
    return found


def test_every_runtime_declares_session_end() -> None:
    for name in sync.load_runtimes():
        assert "SessionEnd" in sync.hook_event_maps().get(name, set()), name


def test_a_registry_with_session_end_leaves_no_runtime_a_gap(stage: Path) -> None:
    for name in sync.load_runtimes():
        assert sync.unmapped_hook_events(stage, name) == set(), name


def test_an_undeclared_event_is_still_a_gap_for_every_runtime(stage: Path) -> None:
    registry = dict(REGISTRY, SessionPaused=[])
    (stage / "hooks" / "hooks.json").write_text(json.dumps(registry))
    for name in sync.load_runtimes():
        assert sync.unmapped_hook_events(stage, name) == {"SessionPaused"}, name


def test_claude_registers_session_end_in_settings(stage: Path, stratarc_home: Path) -> None:
    target = deploy("claude", stage, stratarc_home)
    hooks = json.loads((target / "settings.json").read_text())["hooks"]
    assert commands(hooks["SessionEnd"]) == ["$HOME/.claude/hooks/session-end.sh"]
    assert commands(hooks["SessionStart"]) == ["$HOME/.claude/hooks/session-start.sh"]
    assert (target / "hooks" / "session-end.sh").is_file()


def test_codex_registers_session_end_under_its_own_name(stage: Path, stratarc_home: Path) -> None:
    target = deploy("codex", stage, stratarc_home)
    hooks = json.loads((target / "hooks.json").read_text())["hooks"]
    assert [command for command in commands(hooks["SessionEnd"]) if command.endswith("session-end.sh")] != []
    assert all("/.codex/hooks/" in command for command in commands(hooks["SessionEnd"]))
    assert (target / "hooks" / "session-end.sh").is_file()


def test_cursor_registers_session_end_as_its_camel_case_event(stage: Path, stratarc_home: Path) -> None:
    target = deploy("cursor", stage, stratarc_home)
    hooks = json.loads((target / "hooks.json").read_text())["hooks"]
    assert commands(hooks["sessionEnd"]) == ["$HOME/.cursor/hooks/session-end.sh"]
    assert "SessionEnd" not in hooks
    assert (target / "hooks" / "session-end.sh").is_file()


def test_gemini_registers_session_end_in_settings(stage: Path, stratarc_home: Path) -> None:
    target = deploy("gemini", stage, stratarc_home)
    hooks = json.loads((target / "settings.json").read_text())["hooks"]
    assert any(command.endswith("/hooks/session-end.sh") for command in commands(hooks["SessionEnd"]))
    assert (target / "hooks" / "session-end.sh").is_file()


def test_opencode_carries_the_registry_but_its_bridge_dispatches_no_session_end(stage: Path, stratarc_home: Path) -> None:
    from stratarc.resources import data_dir

    target = deploy("opencode", stage, stratarc_home)
    assert "SessionEnd" in json.loads((target / "hooks" / "hooks.json").read_text())
    bridge = (Path(str(data_dir("hooks"))) / "opencode-runtime-hooks.ts").read_text()
    assert 'dispatch(registry, "SessionStart"' in bridge
    assert '"SessionEnd"' not in bridge
