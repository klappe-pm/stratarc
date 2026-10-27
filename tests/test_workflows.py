"""stratarc workflows: the layers, the merge, each validation error, the tighten only rule and the exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stratarc import cli, config, workflows


def make_root(tmp_path: Path, control: str = "", projects: dict[str, str] | None = None) -> Path:
    root = tmp_path / "source"
    root.mkdir(parents=True)
    (root / "stratarc.toml").write_text('[layout]\nproject_config_dir = "projects/roots"\n' + control)
    for name, text in (projects or {}).items():
        (root / "projects" / "roots" / name).mkdir(parents=True)
        (root / "projects" / "roots" / name / "workflows.toml").write_text(text)
    return root


def run(root: Path, *argv: str) -> list[str]:
    return workflows.check(root, *argv)


def test_defaults_are_off_and_every_mode_is_report():
    base = workflows.merge()
    assert base["enabled"] is False
    assert base["decision-records"]["check"] == "report"
    assert base["automation"]["pre-commit"] == "report"
    assert base["claims"]["mode"] == "plan"
    assert base["tickets"]["backend"] == "backlog"
    assert base["decision-records"]["target-words"] == 300
    assert base["gates"] == workflows.FLOORS


def test_merge_order_is_defaults_then_control_plane_then_project(tmp_path):
    root = make_root(
        tmp_path,
        '[workflows]\nenabled = true\n[workflows.paths]\nplan = "docs/plan.md"\nhandoff = "h.md"\n[workflows.gates]\ndeploy = "G3"\n',
        {"alpha": 'enabled = false\n[paths]\nhandoff = "mine.md"\n[gates]\npush-branch = "G2"\n'},
    )
    control, _ = workflows.effective(root)
    assert control["enabled"] is True and control["paths"]["plan"] == "docs/plan.md"
    mine, problems = workflows.effective(root, "alpha")
    assert problems == []
    assert mine["enabled"] is False
    assert mine["paths"] == {"plan": "docs/plan.md", "handoff": "mine.md", "backlog": "local/backlog.md", "reports": "local/reports"}
    assert mine["gates"]["deploy"] == "G3" and mine["gates"]["push-branch"] == "G2" and mine["gates"]["open-pr"] == "G1"


def test_a_project_without_a_file_gets_the_control_plane_defaults(tmp_path):
    root = make_root(tmp_path, "[workflows]\nenabled = true\n")
    config_for_new, problems = workflows.effective(root, "nobody")
    assert problems == [] and config_for_new["enabled"] is True


def test_a_missing_table_leaves_the_module_off(tmp_path):
    assert run(make_root(tmp_path)) == []
    assert workflows.effective(make_root(tmp_path / "again"))[0]["enabled"] is False


def test_load_config_allows_and_ignores_the_workflows_table(tmp_path):
    root = make_root(tmp_path, "[workflows]\nenabled = true\n[workflows.gates]\ndeploy = \"G3\"\n")
    assert config.load_config(root).layout.project_config_dir == "projects/roots"


@pytest.mark.parametrize(
    "text, expect",
    [
        ("enabled = 1\n", "enabled must be true or false"),
        ("mystery = 1\n", "unknown key mystery"),
        ("[mystery]\nx = 1\n", "unknown key mystery"),
        ("[paths]\nroot = 'x'\n", "unknown key paths.root"),
        ("[paths]\nplan = ''\n", "paths.plan must be a non-empty string"),
        ("[paths]\nloadouts = 'x'\n", "paths.loadouts is a retired name"),
        ("[claims]\nmode = 'all'\n", "claims.mode must be one of plan, files, off"),
        ("[gates]\ndeploy = 'G9'\n", "gates.deploy must be one of G0, G1, G2, G3"),
        ("[gates]\nship-it = 'G2'\n", "unknown gate action ship-it"),
        ("[decision-records]\ntarget-words = 0\n", "decision-records.target-words must be a positive integer"),
        ("[decision-records]\ntarget-words = true\n", "decision-records.target-words must be a positive integer"),
        ("[decision-records]\ndomains = [1]\n", "decision-records.domains must be a list of non-empty strings"),
        ("[decision-records]\ncheck = 'strict'\n", "decision-records.check must be one of report, enforce, off"),
        ("[decision-records]\nenabled = 'yes'\n", "decision-records.enabled must be true or false"),
        ("[tickets]\nbackend = 'jira'\n", "tickets.backend must be one of github, backlog, off"),
        ("[automation]\nsession-start = 'on'\n", "automation.session-start must be true or false"),
        ("[automation]\npre-commit = 'block'\n", "automation.pre-commit must be one of report, enforce, off"),
        ("[automation]\ntriage = 'daily'\n", "automation.triage must be one of on-demand, weekly, off"),
        ("gates = 3\n", "[gates] must be a table"),
        ("paths = 3\n", "[paths] must be a table"),
    ],
)
def test_each_validation_error_names_the_key_in_both_layers(tmp_path, text, expect):
    in_control = run(make_root(tmp_path / "a", "[workflows]\n" + text.replace("[", "[workflows.", 1) if text.startswith("[") else "[workflows]\n" + text))
    assert any(line.startswith("stratarc.toml: ") and expect in line for line in in_control), in_control
    in_project = run(make_root(tmp_path / "b", projects={"alpha": text}))
    assert any(line.startswith("alpha/workflows.toml: ") and expect in line for line in in_project), in_project


def test_a_malformed_file_is_a_problem(tmp_path):
    problems = run(make_root(tmp_path, projects={"alpha": "enabled = \n"}))
    assert len(problems) == 1 and problems[0].startswith("alpha/workflows.toml: cannot read")


def test_a_gate_may_not_sit_below_the_standing_floor(tmp_path):
    problems = run(make_root(tmp_path, "[workflows]\n[workflows.gates]\ndeploy = 'G1'\ndelete = 'G2'\nlocal-edit = 'G1'\n"))
    assert len(problems) == 1 and "gates.deploy = G1 loosens G2" in problems[0] and "standing policy" in problems[0]
    problems = run(make_root(tmp_path / "p", projects={"alpha": "[gates]\nbypass-guard = 'G2'\n"}))
    assert len(problems) == 1 and "gates.bypass-guard = G2 loosens G3" in problems[0]


def test_a_project_may_not_loosen_a_gate_the_control_plane_tightened(tmp_path):
    root = make_root(
        tmp_path,
        "[workflows]\n[workflows.gates]\npush-branch = 'G3'\n",
        {"alpha": "[gates]\npush-branch = 'G2'\nopen-pr = 'G2'\n", "beta": "[gates]\npush-branch = 'G3'\n"},
    )
    problems = run(root)
    assert problems == ["alpha/workflows.toml: gates.push-branch = G2 loosens G3 from the control plane; gates may only tighten"]


def test_equal_to_the_floor_is_allowed(tmp_path):
    assert run(make_root(tmp_path, projects={"alpha": "[gates]\ndeploy = 'G2'\n"})) == []


def test_project_selection_checks_only_that_project(tmp_path):
    root = make_root(tmp_path, projects={"alpha": "mystery = 1\n", "beta": "mystery = 2\n"})
    assert len(run(root)) == 2
    assert [line.split(":")[0] for line in run(root, "beta")] == ["beta/workflows.toml"]
    assert run(root, "gamma") == []


def test_an_invalid_control_plane_does_not_hide_project_problems(tmp_path):
    root = make_root(tmp_path, "[workflows]\nmystery = 1\n", {"alpha": "enabled = 3\n"})
    assert [line.split(":")[0] for line in run(root)] == ["stratarc.toml", "alpha/workflows.toml"]


def test_check_exit_codes_and_output(tmp_path, capsys):
    clean = make_root(tmp_path / "c", projects={"alpha": "enabled = true\n"})
    assert workflows.main(["check", "--root", str(clean)]) == 0
    assert capsys.readouterr().out == "stratarc workflows: ok, control plane and projects\n"
    bad = make_root(tmp_path / "d", projects={"alpha": "[paths]\nloadouts = 'x'\n"})
    assert workflows.main(["check", "--root", str(bad)]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "alpha/workflows.toml: paths.loadouts is a retired name and is not accepted"
    assert out[1] == "stratarc workflows: 1 problems in control plane and projects"
    assert workflows.main(["check", "--root", str(bad), "--project", "other"]) == 0


def test_usage_errors_exit_2(tmp_path, capsys):
    root = make_root(tmp_path)
    with pytest.raises(SystemExit) as raised:
        workflows.main([])
    assert raised.value.code == 2
    assert workflows.main(["check", "--root", str(root), "--project", "Bad Name"]) == 2
    with pytest.raises(SystemExit) as raised:
        workflows.main(["show", "--format", "yaml"])
    assert raised.value.code == 2


def test_show_prints_the_effective_config_as_json(tmp_path, capsys):
    root = make_root(tmp_path, "[workflows]\nenabled = true\n", {"alpha": "[tickets]\nbackend = 'github'\n"})
    assert workflows.main(["show", "--root", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["tickets"]["backend"] == "backlog"
    assert workflows.main(["show", "--root", str(root), "--project", "alpha", "--format", "json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["enabled"] is True and shown["tickets"]["backend"] == "github"


def test_show_fails_on_a_problem_without_printing_a_config(tmp_path, capsys):
    root = make_root(tmp_path, projects={"alpha": "mystery = 1\n"})
    assert workflows.main(["show", "--root", str(root), "--project", "alpha"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "unknown key mystery" in captured.err


def test_the_command_line_forwards_workflows_and_a_problem_is_a_failure_not_drift(tmp_path):
    root = make_root(tmp_path, projects={"alpha": "mystery = 1\n"})
    assert "workflows" in cli.PASSTHROUGH
    assert cli._reports_drift("workflows", ["check"]) is False
    assert cli.main(["--root", str(root), "workflows", "check"]) == 1
    assert cli.main(["--root", str(root), "workflows", "check", "--project", "none"]) == 0


def test_the_shipped_project_template_is_valid(tmp_path):
    template = Path(workflows.__file__).parent / "data/templates/source-root/templates/project/roots/workflows.toml"
    root = make_root(tmp_path, projects={"alpha": template.read_text()})
    assert run(root) == []
    assert workflows.effective(root, "alpha")[0]["gates"]["push-branch"] == "G2"


def test_the_shipped_stratarc_toml_enables_nothing(tmp_path):
    template = Path(workflows.__file__).parent / "data/templates/source-root"
    assert workflows.effective(template)[0]["enabled"] is False
    assert run(template) == []
