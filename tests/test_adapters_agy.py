"""Tests for the Antigravity CLI adapter, using temporary directories only."""

import json
import tempfile
import unittest
from pathlib import Path

import pytest

from stratarc.adapters import agy
from stratarc.adapters._common import runtime_registry


@pytest.fixture(autouse=True)
def _isolated_home(stratarc_home):
    """Every test reads the home through STRATARC_HOME, never the real one."""
    return stratarc_home


def _stage(source: Path, *, model=None, aliases=None, skill=True) -> None:
    if skill:
        (source / "skills" / "demo").mkdir(parents=True)
        (source / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    block: dict = {}
    if model is not None:
        block["model"] = model
    if aliases is not None:
        block["aliases"] = aliases
    (source / "components.json").write_text(json.dumps({"runtime_settings": {"agy": block}}))


class AgyAdapterTest(unittest.TestCase):
    def test_is_a_registered_bundled_runtime(self):
        registry = runtime_registry()
        self.assertIn("agy", registry)
        self.assertEqual(registry["agy"].relative, ".gemini/antigravity-cli")
        self.assertIsNone(registry["agy"].hook_registry)

    def test_mirrors_skills_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(source)
            self.assertEqual(len(agy.sync(source, target, dry_run=True)), 1)
            self.assertFalse((target / "skills").exists())
            self.assertEqual(len(agy.sync(source, target)), 1)
            self.assertTrue((target / "skills" / "demo" / "SKILL.md").is_file())
            self.assertEqual(agy.sync(source, target), [])

    def test_writes_no_instruction_file(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(source)
            (source / "AGENTS.md").write_text("instructions\n")
            agy.sync(source, target)
            self.assertFalse((target / "AGENTS.md").exists())

    def test_writes_the_aliased_model_and_keeps_other_settings(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(source, model="opus", aliases={"opus": "Claude Opus 4.6 (Thinking)"}, skill=False)
            (target / "settings.json").write_text(json.dumps({"theme": "dark"}))
            self.assertEqual(agy.sync(source, target), ["set settings.json model to Claude Opus 4.6 (Thinking)"])
            self.assertEqual(
                json.loads((target / "settings.json").read_text()),
                {"theme": "dark", "model": "Claude Opus 4.6 (Thinking)"},
            )
            self.assertEqual(agy.sync(source, target), [])

    def test_translates_a_provider_model_id(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(
                source,
                model="google-antigravity/gemini-3.1-pro-high",
                aliases={"google-antigravity/gemini-3.1-pro-high": "Gemini 3.1 Pro (High)"},
                skill=False,
            )
            agy.sync(source, target)
            self.assertEqual(json.loads((target / "settings.json").read_text())["model"], "Gemini 3.1 Pro (High)")

    def test_skips_a_claude_name_with_no_alias_and_an_inherit(self):
        for model in ("sonnet", "inherit", None):
            with self.subTest(model=model):
                with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
                    source, target = Path(source_dir), Path(target_dir)
                    _stage(source, model=model, aliases={"opus": "Claude Opus 4.6 (Thinking)"}, skill=False)
                    self.assertEqual(agy.sync(source, target), [])
                    self.assertFalse((target / "settings.json").exists())

    def test_leaves_a_settings_file_that_is_not_an_object(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(source, model="opus", aliases={"opus": "X"}, skill=False)
            (target / "settings.json").write_text("not json")
            self.assertEqual(agy.sync(source, target), [])
            self.assertEqual((target / "settings.json").read_text(), "not json")

    def test_owns_only_the_skills_directory(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source, target = Path(source_dir), Path(target_dir)
            _stage(source)
            owned = agy.owned_outputs(source, target)
            self.assertEqual([(o.kind, o.path, set(o.names), o.per_item) for o in owned], [("skill", target / "skills", {"demo"}, True)])
