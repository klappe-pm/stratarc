"""stratarc drift: the finding mappers, the report and the exit status."""

from __future__ import annotations

import datetime
import json

from stratarc import cli, drift

WHEN = datetime.datetime(2026, 10, 27, 9, 0, 0, tzinfo=datetime.timezone.utc)


def test_a_missing_surface_is_an_error_and_a_differing_one_is_stale():
    found = drift.from_surfaces(["verdict: AGENTS.md is missing", "eppal: CLAUDE.md diverges from the master"])
    assert [(f.rule, f.severity, f.project, f.path) for f in found] == [
        ("cp-missing", "error", "verdict", "AGENTS.md"),
        ("cp-stale", "error", "eppal", "CLAUDE.md"),
    ]


def test_the_manifest_lines_map_to_their_rules():
    found = drift.from_manifest(
        [
            "guardline: checkout at ~/projects/guardline is not in the manifest",
            "memo: listed as active, no checkout found",
            "eppal: listed as active but sits under inactive/",
            "eppal: 2 checkouts, a, b",
        ]
    )
    assert [(f.rule, f.severity) for f in found] == [
        ("cp-unregistered", "warn"),
        ("cp-missing", "error"),
        ("cp-layout", "warn"),
        ("cp-layout", "warn"),
    ]


def test_a_lone_skip_line_is_a_fact_and_any_other_action_is_drift():
    assert drift.from_delivery("verdict", ["skip: verdict is active but has no checkout"]) == []
    found = drift.from_delivery("verdict", ["write AGENTS.md", "remove .claude/old.md"])
    assert [f.rule for f in found] == ["cp-stale", "cp-stale"]


def test_a_graph_retired_reference_keeps_its_severity_and_the_evidence_as_the_hint():
    found = drift.from_graph(
        [
            {"severity": "warning", "check": "retired-reference", "node": "AGENTS.md", "message": "names retired rule rules/x.md", "evidence": "AGENTS.md:3"},
            {"severity": "error", "check": "dangling-reference", "node": "hooks/a.sh", "message": "reads b", "evidence": "hooks/a.sh:9"},
        ]
    )
    assert [(f.rule, f.severity) for f in found] == [("in-retired-name", "warn"), ("in-dangling", "error")]
    assert found[0].hint == "evidence: AGENTS.md:3"


def test_findings_are_unique_and_errors_sort_first():
    warn = drift.Finding("cp-unregistered", "warn", "a", "", "m", "h")
    error = drift.Finding("cp-missing", "error", "b", "AGENTS.md", "m", "h")
    assert drift.dedupe([warn, error, warn]) == [error, warn]


def test_the_markdown_report_has_a_row_per_finding_and_escapes_pipes():
    finding = drift.Finding("cp-stale", "error", "verdict", "AGENTS.md", "a | b", "sync")
    body = drift.render_markdown([finding], WHEN)
    assert "1 findings, 1 at error level" in body
    assert "| error | `cp-stale` | verdict | `AGENTS.md` | a / b | sync |" in body
    assert "No drift found." in drift.render_markdown([], WHEN)


def test_the_report_is_written_as_latest_and_as_a_dated_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(drift, "report_dir", lambda: tmp_path / "drift")
    latest = drift.write_report([], WHEN)
    assert latest == tmp_path / "drift" / "latest.md"
    assert sorted(p.name for p in latest.parent.iterdir()) == ["20261027-090000.md", "latest.md"]


def test_the_exit_status_is_1_only_for_an_error_level_finding(tmp_path, monkeypatch, capsys):
    warn = drift.Finding("cp-unregistered", "warn", "a", "", "m", "h")
    error = drift.Finding("cp-missing", "error", "b", "AGENTS.md", "m", "h")
    monkeypatch.setattr(drift, "collect", lambda root: [warn])
    assert drift.main(["--root", str(tmp_path)]) == 0
    monkeypatch.setattr(drift, "collect", lambda root: [warn, error])
    assert drift.main(["--root", str(tmp_path), "--format", "json"]) == 1
    out = capsys.readouterr().out
    assert json.loads(out[out.index("{") :])["findings"][1]["rule"] == "cp-missing"


def test_the_command_line_maps_drift_to_exit_6():
    assert "drift" in cli.PASSTHROUGH
    assert cli._reports_drift("drift", []) is True
