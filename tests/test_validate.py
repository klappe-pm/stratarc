"""Tests for the source validator: each check gets its own fixture tree, shown failing before the defect is corrected and clean after.

Every tree here is a temporary fixture. The worked example under examples/ is the one tree read from the repository, and only to show that a published example passes the gate the sync runs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from stratarc import validate as vs


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def by_check(items: list[dict], check: str) -> list[dict]:
    return [item for item in items if item["check"] == check]




class TestAgentTools:
    def test_missing_line_and_lowercase_name_fail(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/missing-tools.md", "---\nname: missing-tools\ndescription: does a thing.\nmodel: sonnet\n---\n\n# missing-tools\n")
        write(tmp_path, "agents/bad-name.md", "---\nname: bad-name\ndescription: does a thing.\ntools: read, Grep\nmodel: sonnet\n---\n\n# bad-name\n")
        items = by_check(vs.check_agent_tools(tmp_path), "agent-tools-declaration")
        assert any("missing-tools.md" in item["path"] and "no tools" in item["message"] for item in items)
        assert any("bad-name.md" in item["path"] and "'read'" in item["message"] for item in items)

    def test_corrected_fixture_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/missing-tools.md", "---\nname: missing-tools\ndescription: does a thing.\ntools: Read, Glob\nmodel: sonnet\n---\n\n# missing-tools\n")
        write(tmp_path, "agents/bad-name.md", "---\nname: bad-name\ndescription: does a thing.\ntools: Read, Grep\nmodel: sonnet\n---\n\n# bad-name\n")
        assert vs.check_agent_tools(tmp_path) == []

    def test_mcp_tool_names_pass_and_a_malformed_one_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/graph.md", "---\nname: graph\ndescription: does a thing.\ntools: Read, mcp__code-index__search_graph\nmodel: sonnet\n---\n\n# graph\n")
        write(tmp_path, "agents/broken.md", "---\nname: broken\ndescription: does a thing.\ntools: Read, mcp__nothing\nmodel: sonnet\n---\n\n# broken\n")
        items = by_check(vs.check_agent_tools(tmp_path), "agent-tools-declaration")
        assert [item["path"].split(":")[0] for item in items] == ["agents/broken.md"]

    def test_a_file_without_frontmatter_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/bare.md", "# bare\n")
        items = by_check(vs.check_agent_tools(tmp_path), "agent-tools-declaration")
        assert [item["path"] for item in items] == ["agents/bare.md:1"]

    def test_no_agents_directory_is_no_finding(self, tmp_path: Path) -> None:
        assert vs.check_agent_tools(tmp_path) == []

    def test_the_directory_readme_is_not_an_agent_definition(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/README.md", "# agents\n\nWhat this directory holds.\n")
        assert vs.check_agent_tools(tmp_path) == []


class TestAgentToolUse:
    BODY = "\n# verifier\n\n1. Read the project files.\n2. Use WebFetch to reference the official docs.\n3. Keep a TodoWrite-style checklist.\n\n```text\nUse WebSearch here: inside a fence this is an example, not an instruction.\n```\n"

    def test_body_tool_missing_from_the_declaration_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/verifier.md", "---\nname: verifier\ndescription: checks a thing.\ntools: Read, Grep, Glob, Bash\n---\n" + self.BODY)
        write(tmp_path, "commands/fetcher.md", "---\ndescription: fetches a thing.\nallowed-tools: Read, Bash\n---\n\n# fetcher\n\nFetch the page with `WebFetch`.\n")
        findings = by_check(vs.check_agent_tool_use(tmp_path), "agent-tool-undeclared")
        assert [(item["path"], "WebFetch" in item["message"]) for item in findings] == [("agents/verifier.md:10", True), ("commands/fetcher.md:8", True)]

    def test_declared_tool_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/verifier.md", "---\nname: verifier\ndescription: checks a thing.\ntools: Read, Grep, Glob, Bash, WebFetch\n---\n" + self.BODY)
        assert vs.check_agent_tool_use(tmp_path) == []

    def test_a_command_without_allowed_tools_inherits_every_tool(self, tmp_path: Path) -> None:
        write(tmp_path, "commands/open.md", "---\ndescription: opens a thing.\n---\n\n# open\n\nFetch the page with `WebFetch`.\n")
        assert vs.check_agent_tool_use(tmp_path) == []


class TestAgentFrontmatter:
    def test_plain_description_with_colon_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/broken.md", "---\nname: broken\ndescription: Includes a label: value.\ntools: Read\nmodel: sonnet\n---\n\n# broken\n")
        items = by_check(vs.check_agent_frontmatter(tmp_path), "agent-frontmatter-yaml")
        assert [item["path"] for item in items] == ["agents/broken.md:3"]

    def test_block_description_with_colon_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "agents/fixed.md", "---\nname: fixed\ndescription: >-\n  Includes a label: value.\ntools: Read\nmodel: sonnet\n---\n\n# fixed\n")
        assert vs.check_agent_frontmatter(tmp_path) == []


class TestRulePathsLine:
    def test_leading_paths_line_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/leaky.md", 'paths:\n  - "**/*.sh"\n\n# leaky\n\nbody\n')
        items = by_check(vs.check_rule_paths_line(tmp_path), "rule-leading-paths-line")
        assert [item["path"] for item in items] == ["rules/leaky.md:1"]

    def test_corrected_fixture_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/leaky.md", "# leaky\n\nA paths: mention inside the body is fine; only the leading line is checked.\n")
        assert vs.check_rule_paths_line(tmp_path) == []

    def test_readme_is_not_checked(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/README.md", "paths:\nnot really, this file is exempt\n")
        assert vs.check_rule_paths_line(tmp_path) == []


class TestRuleBindingBudget:
    def test_a_binding_over_the_budget_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/long.md", "# long\n\n## binding\n\n" + "word " * 121 + "\n\n## detail\n\nmore\n")
        items = by_check(vs.check_rule_binding_budget(tmp_path), "rule-binding-budget")
        assert [item["path"] for item in items] == ["rules/long.md"]
        assert "121 words" in items[0]["message"]

    def test_a_binding_at_the_budget_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/fits.md", "# fits\n\n## binding\n\n" + "word " * 120 + "\n\n## detail\n\n" + "more " * 500 + "\n")
        assert vs.check_rule_binding_budget(tmp_path) == []

    def test_a_rule_with_no_binding_section_fails(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/bare.md", "# bare\n\nbody\n")
        assert len(by_check(vs.check_rule_binding_budget(tmp_path), "rule-binding-budget")) == 1


class TestComponentsManifest:
    def test_an_invalid_manifest_is_an_error(self, tmp_path: Path) -> None:
        write(tmp_path, "components.json", '{"version": 2, "budgets": {"turns": -1}}')
        items = by_check(vs.check_components_manifest(tmp_path), "components-manifest")
        assert len(items) == 2
        assert all(item["severity"] == "error" for item in items)

    def test_an_unreadable_manifest_is_an_error(self, tmp_path: Path) -> None:
        write(tmp_path, "components.json", "{not json")
        assert len(by_check(vs.check_components_manifest(tmp_path), "components-manifest")) == 1

    def test_no_manifest_is_no_finding(self, tmp_path: Path) -> None:
        assert vs.check_components_manifest(tmp_path) == []

    def test_a_valid_manifest_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "components.json", '{"version": 1}')
        assert vs.check_components_manifest(tmp_path) == []




class TestRuleTiers:
    def test_missing_manifest_is_skipped_with_an_info_line(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/alpha.md", "# alpha\n")
        findings = vs.check_rule_tiers(tmp_path)
        assert len(findings) == 1
        assert findings[0]["severity"] == "info"
        assert "does not exist" in findings[0]["message"]

    def test_unknown_name_untiered_rule_and_duplicate_fail(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/alpha.md", "# alpha\n")
        write(tmp_path, "rules/beta.md", "# beta\n")
        write(tmp_path, "rules/retired.json", json.dumps({"retired": ["gamma.md"]}))
        write(tmp_path, "rules/tiers.json", json.dumps({"global": ["alpha.md", "ghost.md", "gamma.md"], "common": ["alpha.md"]}))
        items = by_check(vs.check_rule_tiers(tmp_path), "rule-tier-membership")
        assert any("ghost.md" in item["message"] and "not a file" in item["message"] for item in items)
        assert any("gamma.md" in item["message"] and "retired" in item["message"] for item in items)
        assert any("alpha.md" in item["message"] and "more than one tier" in item["message"] for item in items)
        assert any(item["path"] == "rules/beta.md" for item in items)

    def test_corrected_fixture_passes(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/alpha.md", "# alpha\n")
        write(tmp_path, "rules/beta.md", "# beta\n")
        write(tmp_path, "rules/tiers.json", json.dumps({"global": ["alpha.md"], "common": ["beta.md"]}))
        assert vs.check_rule_tiers(tmp_path) == []

    def test_non_string_tier_member_produces_a_finding(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/alpha.md", "# alpha\n")
        write(tmp_path, "rules/tiers.json", json.dumps({"global": ["alpha.md", {"bad": "member"}]}))
        items = by_check(vs.check_rule_tiers(tmp_path), "rule-tier-membership")
        assert any("non-string member" in item["message"] for item in items)

    def test_invalid_json_is_one_error(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/tiers.json", "{nope")
        items = by_check(vs.check_rule_tiers(tmp_path), "rule-tier-membership")
        assert [item["severity"] for item in items] == ["error"]


class TestReferenceGraphDelegation:
    def test_errors_pass_through_and_warnings_are_dropped(self, tmp_path: Path) -> None:
        pytest.importorskip("stratarc.source_graph")
        write(tmp_path, "hooks/hooks.json", json.dumps({"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "hooks/vanished.sh"}]}]}))
        write(tmp_path, "docs/notes.md", "# notes\n\nSee [gone](scripts/gone.py) for the old approach.\n")
        findings = vs.check_reference_graph(tmp_path)
        errors = by_check(findings, "dangling-reference")
        assert any(item["path"] == "hooks/hooks.json" for item in errors)
        assert not any(item["path"] == "docs/notes.md" for item in findings), "a warning-level doc reference must not surface here"
        assert all(item["severity"] == "error" for item in findings)

    def test_clean_tree_has_no_findings(self, tmp_path: Path) -> None:
        pytest.importorskip("stratarc.source_graph")
        write(tmp_path, "scripts/tool.py", '"""Tool."""\n')
        assert vs.check_reference_graph(tmp_path) == []

    def test_a_graph_that_is_not_installed_is_an_info_skip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def missing(name: str):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        monkeypatch.setattr(vs.importlib, "import_module", missing)
        findings = vs.check_reference_graph(tmp_path)
        assert [(item["severity"], item["check"]) for item in findings] == [("info", "reference-graph")]


GOOD_SHA = "11d5960a326750d5838078e36cf38b85af677262"




class TestMainEntryPoint:
    def test_strict_exits_nonzero_on_error_and_zero_without(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(tmp_path, "agents/bad.md", "---\nname: bad\ndescription: does a thing.\nmodel: sonnet\n---\n\n# bad\n")
        assert vs.main(["--root", str(tmp_path), "--strict"]) == 1
        assert "agent-tools-declaration" in capsys.readouterr().out
        assert vs.main(["--root", str(tmp_path)]) == 0
        assert "validate:" in capsys.readouterr().out

    def test_clean_tree_exits_zero_even_strict(self, tmp_path: Path) -> None:
        assert vs.main(["--root", str(tmp_path), "--strict"]) == 0

    def test_the_root_defaults_to_the_resolved_source_root(self, source_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        write(source_root, "agents/bad.md", "---\nname: bad\ndescription: does a thing.\nmodel: sonnet\n---\n\n# bad\n")
        assert vs.main(["--strict"]) == 1
        assert "agents/bad.md" in capsys.readouterr().out

    def test_the_root_is_bound_as_the_source_root_while_it_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STRATARC_SOURCE", "/previous/value")
        seen: list[str | None] = []
        monkeypatch.setattr(vs, "CHECKS", (lambda root: seen.append(os.environ.get("STRATARC_SOURCE")) or [],))
        vs.main(["--root", str(tmp_path)])
        assert seen == [str(tmp_path.resolve())]
        assert os.environ["STRATARC_SOURCE"] == "/previous/value"

    def test_an_unset_source_variable_is_unset_again_afterwards(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("STRATARC_SOURCE", raising=False)
        with vs.bound_source(tmp_path):
            assert os.environ["STRATARC_SOURCE"] == str(tmp_path)
        assert "STRATARC_SOURCE" not in os.environ

    def test_the_worked_example_passes_the_generic_strict_gate(self, repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert vs.main(["--root", str(repo_root / "examples" / "notes-cli" / "source"), "--strict", "--checks", "generic"]) == 0
        assert "0 errors" in capsys.readouterr().out


PRIVATE_MODULE = (Path(__file__).resolve().parent / "fixtures" / "validate" / "private-checks" / "validate_checks.py").read_text(encoding="utf-8")


class TestPrivateChecks:
    """A source root adds checks in scripts/private/validate_checks.py; --checks selects which class runs."""

    BAD_AGENT = "---\nname: bad\ndescription: does a thing.\nmodel: sonnet\n---\n\n# bad\n"

    def test_every_built_in_check_is_listed_once(self) -> None:
        names = [check.__name__ for check in vs.CHECKS]
        assert len(names) == len(set(names))
        module_checks = {
            name
            for name in dir(vs)
            if name.startswith("check_") and callable(getattr(vs, name)) and name not in ("check_frontmatter_keys", "check_provenance_shape", "check_headings", "check_one_doc")
        }
        assert module_checks == set(names)

    def test_the_built_in_set_carries_no_user_input(self) -> None:
        for gone in ("PRIVATE_INPUTS", "has_private_inputs", "check_loadout_budgets", "check_project_remotes"):
            assert not hasattr(vs, gone)

    def test_no_module_is_no_checks_and_no_findings(self, tmp_path: Path) -> None:
        assert vs.private_checks(tmp_path) == ([], [])
        assert vs.run_private(tmp_path) == []

    def _root_with_module(self, tmp_path: Path, text: str = PRIVATE_MODULE) -> Path:
        write(tmp_path, vs.PRIVATE_CHECKS_PATH, text)
        write(tmp_path, "widget.txt", "")
        write(tmp_path, "agents/bad.md", self.BAD_AGENT)
        return tmp_path

    def test_the_modules_checks_run_under_private_and_all(self, tmp_path: Path) -> None:
        root = self._root_with_module(tmp_path)
        assert [item["check"] for item in vs.run_all(root, "private")] == ["widget"]
        assert {"widget", "agent-tools-declaration"} <= {item["check"] for item in vs.run_all(root, "all")}
        assert {"widget", "agent-tools-declaration"} <= {item["check"] for item in vs.run_all(root)}

    def test_generic_skips_the_private_defect(self, tmp_path: Path) -> None:
        root = self._root_with_module(tmp_path)
        checks = {item["check"] for item in vs.run_all(root, "generic")}
        assert "agent-tools-declaration" in checks
        assert "widget" not in checks

    def test_private_skips_the_generic_defect(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        root = self._root_with_module(tmp_path)
        assert vs.main(["--root", str(root), "--strict", "--checks", "private"]) == 1
        out = capsys.readouterr().out
        assert "widget" in out
        assert "agent-tools-declaration" not in out

    def test_a_module_that_cannot_be_imported_is_an_error_finding(self, tmp_path: Path) -> None:
        write(tmp_path, vs.PRIVATE_CHECKS_PATH, "raise RuntimeError('boom')\n")
        items = vs.run_all(tmp_path, "private")
        assert [(item["severity"], item["check"], item["path"]) for item in items] == [("error", "private-checks", vs.PRIVATE_CHECKS_PATH)]
        assert "boom" in items[0]["message"]

    def test_a_module_without_the_declaration_is_an_error_finding(self, tmp_path: Path) -> None:
        write(tmp_path, vs.PRIVATE_CHECKS_PATH, "CHECKS = []\n")
        items = vs.run_all(tmp_path, "private")
        assert len(items) == 1
        assert "VALIDATE_CHECKS" in items[0]["message"]

    def test_a_declaration_of_non_callables_is_an_error_finding(self, tmp_path: Path) -> None:
        write(tmp_path, vs.PRIVATE_CHECKS_PATH, "VALIDATE_CHECKS = ['not callable']\n")
        assert len(vs.run_all(tmp_path, "private")) == 1

    def test_a_check_that_raises_is_one_finding_and_the_rest_still_run(self, tmp_path: Path) -> None:
        module = (
            "from stratarc.validate import finding\n\n\n"
            "def check_breaks(root):\n    raise ValueError('bad input')\n\n\n"
            "def check_fine(root):\n    return [finding('warning', 'fine', 'x', 'still ran')]\n\n\n"
            "VALIDATE_CHECKS = [check_breaks, check_fine]\n"
        )
        write(tmp_path, vs.PRIVATE_CHECKS_PATH, module)
        items = vs.run_all(tmp_path, "private")
        assert {item["check"] for item in items} == {"private-checks", "fine"}
        assert any("check_breaks raised ValueError" in item["message"] for item in items)

    def test_an_unknown_class_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            vs.run_all(tmp_path, "some")

    def test_findings_sort_errors_first(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/alpha.md", "# alpha\n")
        write(tmp_path, "agents/bad.md", self.BAD_AGENT)
        severities = [item["severity"] for item in vs.run_all(tmp_path, "generic")]
        assert severities == sorted(severities, key=vs.SEVERITY_ORDER.get)
        assert severities[0] == "error"

    def test_an_example_root_with_a_projects_root_passes_generic_strict(self, tmp_path: Path) -> None:
        write(tmp_path, "rules/example.md", "# example\n\n## binding\n\nBody.\n")
        write(tmp_path, "rules/tiers.json", json.dumps({"common": ["example.md"]}))
        (tmp_path / "projects-root" / "example").mkdir(parents=True)
        assert vs.main(["--root", str(tmp_path), "--strict", "--checks", "generic"]) == 0


class TestRuntimeConfig:
    def test_a_runtime_table_with_no_adapter_is_an_error(self, tmp_path: Path) -> None:
        write(tmp_path, "stratarc.toml", "[runtimes.acme-agent]\nenabled = true\n")
        findings = by_check(vs.check_runtime_config(tmp_path), "runtime-config")
        assert [item["severity"] for item in findings] == ["error"]
        assert "acme-agent" in findings[0]["message"] and "adapters/acme-agent.py" in findings[0]["message"]

    def test_a_packaged_runtime_and_a_source_adapter_are_known(self, tmp_path: Path) -> None:
        write(tmp_path, "stratarc.toml", "[runtimes.claude]\nenabled = true\n[runtimes.acme]\nenabled = true\n")
        write(tmp_path, "adapters/acme.py", 'RUNTIME = {"name": "acme", "target": ".acme", "hook_registry": None, "hook_events": []}\n')
        assert vs.check_runtime_config(tmp_path) == []
