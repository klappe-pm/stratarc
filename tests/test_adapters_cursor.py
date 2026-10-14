"""Tests for the Cursor hook adapter, using temporary directories only."""

import json
import tempfile
import unittest
from pathlib import Path

import pytest


from stratarc.adapters import cursor
from stratarc.adapters._common import owned_dir_entries


@pytest.fixture(autouse=True)
def _isolated_home(stratarc_home):
    """Every test reads the home through STRATARC_HOME, never the real one."""
    return stratarc_home



class CursorHookAdapterTest(unittest.TestCase):
    def test_copies_the_selected_rules(self):
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as target_dir,
        ):
            source, target = Path(source_dir), Path(target_dir)
            rules = source / "rules"
            rules.mkdir()
            rule_text = "# keep-answers-short\n\nKeep answers short.\n"
            (rules / "keep-answers-short.md").write_text(rule_text)
            (rules / "README.md").write_text("# rules\n")

            cursor.sync(source, target)

            destination = target / "rules" / "keep-answers-short.md"
            self.assertEqual(destination.read_text(), rule_text)
            self.assertFalse((target / "rules" / "README.md").exists())

    def test_rewrites_and_merges_hook_configuration(self):
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as target_dir,
        ):
            source, target = Path(source_dir), Path(target_dir)
            hooks = source / "hooks"
            hooks.mkdir()
            (hooks / "guard.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            (hooks / "hooks.json").write_text(
                json.dumps(
                    {
                        "PreToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "$HOME/.claude/hooks/guard.sh",
                                        "timeout": 3,
                                    }
                                ],
                            }
                        ]
                    }
                )
            )
            (target / "hooks.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "preToolUse": [{"hooks": [{"command": "foreign-hook"}]}]
                        },
                    }
                )
            )

            cursor.sync(source, target)

            result = json.loads((target / "hooks.json").read_text())
            entries = result["hooks"]["preToolUse"]
            self.assertIn(
                {"command": "$HOME/.cursor/hooks/guard.sh", "matcher": "Write", "timeout": 3},
                entries,
            )
            # A foreign group in the shape Cursor ignores is flattened too:
            # one grouped entry leaves the whole file inert.
            self.assertIn({"command": "foreign-hook"}, entries)
            self.assertTrue((target / "hooks" / "guard.sh").exists())


class CursorHookShapeTest(unittest.TestCase):
    """Cursor reads flat hook entries, and has session events.

    Live checks with cursor-agent 2026.07.23-e383d2b on 2026-09-23, each in a
    scratch project whose .cursor/hooks.json recorded every payload:
      - flat entries ({"command": ..., "matcher": ...}) under sessionStart,
        preToolUse and sessionEnd all fired, and sessionStart's
        additional_context reached the model;
      - the same file with Claude-shaped groups ({"matcher", "hooks": [...]})
        fired nothing at all, not even its one flat entry.
    The adapter wrote Claude-shaped groups, so the deployed hooks were inert.
    """

    def _sync(self, canonical: dict, existing: dict | None = None) -> dict:
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as target_dir,
        ):
            source, target = Path(source_dir), Path(target_dir)
            (source / "hooks").mkdir()
            for name in ("guard.sh", "session-start.sh"):
                (source / "hooks" / name).write_text("#!/usr/bin/env bash\nexit 0\n")
            (source / "hooks" / "hooks.json").write_text(json.dumps(canonical))
            if existing is not None:
                (target / "hooks.json").write_text(json.dumps(existing))
            cursor.sync(source, target)
            return json.loads((target / "hooks.json").read_text())

    def test_every_written_entry_is_flat(self):
        result = self._sync(
            {
                "PreToolUse": [
                    {
                        "matcher": "Write|Edit|NotebookEdit",
                        "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/guard.sh", "timeout": 3}],
                    },
                    {"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/guard.sh"}]},
                ],
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/session-start.sh", "timeout": 5}]}
                ],
            }
        )
        self.assertEqual(
            result["hooks"]["preToolUse"],
            [
                {"command": "$HOME/.cursor/hooks/guard.sh", "matcher": "Write|NotebookEdit", "timeout": 3},
                {"command": "$HOME/.cursor/hooks/guard.sh"},
            ],
        )
        self.assertEqual(
            result["hooks"]["sessionStart"],
            [{"command": "$HOME/.cursor/hooks/session-start.sh", "timeout": 5}],
        )
        for entries in result["hooks"].values():
            for entry in entries:
                self.assertIn("command", entry)
                self.assertNotIn("hooks", entry)

    def test_matcher_names_follow_cursor_tool_names(self):
        self.assertEqual(cursor._cursor_matcher("Bash|mcp__github__.*"), "Shell|MCP:.*")
        self.assertEqual(cursor._cursor_matcher("Task"), "Task")
        self.assertIsNone(cursor._cursor_matcher(None))
        self.assertIsNone(cursor._cursor_matcher("*"))

    def test_a_previously_written_grouped_entry_of_ours_is_replaced(self):
        result = self._sync(
            {"PreToolUse": [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/guard.sh"}]}]},
            existing={
                "version": 1,
                "hooks": {
                    "preToolUse": [
                        {"hooks": [{"type": "command", "command": "$HOME/.cursor/hooks/guard.sh"}]},
                        {"command": "foreign-flat", "timeout": 5},
                    ]
                },
            },
        )
        self.assertEqual(
            result["hooks"]["preToolUse"],
            [{"command": "$HOME/.cursor/hooks/guard.sh"}, {"command": "foreign-flat", "timeout": 5}],
        )


class TestOwnedOutputs(unittest.TestCase):
    """owned_outputs names exactly the rules and hooks sync() writes."""

    def test_owned_directories_match_a_fixture_source(self):
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as target_dir,
        ):
            source, target = Path(source_dir), Path(target_dir)
            (source / "rules").mkdir()
            (source / "rules" / "keep-answers-short.md").write_text("rule\n")
            (source / "rules" / "README.md").write_text("readme\n")
            (source / "hooks").mkdir()
            (source / "hooks" / "guard.sh").write_text("#!/bin/sh\n")
            (source / "hooks" / "guard.test.sh").write_text("#!/bin/sh\n")

            owned = {od.kind: od for od in cursor.owned_outputs(source, target)}

            self.assertEqual(owned["rule"].path, target / "rules")
            self.assertEqual(owned["rule"].names, frozenset({"keep-answers-short.md"}))
            self.assertEqual(owned["hook"].path, target / "hooks")
            self.assertEqual(owned["hook"].names, frozenset({"guard.sh"}))
            self.assertNotIn("skill", owned)
            self.assertNotIn("agent", owned)
            self.assertNotIn("command", owned)

    def test_a_target_only_hook_is_reported_as_an_orphan(self):
        with (
            tempfile.TemporaryDirectory() as source_dir,
            tempfile.TemporaryDirectory() as target_dir,
        ):
            source, target = Path(source_dir), Path(target_dir)
            (source / "hooks").mkdir()
            (source / "hooks" / "guard.sh").write_text("#!/bin/sh\n")
            cursor.sync(source, target)
            (target / "hooks" / "stale.sh").write_text("#!/bin/sh\n")
            owned = {od.kind: od for od in cursor.owned_outputs(source, target)}
            present = owned_dir_entries(owned["hook"].path)
            self.assertEqual(present - owned["hook"].names, {"stale.sh"})
