"""Plan and decision record drift, waivers and the staged pre-commit mode."""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess

from stratarc import drift, drift_records

TODAY = datetime.date(2026, 10, 27)


def tree(tmp_path: pathlib.Path, files: dict[str, str], name: str = "repo") -> pathlib.Path:
    root = tmp_path / name
    (root / ".git").mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def record(status: str = "DONE", revised: str = "2026-10-26", kind: str = "plan", extra: str = "") -> str:
    return f"---\ntype: {kind}\nstatus: {status}\ndate-revised: {revised}\n{extra}---\n\n# record\n"


def rules(found: list[dict]) -> list[str]:
    return [f["rule"] for f in found]


def test_frontmatter_reads_scalars_inline_lists_and_dash_lists():
    data = drift_records.frontmatter("---\ntype: plan\ntypes: [plan, decision]\nsupersedes:\n  - a.md\n  - b.md\nstatus: INPRG\n---\nbody\n")
    assert data == {"type": ["plan"], "types": ["plan", "decision"], "supersedes": ["a.md", "b.md"], "status": ["INPRG"]}
    assert drift_records.frontmatter("no frontmatter") == {}


def test_a_pointer_must_name_exactly_one_existing_path(tmp_path):
    root = tree(
        tmp_path,
        {
            "plans/2026-10-01-a.md": record(),
            "plans/OK.pointer": "# the plan\n2026-10-01-a.md\n",
            "plans/GONE.pointer": "2026-10-02-missing.md\n",
            "plans/TWO.pointer": "2026-10-01-a.md\n2026-10-01-b.md\n",
        },
    )
    found = drift_records.check(root, None, TODAY)
    assert sorted(f["path"] for f in found if f["rule"] == "dc-pointer-dangling") == ["plans/GONE.pointer", "plans/TWO.pointer"]


def test_a_dated_name_that_a_pointer_names_must_be_cited_through_the_pointer(tmp_path):
    root = tree(
        tmp_path,
        {
            "plans/2026-10-01-a.md": record(),
            "plans/ACTIVE.pointer": "2026-10-01-a.md\n",
            "AGENTS.md": "Read plans/2026-10-01-a.md first.\n",
            "hooks/start.sh": "cat plans/ACTIVE.pointer\n",
        },
    )
    found = drift_records.check(root, None, TODAY)
    assert [(f["rule"], f["path"]) for f in found] == [("dc-dated-reference", "AGENTS.md")]


def test_supersede_pairs_must_name_each_other(tmp_path):
    root = tree(
        tmp_path,
        {
            "d/old.md": record(kind="decision", extra="superseded-by: new\n"),
            "d/new.md": record(kind="decision"),
            "d/paired-new.md": record(kind="decision", extra="supersedes:\n  - paired-old\n"),
            "d/paired-old.md": record(kind="decision", extra="superseded-by: paired-new\n"),
        },
    )
    found = [f for f in drift_records.check(root, None, TODAY) if f["rule"] == "dc-supersede-unpaired"]
    assert [f["path"] for f in found] == ["d/old.md"]


def test_a_superseded_record_cited_by_an_instruction_file_is_flagged(tmp_path):
    root = tree(
        tmp_path,
        {
            "d/old.md": record(kind="decision", status="ARCHIVED", extra="superseded-by: new\n"),
            "d/new.md": record(kind="decision", extra="supersedes: [old]\n"),
            "AGENTS.md": "Follow old for the layout, and new for naming.\n",
        },
    )
    found = [f for f in drift_records.check(root, None, TODAY) if f["rule"] == "dc-superseded-cited"]
    assert len(found) == 1 and "old" in found[0]["message"]


def test_only_live_plans_past_the_limit_are_stale(tmp_path):
    root = tree(
        tmp_path,
        {
            "p/stale.md": record(status="INPRG", revised="2026-09-01"),
            "p/fresh.md": record(status="INPRG", revised="2026-10-20"),
            "p/done.md": record(status="DONE", revised="2026-01-01"),
            "p/decision.md": record(status="INPRG", revised="2026-01-01", kind="decision"),
        },
    )
    found = drift_records.check(root, None, TODAY)
    assert [(f["rule"], f["path"], f["severity"]) for f in found] == [("dc-plan-stale", "p/stale.md", "info")]


