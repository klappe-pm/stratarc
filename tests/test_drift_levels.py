"""Folder level drift rules, `drift explain` and the session start line."""

from __future__ import annotations

import json
import pathlib

from stratarc import drift, drift_levels

LONG = "Every change goes through a pull request and a reviewer before it merges into the main branch of this repository."


def checkout(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    for name, body in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def rules(found: list[dict]) -> list[str]:
    return [f["rule"] for f in found]


def test_a_nested_instruction_file_must_be_declared(tmp_path):
    root = checkout(tmp_path, {"AGENTS.md": "# root\n", "docs/AGENTS.md": "# docs\n"})
    assert rules(drift_levels.check(root, set())) == ["lv-undeclared-nested"]
    assert drift_levels.check(root, {"docs/AGENTS.md"}) == []
    assert drift_levels.check(root, {"docs"}) == []


def test_dot_folders_vendored_folders_and_nested_repositories_are_not_walked(tmp_path):
    root = checkout(tmp_path, {"AGENTS.md": "# root\n", ".claude/AGENTS.md": "x", "node_modules/p/AGENTS.md": "x", "sub/AGENTS.md": "x"})
    (root / "sub" / ".git").mkdir()
    assert [p.relative_to(root).as_posix() for p in drift_levels.instruction_files(root)] == ["AGENTS.md"]


def test_a_copy_that_differs_from_its_sibling_master_is_a_split(tmp_path):
    root = checkout(tmp_path, {"AGENTS.md": "# root\n", "docs/AGENTS.md": "# docs\n", "docs/CODEX.md": "# other\n"})
    found = drift_levels.check(root, {"docs"}, ("AGENTS.md", "CODEX.md"))
    assert rules(found) == ["lv-surface-split"]
    assert drift_levels.check(root, {"docs"}, ("AGENTS.md",)) == []


def test_different_commands_for_the_same_job_conflict_and_overlapping_ones_do_not(tmp_path):
    root = checkout(
        tmp_path,
        {
            "AGENTS.md": "# root\n\n```sh\nnpm install\npytest -q\n```\n",
            "a/AGENTS.md": "# a\n\n```sh\nuv sync\npytest -q\n```\n",
            "b/AGENTS.md": "# b\n\n```sh\nmake test\n```\n",
        },
    )
    found = drift_levels.check(root, {"a", "b"})
    messages = [f["message"] for f in found if f["rule"] == "lv-fact-conflict"]
    assert len(messages) == 2
    assert any("package-manager" in m and "'uv'" in m and "'npm'" in m for m in messages)
    assert any("test" in m and "make test" in m for m in messages)


def test_a_repeated_paragraph_is_restated_and_a_short_one_is_not(tmp_path):
    root = checkout(tmp_path, {"AGENTS.md": f"# root\n\n{LONG}\n\nUse tabs.\n", "docs/AGENTS.md": f"# docs\n\n{LONG}\n\nUse tabs.\n"})
    found = drift_levels.check(root, {"docs"})
    assert rules(found) == ["lv-restated"]


def test_a_reference_is_dead_unless_it_resolves_beside_the_file_or_from_the_root(tmp_path):
    root = checkout(
        tmp_path,
        {
            "AGENTS.md": "See [guide](docs/guide.md) and `docs/gone.md` and `real.py` and `notes.md`.\n",
            "docs/guide.md": "# guide\n",
            "real.py": "",
        },
    )
    found = {f["message"]: f for f in drift_levels.check(root, set())}
    assert len(found) == 2
    assert next(f for m, f in found.items() if "docs/gone.md" in m)["severity"] == "warn"
    assert next(f for m, f in found.items() if "notes.md" in m)["severity"] == "info"


def test_a_mirror_of_the_master_does_not_repeat_the_masters_dead_references(tmp_path):
    body = "See `docs/gone.md`.\n"
    root = checkout(tmp_path, {"AGENTS.md": body, "CODEX.md": body})
    assert rules(drift_levels.check(root, set())) == ["lv-dead-reference"]


def test_explain_lists_the_files_from_the_root_down_and_marks_conflicts(tmp_path):
    root = checkout(
        tmp_path,
        {
            "AGENTS.md": "# root\n\n```sh\nnpm test\n```\n",
            "a/AGENTS.md": "# a\n\n```sh\nyarn test\n```\n",
            "a/b/CLAUDE.md": "# b\n",
            "other/AGENTS.md": "# other\n",
        },
    )
    lines = drift_levels.explain(root, root / "a" / "b" / "file.py")
    assert lines[:3] == ["AGENTS.md", "a/AGENTS.md", "a/b/CLAUDE.md"]
    assert any(line.startswith("conflict lv-fact-conflict") for line in lines[3:])
    assert "other/AGENTS.md" not in lines


def test_the_session_line_is_empty_when_clean_and_cached_by_mtime(tmp_path, monkeypatch):
    root = checkout(tmp_path, {"AGENTS.md": "# root\n", "docs/AGENTS.md": "# docs\n"})
    source = tmp_path / "source"
    monkeypatch.setattr(drift, "report_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(drift.paths, "project_config_dir", lambda r=None: source / "roots")
    line = drift.session_line(source, root)
    assert "1 drift findings (0 at error level) in repo" in line
    (source / "roots" / "repo").mkdir(parents=True)
    (source / "roots" / "repo" / "surfaces.json").write_text(json.dumps({"nested": ["docs/AGENTS.md"]}))
    assert drift.session_line(source, root) == ""
    cache = json.loads((tmp_path / "state" / "session-cache.json").read_text())
    assert cache[str(root)]["line"] == ""


def test_the_session_line_is_empty_outside_a_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(drift, "report_dir", lambda: tmp_path / "state")
    assert drift.session_line(tmp_path, tmp_path / "nowhere") == ""


def test_without_declarations_the_undeclared_nested_rule_is_skipped(tmp_path):
    root = checkout(tmp_path, {"AGENTS.md": "# root\n", "docs/AGENTS.md": "# docs\n"})
    assert rules(drift_levels.check(root, None)) == []
    assert rules(drift_levels.check(root, set())) == ["lv-undeclared-nested"]
