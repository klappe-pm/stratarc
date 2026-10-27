"""The optional workflow module's configuration: loading, merging and checking.

Two layers set it. The control plane defaults are a `[workflows]` table in the source root's `stratarc.toml`; a project overrides them in `<project config dir>/<project>/workflows.toml`. The module is off unless a layer sets `enabled = true`, and a project without the file gets the control plane defaults. The effective configuration is the built in defaults, then the control plane table, then the project file, table by table.

Gates only tighten. Each action has a standing floor, a layer may raise it (G0 < G1 < G2 < G3) and may not lower it, and a project may not lower a gate the control plane raised. Every check mode defaults to `report`.

- `stratarc workflows check` validates the control plane table and every project file, or just one project, and prints one problem per line as `<where>: <message>`.
- `stratarc workflows show` prints the effective configuration as JSON.

Exit codes: 0 clean, 1 a problem was found, 2 usage error.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
import tomllib

from stratarc import paths
from stratarc.config import validate_name

PROG = "stratarc workflows"
FILE = "workflows.toml"
LEVELS = ("G0", "G1", "G2", "G3")

# The standing policy: the lowest gate each action may have.
FLOORS = {
    "local-edit": "G0",
    "push-branch": "G1",
    "open-pr": "G1",
    "create-issue": "G2",
    "merge-default-branch": "G2",
    "deploy": "G2",
    "release-candidate": "G1",
    "publish": "G2",
    "delete": "G2",
    "external-repo-write": "G2",
    "bypass-guard": "G3",
    "settle-decision": "G3",
}

DEFAULTS = {
    "enabled": False,
    "paths": {"plan": "PLAN.md", "handoff": "local/handoff.md", "backlog": "local/backlog.md", "reports": "local/reports"},
    "claims": {"mode": "plan"},
    "gates": dict(FLOORS),
    "decision-records": {
        "enabled": False,
        "root": "docs/decision-records",
        "index": "docs/decision-records/index.json",
        "domains": ["architecture", "content", "design", "data", "integrations"],
        "target-words": 300,
        "check": "report",
    },
    "tickets": {"backend": "backlog"},
    "automation": {"session-start": False, "session-stop": False, "pre-commit": "report", "ci": False, "triage": "on-demand"},
}

# Per table: key -> a kind ("bool", "str", "words", "list") or a tuple of allowed words.
SCHEMA = {
    "paths": {"plan": "str", "handoff": "str", "backlog": "str", "reports": "str"},
    "claims": {"mode": ("plan", "files", "off")},
    "decision-records": {"enabled": "bool", "root": "str", "index": "str", "domains": "list", "target-words": "words", "check": ("report", "enforce", "off")},
    "tickets": {"backend": ("github", "backlog", "off")},
    "automation": {"session-start": "bool", "session-stop": "bool", "pre-commit": ("report", "enforce", "off"), "ci": "bool", "triage": ("on-demand", "weekly", "off")},
}


def _value_problem(key: str, value: object, kind: object) -> str:
    """The message for a value of the wrong kind, or an empty string when it fits."""
    if kind == "bool":
        return "" if isinstance(value, bool) else f"{key} must be true or false"
    if kind == "str":
        return "" if isinstance(value, str) and value else f"{key} must be a non-empty string"
    if kind == "words":
        return "" if isinstance(value, int) and not isinstance(value, bool) and value > 0 else f"{key} must be a positive integer"
    if kind == "list":
        return "" if isinstance(value, list) and all(isinstance(item, str) and item for item in value) else f"{key} must be a list of non-empty strings"
    return "" if value in kind else f"{key} must be one of {', '.join(kind)}"


def _table_problems(name: str, table: object) -> list[str]:
    if not isinstance(table, dict):
        return [f"[{name}] must be a table"]
    problems = []
    for key, value in table.items():
        if name == "paths" and key == "loadouts":
            problems.append("paths.loadouts is a retired name and is not accepted")
        elif key not in SCHEMA[name]:
            problems.append(f"unknown key {name}.{key}")
        else:
            message = _value_problem(f"{name}.{key}", value, SCHEMA[name][key])
            if message:
                problems.append(message)
    return problems


def _gate_problems(table: object, base: dict[str, str], base_name: str) -> list[str]:
    """Problems with a `[gates]` table; a gate may not sit below `base`, which is the standing floor or the control plane's value."""
    if not isinstance(table, dict):
        return ["[gates] must be a table"]
    problems = []
    for action, level in table.items():
        if action not in FLOORS:
            problems.append(f"unknown gate action {action}")
        elif level not in LEVELS:
            problems.append(f"gates.{action} must be one of {', '.join(LEVELS)}")
        elif LEVELS.index(level) < LEVELS.index(base[action]):
            problems.append(f"gates.{action} = {level} loosens {base[action]} from the {base_name}; gates may only tighten")
    return problems


