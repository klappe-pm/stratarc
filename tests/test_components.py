"""Tests for stratarc.components, the loader and checker for components.json.

The manifest declares the sections and the entry shape; a loadout may name only what it declares. Every test runs on a fixture document or on tests/fixtures/components/manifest.json, never on a live manifest.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from stratarc import components
from stratarc.adapters import _common

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_DIR = FIXTURES / "components"
FIXTURE_MANIFEST = FIXTURE_DIR / "manifest.json"
SIXTH_ADAPTER = FIXTURES / "adapters" / "registry" / "sixth.py"


def fixture_adapters_with_a_sixth(directory: Path) -> Path:
    """A copy of the packaged adapter files plus the registry fixture's sixth adapter."""
    fixture = directory / "adapters"
    fixture.mkdir()
    packaged = Path(_common.__file__).parent
    for path in packaged.glob("*.py"):
        shutil.copyfile(path, fixture / path.name)
    shutil.copyfile(SIXTH_ADAPTER, fixture / "sixth.py")
    return fixture


def server(name, **extra):
    entry = {"name": name, "runtimes": ["claude", "codex"], "owner": "example", "wanted": True, "command": "npx", "args": ["-y", name]}
    entry.update(extra)
    return entry


class TestFixtureManifest:
    """The fixture manifest, grown from the example, carries one entry of every section and every top-level block."""

    @pytest.fixture(autouse=True)
    def document(self):
        self.document = components.load(FIXTURE_MANIFEST)

    def entry(self, section, name):
        found = [e for e in self.document.get(section) or [] if e.get("name") == name]
        assert len(found) == 1, f"{section} declares {name} once"
        return found[0]

    def test_it_validates(self):
        assert components.validate(self.document) == []

    def test_every_section_is_represented(self):
        for section in components.SECTIONS:
            assert self.document.get(section), section

    def test_runtime_settings_carry_the_status_line(self):
        assert "statusLine" in self.document["runtime_settings"]["claude"]["settings"]


class TestValidate:
    def test_load_reads_the_source_roots_manifest_by_default(self, source_root):
        shutil.copyfile(FIXTURE_MANIFEST, source_root / "components.json")
        assert components.load()["version"] == 1
        assert components.validate(components.load()) == []

    def test_a_well_formed_manifest_has_no_errors(self):
        document = {"version": 1, "mcp_servers": [server("github", env={"GITHUB_TOKEN": "secret://github/default"})]}
        assert components.validate(document) == []

    def test_a_fixture_manifest_written_to_disk_loads_and_validates(self, tmp_path):
        """A manifest carrying one entry of every section plus every top-level
        block, written to a temporary directory and read back through load():
        the validator's full path."""
        document = {
            "version": 1,
            "runtime_settings": {"claude": {"settings": {"statusLine": {"type": "command"}}}},
            **{section: [entry] for section, entry in VALID.items()},
        }
        path = tmp_path / "components.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        loaded = components.load(path)
        assert components.validate(loaded) == []
        assert sorted(components.declared(loaded, "dependencies")) == ["ripgrep"]

    def test_entry_problems_are_named(self):
        document = {
            "version": 1,
            "mcp_servers": [
                {"name": "a", "runtimes": ["claude"], "owner": "x", "wanted": True},
                server("b", runtimes=["emacs"]),
                server("b"),
                server("c", wanted="yes"),
            ],
            "gadgets": [],
        }
        joined = "\n".join(components.validate(document))
        assert "mcp_servers a: needs a command or a url" in joined
        assert "unknown runtime emacs" in joined
        assert "declared twice" in joined
        assert "wanted" in joined
        assert "unknown section gadgets" in joined

    def test_a_literal_secret_in_env_is_refused(self):
        literal = "sk-" + "a" * 40
        document = {"version": 1, "mcp_servers": [server("leaky", env={"API_KEY": literal})]}
        errors = components.validate(document)
        assert any("secret://" in e for e in errors), errors
        # The value itself never appears in a message.
        assert not any(literal in e for e in errors)