def test_the_same_record_in_the_project_root_and_the_checkout_with_different_content_is_two_homes(tmp_path):
    root = tree(tmp_path, {"plans/x.md": record(), "plans/y.md": record()})
    config = tmp_path / "config"
    config.mkdir()
    (config / "x.md").write_text(record(revised="2026-10-01"), encoding="utf-8")
    (config / "y.md").write_text(record(), encoding="utf-8")
    found = drift_records.check(root, config, TODAY)
    assert [(f["rule"], f["path"], f["severity"]) for f in found] == [("dc-two-homes", "plans/x.md", "error")]


def finding(rule="cp-stale", project="verdict", path="AGENTS.md"):
    return drift.Finding(rule, "error", project, path, "m", "h")


def test_a_live_waiver_removes_the_finding_it_names_and_nothing_else():
    waivers = [{"rule": "cp-stale", "project": "verdict", "path": "AGENTS.*", "reason": "hand authored", "expires": "2026-12-01"}]
    kept = drift.apply_waivers([finding(), finding(project="eppal"), finding(rule="cp-missing")], waivers, TODAY)
    assert [(f.rule, f.project) for f in kept] == [("cp-stale", "eppal"), ("cp-missing", "verdict")]


def test_an_expired_waiver_covers_nothing_and_is_reported():
    waivers = [{"rule": "cp-stale", "project": "verdict", "path": "AGENTS.md", "reason": "r", "expires": "2026-10-01"}]
    kept = drift.apply_waivers([finding()], waivers, TODAY)
    assert [f.rule for f in kept] == ["cp-stale", "dc-waiver"]
    assert "expired on 2026-10-01" in kept[1].message


def test_a_waiver_without_a_reason_or_expiry_covers_nothing_and_is_reported():
    kept = drift.apply_waivers([finding()], [{"rule": "cp-stale", "expires": "2026-12-01"}, {"rule": "cp-stale", "reason": "r"}], TODAY)
    assert [f.rule for f in kept] == ["cp-stale", "dc-waiver", "dc-waiver"]


def test_waivers_are_read_from_the_file_beside_the_control_plane(tmp_path, monkeypatch):
    monkeypatch.setattr(drift.paths, "control_plane_file", lambda root=None: tmp_path / "roots" / "control-plane.md")
    assert drift.load_waivers(tmp_path) == []
    (tmp_path / "roots").mkdir()
    (tmp_path / "roots" / "drift-waivers.json").write_text(json.dumps({"waivers": [{"rule": "r"}]}))
    assert drift.load_waivers(tmp_path) == [{"rule": "r"}]


def test_staged_mode_reports_only_staged_files_and_blocks_on_an_error(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    git("init", "-q")
    (repo / "AGENTS.md").write_text("# root\n", encoding="utf-8")
    (repo / "plans").mkdir()
    (repo / "plans" / "BAD.pointer").write_text("missing.md\n", encoding="utf-8")
    (repo / "plans" / "OTHER.pointer").write_text("missing.md\n", encoding="utf-8")
    git("add", "plans/BAD.pointer")
    monkeypatch.setattr(drift.paths, "project_config_dir", lambda root=None: tmp_path / "roots")
    monkeypatch.setattr(drift.paths, "control_plane_file", lambda root=None: tmp_path / "roots" / "control-plane.md")
    found = drift.staged_findings(tmp_path, repo)
    assert [(f.rule, f.path) for f in found] == [("dc-pointer-dangling", "plans/BAD.pointer")]
    monkeypatch.chdir(repo)
    monkeypatch.setattr(drift.paths, "source_root", lambda explicit=None: tmp_path)
    assert drift.main(["--staged"]) == 1