def table_problems(table: dict, base_gates: dict[str, str], base_name: str) -> list[str]:
    """Every problem in one layer's table, with gates measured against `base_gates`."""
    problems = []
    for key, value in table.items():
        if key == "enabled":
            if not isinstance(value, bool):
                problems.append("enabled must be true or false")
        elif key == "gates":
            problems += _gate_problems(value, base_gates, base_name)
        elif key in SCHEMA:
            problems += _table_problems(key, value)
        else:
            problems.append(f"unknown key {key}")
    return problems


def merge(*layers: dict) -> dict:
    """The defaults with each layer laid over them in turn, table by table."""
    result = copy.deepcopy(DEFAULTS)
    for layer in layers:
        for key, value in layer.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key].update(copy.deepcopy(value))
            else:
                result[key] = copy.deepcopy(value)
    return result


def _read(path: pathlib.Path) -> tuple[dict, str]:
    """The parsed TOML at `path` and an error message; a missing file is an empty table."""
    if not path.is_file():
        return {}, ""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), ""
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        return {}, f"cannot read: {exc}"


def control_table(root: pathlib.Path) -> tuple[dict, list[str]]:
    """The `[workflows]` table of `stratarc.toml` and its problems."""
    data, error = _read(root / paths.CONFIG_NAME)
    if error:
        return {}, [f"{paths.CONFIG_NAME}: {error}"]
    table = data.get("workflows", {})
    if not isinstance(table, dict):
        return {}, [f"{paths.CONFIG_NAME}: [workflows] must be a table"]
    return table, [f"{paths.CONFIG_NAME}: {m}" for m in table_problems(table, FLOORS, "standing policy")]


def project_table(root: pathlib.Path, name: str, control: dict) -> tuple[dict, list[str]]:
    """A project's override table and its problems, with gates measured against the control plane."""
    where = f"{name}/{FILE}"
    data, error = _read(paths.project_config_dir(root) / name / FILE)
    if error:
        return {}, [f"{where}: {error}"]
    base = merge(control)["gates"]
    return data, [f"{where}: {m}" for m in table_problems(data, base, "control plane")]


def project_names(root: pathlib.Path) -> list[str]:
    base = paths.project_config_dir(root)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / FILE).is_file())


def check(root: pathlib.Path, project: str | None = None) -> list[str]:
    """Every problem in the control plane table and the project files (or just `project`)."""
    control, problems = control_table(root)
    if problems:
        control = {}
    for name in [project] if project else project_names(root):
        problems += project_table(root, name, control)[1]
    return problems


def effective(root: pathlib.Path, project: str | None = None) -> tuple[dict, list[str]]:
    """The merged configuration for `project` (the control plane defaults when None) and any problems met reading it."""
    control, problems = control_table(root)
    if problems:
        return merge(), problems
    if project is None:
        return merge(control), []
    override, problems = project_table(root, project, control)
    return merge(control, override), problems


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=PROG, description="Check and show the optional workflow module's configuration.")
    modes = ap.add_subparsers(dest="mode", required=True)
    checker = modes.add_parser("check", help="validate the control plane table and the project overrides")
    shower = modes.add_parser("show", help="print the effective configuration")
    for p in (checker, shower):
        p.add_argument("--project", metavar="NAME", help="only this project")
        p.add_argument("--root", metavar="PATH", help="the source root (default: $STRATARC_SOURCE, then the nearest stratarc.toml, then the current directory)")
    shower.add_argument("--format", choices=("json",), default="json", help="the output format (default: json)")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.project is not None and not validate_name(args.project):
        print(f"{PROG}: {args.project} is not a project name", file=sys.stderr)
        return 2
    root = paths.source_root(pathlib.Path(args.root) if args.root else None)
    if args.mode == "check":
        problems = check(root, args.project)
        for line in problems:
            print(line)
        scope = args.project or "control plane and projects"
        print(f"{PROG}: {len(problems)} problems in {scope}" if problems else f"{PROG}: ok, {scope}")
        return 1 if problems else 0
    config, problems = effective(root, args.project)
    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        return 1
    print(json.dumps(config, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