def common(**extra):
    entry = {"name": "x", "runtimes": ["claude"], "owner": "example", "wanted": True}
    entry.update(extra)
    return entry


VALID = {
    "mcp_servers": server("github"),
    "plugins": common(name="superpowers", marketplace="claude-plugins-official"),
    "foreign_hooks": common(name="vendortool", owner="vendortool", wanted=False, match="vendortool-hook"),
    "third_party_skills": common(name="impeccable", owner="impeccable", installer="npx impeccable install"),
    "dependencies": common(name="ripgrep", command="rg", install="brew install ripgrep", version="14.1.1"),
}


class TestSectionSchemas:
    """Every section has a checked shape, and an unknown key is an error so a typo
    cannot silently disable a check."""

    def errors(self, section, entry):
        return "\n".join(components.validate({"version": 1, section: [entry]}))

    def test_one_well_formed_entry_of_every_section_is_valid(self):
        for section, entry in VALID.items():
            assert self.errors(section, entry) == ""

    def test_a_dependency_without_install_is_refused(self):
        entry = dict(VALID["dependencies"])
        del entry["install"]
        assert "dependencies ripgrep: needs install" in self.errors("dependencies", entry)

    def test_a_dependency_without_command_is_refused(self):
        entry = dict(VALID["dependencies"])
        del entry["command"]
        assert "dependencies ripgrep: needs command" in self.errors("dependencies", entry)

    def test_a_dependency_without_a_pinned_version_is_refused(self):
        # The image pins every tool from this list, so an unpinned entry cannot be built.
        entry = dict(VALID["dependencies"])
        del entry["version"]
        assert "dependencies ripgrep: needs version" in self.errors("dependencies", entry)

    def test_a_dependency_platform_is_optional_and_must_be_darwin_or_linux(self):
        # A keyring daemon is a container-only (Linux) addition; every other
        # dependency carries no platform key and applies everywhere.
        assert self.errors("dependencies", VALID["dependencies"]) == ""
        assert self.errors("dependencies", dict(VALID["dependencies"], platform="linux")) == ""
        assert "dependencies ripgrep: platform must be darwin or linux" in self.errors("dependencies", dict(VALID["dependencies"], platform="container"))

    def test_a_version_command_is_a_string(self):
        assert self.errors("dependencies", dict(VALID["dependencies"], version_command="rg --version")) == ""
        assert "version_command must be a command string" in self.errors("dependencies", dict(VALID["dependencies"], version_command=["rg"]))

    def test_a_foreign_hook_without_match_is_refused(self):
        entry = dict(VALID["foreign_hooks"])
        del entry["match"]
        assert "foreign_hooks vendortool: needs match" in self.errors("foreign_hooks", entry)

    def test_a_third_party_skill_without_installer_is_refused(self):
        entry = dict(VALID["third_party_skills"])
        del entry["installer"]
        assert "third_party_skills impeccable: needs installer" in self.errors("third_party_skills", entry)

    def test_a_wanted_foreign_hook_may_carry_the_registration_an_adapter_renders(self):
        # A wanted foreign hook is not always the source root's to render: one
        # it only recognizes when another tool installs it (found by match,
        # kept by prune) carries no registration, and that is not an error,
        # so validate must still accept a wanted foreign hook with no
        # registration or prune would refuse any manifest that has one.
        wanted = common(name="reviewer-agent-hook", owner="acme", match="reviewer agent-hook run", runtimes=["claude", "codex"])
        assert self.errors("foreign_hooks", wanted) == ""
        good = dict(wanted, registration={"claude": "scripts/reviewer/claude.json", "codex": "scripts/reviewer/codex.json"})
        assert self.errors("foreign_hooks", good) == ""

    def test_an_unwanted_foreign_hook_needs_no_registration(self):
        assert self.errors("foreign_hooks", VALID["foreign_hooks"]) == ""

    def test_a_registration_names_only_runtimes_the_entry_declares(self):
        entry = common(name="reviewer-agent-hook", owner="acme", match="reviewer agent-hook run", runtimes=["claude"])
        unknown = dict(entry, registration={"claude": "scripts/reviewer/claude.json", "emacs": "scripts/reviewer/emacs.json"})
        assert "registration: unknown runtime emacs" in self.errors("foreign_hooks", unknown)
        undeclared = dict(entry, registration={"claude": "scripts/reviewer/claude.json", "codex": "scripts/reviewer/codex.json"})
        assert "registration: codex is not in runtimes" in self.errors("foreign_hooks", undeclared)

    def test_a_registration_maps_each_runtime_to_a_path(self):
        entry = common(name="reviewer-agent-hook", owner="acme", match="reviewer agent-hook run", runtimes=["claude"])
        assert "registration must be an object" in self.errors("foreign_hooks", dict(entry, registration="scripts/reviewer/claude.json"))
        assert "registration claude must name the captured file" in self.errors("foreign_hooks", dict(entry, registration={"claude": ""}))

    def test_a_third_party_skill_may_name_the_directories_it_installs(self):
        # A tool may install several skill directories under one entry, so the
        # entry names them and the adapters' inventory matches any of them.
        entry = common(name="reviewer", owner="acme", installer="reviewer skills install", skills=["reviewer-review", "reviewer-fix"])
        assert self.errors("third_party_skills", entry) == ""
        assert "skills must be a list of directory names" in self.errors("third_party_skills", dict(entry, skills="reviewer-review"))
        assert "skills must be a list of directory names" in self.errors("third_party_skills", dict(entry, skills=["reviewer-review", ""]))

    def test_a_plugin_needs_a_marketplace(self):
        entry = dict(VALID["plugins"])
        del entry["marketplace"]
        assert "plugins superpowers: needs marketplace" in self.errors("plugins", entry)

    def test_an_opencode_file_plugin_carries_a_path_instead(self):
        entry = common(name="notify", runtimes=["opencode"], path="plugins/notify.ts")
        assert self.errors("plugins", entry) == ""
        assert "path is only for OpenCode file plugins" in self.errors("plugins", dict(entry, runtimes=["claude", "opencode"]))

    def test_a_hosted_mcp_server_needs_no_command_and_hosted_is_a_boolean(self):
        hosted = common(name="gmail", hosted=True)
        assert self.errors("mcp_servers", hosted) == ""
        assert "hosted must be true or false" in self.errors("mcp_servers", server("github", hosted="yes"))

    def test_a_rendered_mcp_server_name_is_a_bare_key(self):
        """The adapters write the name as a TOML table key
        ([mcp_servers.<name>]) and a JSON key; a name with a dot, space or
        bracket would name a different table. A hosted connector is never
        rendered, so its name is the provider's."""
        assert self.errors("mcp_servers", server("my-server_2")) == ""
        for bad in ("my.server", "my server", "srv]", ""):
            if bad:
                assert "name must be letters, digits, - or _" in self.errors("mcp_servers", server(bad))
        assert self.errors("mcp_servers", common(name="claude.ai Gmail", hosted=True)) == ""

    def test_an_unknown_key_is_an_error_in_every_section(self):
        for section, entry in VALID.items():
            joined = self.errors(section, dict(entry, wnated=False))
            assert "unknown key wnated" in joined

    def test_runtime_settings_are_keyed_by_a_known_runtime(self):
        joined = "\n".join(components.validate({"version": 1, "runtime_settings": {"emacs": {}}}))
        assert "runtime_settings: unknown runtime emacs" in joined
        assert components.validate({"version": 1, "runtime_settings": {"claude": {}}}) == []


class TestRuntimeSettingsSchema:
    """runtime_settings.<runtime> accepts exactly model, subagent_model, aliases and settings (plus provider for opencode)."""

    def errors(self, block):
        return "\n".join(components.validate({"version": 1, "runtime_settings": {"codex": block}}))

    def test_the_four_keys_are_accepted(self):
        block = {
            "model": "gpt-5",
            "subagent_model": "gpt-5-mini",
            "aliases": {"opus": "gpt-5", "sonnet": "gpt-5-mini"},
            "settings": {"anything": {"nested": True}},
        }
        assert self.errors(block) == ""

    def test_an_unknown_key_is_rejected(self):
        assert "runtime_settings codex: unknown key statusLine" in self.errors({"statusLine": {}})

    def test_models_must_be_nonempty_strings(self):
        for key in ("model", "subagent_model"):
            for bad in ("", 5, ["opus"]):
                assert f"runtime_settings codex: {key} must be a model name" in self.errors({key: bad})

    def test_inheritance_sentinels_are_not_model_names(self):
        for key in ("model", "subagent_model"):
            for sentinel in ("inherit", "default"):
                assert f"runtime_settings codex: {key} must be a model name" in self.errors({key: sentinel})

    def test_aliases_map_names_to_nonempty_strings(self):
        for bad in (["opus"], {"opus": ""}, {"opus": 1}, {"": "gpt-5"}):
            assert "runtime_settings codex: aliases must map each short name to a model name" in self.errors({"aliases": bad})

    def test_settings_must_be_an_object(self):
        assert "runtime_settings codex: settings must be an object" in self.errors({"settings": []})

    def errors_for(self, runtime, block):
        return "\n".join(components.validate({"version": 1, "runtime_settings": {runtime: block}}))

    def test_provider_maps_ids_to_objects_for_opencode(self):
        block = {"provider": {"local-gateway": {"npm": "@ai-sdk/openai-compatible", "options": {"baseURL": "http://127.0.0.1:3001/v1"}}}}
        assert self.errors_for("opencode", block) == ""

    def test_provider_must_map_each_id_to_an_object(self):
        assert "runtime_settings opencode: provider must map each provider id to an object" in self.errors_for("opencode", {"provider": {"local-gateway": ["not", "an", "object"]}})
        assert "runtime_settings opencode: provider must map each provider id to an object" in self.errors_for("opencode", {"provider": ["local-gateway"]})

    def test_provider_is_only_accepted_for_opencode(self):
        assert "runtime_settings codex: unknown key provider" in self.errors_for("codex", {"provider": {}})








class TestRuntimeRegistry:
    """components reads the adapters' runtime registry instead of its own list."""

    def test_the_runtimes_are_the_registry(self):
        assert sorted(components.known_runtimes()) == sorted(_common.runtime_registry())

    def test_a_sixth_adapter_is_accepted_without_other_edits(self, tmp_path):
        document = {"version": 1, "mcp_servers": [server("github", runtimes=["sixth"])], "runtime_settings": {"sixth": {}}}
        fixture = fixture_adapters_with_a_sixth(tmp_path)
        assert components.validate(document, adapters_dir=fixture) == []
        assert "unknown runtime sixth" in "\n".join(components.validate(document))


class TestDeclared:
    def test_only_wanted_entries_for_the_runtime_are_declared(self):
        document = {
            "version": 1,
            "mcp_servers": [server("one"), server("two", wanted=False), server("three", runtimes=["gemini"])],
        }
        assert sorted(components.declared(document, "mcp_servers")) == ["one", "three"]
        assert sorted(components.declared(document, "mcp_servers", runtime="codex")) == ["one"]

    def test_a_missing_file_loads_as_an_empty_manifest(self, tmp_path):
        document = components.load(tmp_path / "components.json")
        assert components.declared(document, "mcp_servers") == {}

    def test_a_malformed_file_is_an_error_not_an_empty_manifest(self, tmp_path):
        path = tmp_path / "components.json"
        path.write_text("{not json")
        with pytest.raises(components.ManifestError):
            components.load(path)

    def test_a_source_root_with_no_manifest_loads_as_empty(self, source_root):
        assert components.load() == {"version": 1}


