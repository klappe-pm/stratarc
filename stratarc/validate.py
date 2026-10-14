"""Check a source root for the defects the reference graph does not model, then fold the graph's error level reference checks in beside them.

The reference graph (`stratarc.source_graph`) carries the reference checks: dangling agent, skill and command names, hook registrations that resolve to no file, rule paths named in prose that do not exist, the digest's common rule selector, and skill directories with no entry. This module does not reimplement any of that; it reuses the graph's `check` output. What it adds are the checks that are not references at all: an agent's declared tool names against the runtime's own vocabulary, every tool an agent or command body tells it to use against that declaration, a leading `paths:` line left over from an unfenced rule, the binding budget of every rule, the shape of `components.json`, rule tier membership and the runtimes named in `stratarc.toml`.

Usage:
    stratarc validate [--root PATH]            print every finding, exit 0
    stratarc validate [--root PATH] --strict   exit 1 when any error level finding exists
    stratarc validate --checks generic         run only the built in checks (see CHECKS)

Every check is either generic, built in and readable from any source root, or private, supplied by the source root itself. A source root adds private checks in `scripts/private/validate_checks.py`, a module that declares `VALIDATE_CHECKS`, a list of callables that each take the source root and return a list of findings (see `finding`). `--checks generic` runs the built in set only, `--checks private` runs only the module's, and `--checks all`, the default, runs both. A module that cannot be loaded, or a check that raises, is reported as an error finding and never loses the rest of the gate.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

from stratarc.paths import SOURCE_VARIABLE, source_root

# Known agent tool names, spelled as the runtime spells them: the union of the
# tool names the runtimes document for an agent's `tools:` line.
KNOWN_TOOLS = (
    "AskUserQuestion",
    "Bash",
    "BashOutput",
    "Edit",
    "Glob",
    "Grep",
    "KillShell",
    "NotebookEdit",
    "Read",
    "Skill",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
)

# A tool an MCP server contributes is named mcp__<server>__<tool>, so it cannot be listed in advance.
MCP_TOOL = re.compile(r"^mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_-]+$")

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

# Where a source root keeps its private checks, relative to the root.
PRIVATE_CHECKS_PATH = "scripts/private/validate_checks.py"


def finding(severity: str, check: str, path: str, message: str) -> dict:
    return {"severity": severity, "check": check, "path": path, "message": message}


@contextlib.contextmanager
def bound_source(root: Path) -> Iterator[None]:
    """Name root as the source root for everything called inside the block, and restore the old value after.

    Modules that resolve the source root lazily (the component manifest's platform extension, the engine name) read `STRATARC_SOURCE`, so a validation of an explicit root has to bind it.
    """
    previous = os.environ.get(SOURCE_VARIABLE)
    os.environ[SOURCE_VARIABLE] = str(root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(SOURCE_VARIABLE, None)
        else:
            os.environ[SOURCE_VARIABLE] = previous


# ----- check 1: agent tool declarations -----


def check_agent_tools(root: Path) -> list[dict]:
    findings: list[dict] = []
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return findings
    for path in sorted(agents_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines or lines[0].strip() != "---":
            findings.append(finding("error", "agent-tools-declaration", f"{rel}:1", "file does not open with frontmatter"))
            continue
        tools_value = None
        tools_line = None
        for offset, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                break
            match = re.match(r"^tools:\s*(.*)$", line)
            if match:
                tools_value = match.group(1)
                tools_line = offset
                break
        if tools_value is None:
            findings.append(finding("error", "agent-tools-declaration", rel, "frontmatter has no tools: line"))
            continue
        names = [name.strip() for name in tools_value.split(",") if name.strip()]
        if not names:
            findings.append(finding("error", "agent-tools-declaration", f"{rel}:{tools_line}", "tools: line names no tools"))
        for name in names:
            if name not in KNOWN_TOOLS and not MCP_TOOL.match(name):
                findings.append(finding("error", "agent-tools-declaration", f"{rel}:{tools_line}", f"tools: line names {name!r}, which is not a known tool"))
    return findings


TOOL_NAMES = "|".join(KNOWN_TOOLS)
# A tool the body tells the agent to use: a backticked name, or a name after a verb of use. A bare
# capitalized word is not enough, since "Read the file" and "Edit the list" are ordinary prose.
TOOL_USE = re.compile(r"`(" + TOOL_NAMES + r")`|\b(?:[Uu]se|[Uu]sing|[Cc]all|[Ii]nvoke|[Vv]ia|[Ww]ith|[Rr]un)\s+(?:the\s+)?(" + TOOL_NAMES + r")\b(?![\w-])")
DECLARATION_KEYS = {"agents": "tools", "commands": "allowed-tools"}


def check_agent_tool_use(root: Path) -> list[dict]:
    """A tool the body of an agent or command tells it to use must be in its declaration.

    A runtime grants only the declared tools, so an instruction to use any other one fails when the
    agent reaches it. A command with no allowed-tools line inherits every tool and is not checked.
    Fenced blocks are examples and are skipped.
    """
    findings: list[dict] = []
    for directory, key in DECLARATION_KEYS.items():
        for path in sorted((root / directory).glob("*.md")):
            rel = path.relative_to(root).as_posix()
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines or lines[0].strip() != "---":
                continue
            declared: set[str] | None = None
            body_start = len(lines)
            for offset, line in enumerate(lines[1:], start=1):
                if line.strip() == "---":
                    body_start = offset + 1
                    break
                match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
                if match:
                    declared = {name.strip().split("(", 1)[0].strip() for name in match.group(1).split(",") if name.strip()}
            if declared is None:
                continue
            in_fence = False
            for number, line in enumerate(lines[body_start:], start=body_start + 1):
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    continue
                for match in TOOL_USE.finditer(line):
                    name = match.group(1) or match.group(2)
                    if name not in declared:
                        findings.append(finding("error", "agent-tool-undeclared", f"{rel}:{number}", f"the body uses {name}, which the {key}: line does not declare"))
    return findings


def check_agent_frontmatter(root: Path) -> list[dict]:
    """Reject plain description scalars that YAML treats as mappings."""
    findings: list[dict] = []
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return findings
    for path in sorted(agents_dir.glob("*.md")):
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines or lines[0].strip() != "---":
            continue
        for offset, line in enumerate(lines[1:], start=2):
            if line.strip() == "---":
                break
            match = re.match(r"^description:\s*(.*)$", line)
            if not match:
                continue
            value = match.group(1)
            if value and value[0] not in "'\"|>" and re.search(r":(?:\s|$)", value):
                findings.append(finding("error", "agent-frontmatter-yaml", f"{rel}:{offset}", "plain description contains a colon and must be quoted or a block scalar"))
            break
    return findings


# ----- check 2: no leading paths: line in a rule -----


def check_rule_paths_line(root: Path) -> list[dict]:
    findings: list[dict] = []
    rules_dir = root / "rules"
    if not rules_dir.is_dir():
        return findings
    for path in sorted(rules_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(root).as_posix()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() == "":
                continue
            if line.strip().startswith("paths:"):
                findings.append(finding("error", "rule-leading-paths-line", f"{rel}:1", "the first non-empty line is paths:, which belongs in a fenced example, not the rule body"))
            break
    return findings


# ----- check 2b: the 120-word binding budget -----

BINDING_BUDGET_WORDS = 120
BINDING_SECTION = re.compile(r"^##\s+binding\s*\n(.*?)(?=^##\s|\Z)", re.S | re.M)


def check_rule_binding_budget(root: Path) -> list[dict]:
    """A rule's binding section is capped at 120 words, and that cap is a checked limit."""
    findings: list[dict] = []
    rules_dir = root / "rules"
    if not rules_dir.is_dir():
        return findings
    for path in sorted(rules_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        rel = path.relative_to(root).as_posix()
        match = BINDING_SECTION.search(path.read_text(encoding="utf-8", errors="replace"))
        if not match:
            findings.append(finding("error", "rule-binding-budget", rel, "no ## binding section"))
            continue
        words = len(match.group(1).split())
        if words > BINDING_BUDGET_WORDS:
            findings.append(finding("error", "rule-binding-budget", rel, f"binding section is {words} words, over the budget of {BINDING_BUDGET_WORDS}"))
    return findings


# ----- check 2c: components.json -----


def check_components_manifest(root: Path) -> list[dict]:
    """Validate components.json with `stratarc.components`, so a malformed manifest or a literal secret fails the source gate."""
    path = root / "components.json"
    if not path.exists():
        return []
    from stratarc import components

    try:
        document = components.load(path)
    except components.ManifestError as error:
        return [finding("error", "components-manifest", "components.json", str(error))]
    return [finding("error", "components-manifest", "components.json", problem) for problem in components.validate(document)]


# ----- check 3: docs/ and .docs/ frontmatter and headings -----

# ----- check 4: rule tier membership -----


def check_rule_tiers(root: Path) -> list[dict]:
    """rules/tiers.json maps each tier name to the list of rule file names it carries.

    An absent manifest is reported as a skip rather than a failure.
    """
    findings: list[dict] = []
    tiers_path = root / "rules" / "tiers.json"
    if not tiers_path.is_file():
        findings.append(finding("info", "rule-tier-membership", "rules/tiers.json", "rules/tiers.json does not exist; this check is skipped"))
        return findings
    try:
        data = json.loads(tiers_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"rules/tiers.json is not valid JSON: {exc}"))
        return findings
    if not isinstance(data, dict):
        findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", "rules/tiers.json must be a JSON object mapping tier name to a list of rule file names"))
        return findings
    rules_dir = root / "rules"
    rule_files = {path.name for path in rules_dir.glob("*.md") if path.name != "README.md"}
    retired_names: set[str] = set()
    retired_path = rules_dir / "retired.json"
    if retired_path.is_file():
        try:
            retired_data = json.loads(retired_path.read_text(encoding="utf-8"))
            retired_names = {Path(name).name for name in retired_data.get("retired", [])}
        except (json.JSONDecodeError, AttributeError):
            retired_names = set()
    membership: dict[str, list[str]] = {}
    for tier, members in data.items():
        if not isinstance(members, list):
            findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"tier {tier!r} is not a list"))
            continue
        for name in members:
            if not isinstance(name, str):
                findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"tier {tier!r} contains non-string member {name!r}"))
                continue
            membership.setdefault(name, []).append(tier)
            if name not in rule_files:
                findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"tier {tier!r} names {name!r}, which is not a file under rules/"))
            if name in retired_names:
                findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"tier {tier!r} names {name!r}, which rules/retired.json lists as retired"))
    for name, tiers in membership.items():
        if len(tiers) > 1:
            findings.append(finding("error", "rule-tier-membership", "rules/tiers.json:1", f"{name!r} appears in more than one tier: {', '.join(sorted(tiers))}"))
    for name in sorted(rule_files - set(membership)):
        findings.append(finding("error", "rule-tier-membership", f"rules/{name}", "rule file does not appear in any tier of rules/tiers.json"))
    return findings


# ----- check 5: delegate the reference checks to the source graph -----


def check_reference_graph(root: Path) -> list[dict]:
    try:
        source_graph = importlib.import_module("stratarc.source_graph")
    except ModuleNotFoundError as error:
        if error.name != "stratarc.source_graph":
            raise
        return [finding("info", "reference-graph", ".", "stratarc.source_graph is not available; the reference checks were skipped")]
    graph = source_graph.build_graph(root)
    findings: list[dict] = []
    for item in graph.check(live=False):
        if item["severity"] != "error":
            continue
        findings.append(finding("error", item["check"], item["node"], f"{item['message']} ({item['evidence']})"))
    return findings


def check_runtime_config(root: Path) -> list[dict]:
    """Every [runtimes.<name>] table in stratarc.toml names a runtime an adapter provides."""
    from stratarc.adapters._common import RegistryError, runtime_registry
    from stratarc.config import ConfigError, load_config

    try:
        configured = load_config(root).runtimes
        registry = runtime_registry(root=root)
    except (ConfigError, RegistryError) as error:
        return [finding("error", "runtime-config", "stratarc.toml", str(error))]
    return [
        finding("error", "runtime-config", "stratarc.toml", f"[runtimes.{name}] names a runtime with no adapter; create adapters/{name}.py (`stratarc adapter new {name}` writes one)")
        for name in sorted(set(configured) - set(registry))
    ]


# ----- the source root's private checks -----


def private_checks(root: Path) -> tuple[list, list[dict]]:
    """The callables the source root's private module declares, and any finding that loading it produced.

    A missing module is the absent extension: no checks and no findings. A module that cannot be imported, or that does not declare `VALIDATE_CHECKS` as a list of callables, is an error finding naming it.
    """
    path = root / PRIVATE_CHECKS_PATH
    if not path.is_file():
        return [], []
    spec = importlib.util.spec_from_file_location("stratarc_private_validate_checks", path)
    if spec is None or spec.loader is None:
        return [], [finding("error", "private-checks", PRIVATE_CHECKS_PATH, "cannot be loaded")]
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # a private module may fail in any way, and the gate must still report
        return [], [finding("error", "private-checks", PRIVATE_CHECKS_PATH, f"cannot be imported: {type(error).__name__}: {error}")]
    checks = getattr(module, "VALIDATE_CHECKS", None)
    if not isinstance(checks, (list, tuple)) or not all(callable(check) for check in checks):
        return [], [finding("error", "private-checks", PRIVATE_CHECKS_PATH, "must declare VALIDATE_CHECKS, a list of callables that each take the source root")]
    return list(checks), []


def run_private(root: Path) -> list[dict]:
    """Run the source root's private checks; a check that raises is one error finding."""
    checks, findings = private_checks(root)
    for check in checks:
        name = getattr(check, "__name__", "check")
        try:
            produced = check(root)
        except Exception as error:
            findings.append(finding("error", "private-checks", PRIVATE_CHECKS_PATH, f"{name} raised {type(error).__name__}: {error}"))
            continue
        findings.extend(produced or [])
    return findings


# ----- assembly and output -----

# Every built in check, in the order it runs. Each reads only what any source
# root carries (agents, rules, hooks, docs, components.json and
# stratarc.toml) and skips a subject the root does not have.
CHECKS: tuple = (
    check_agent_tools,
    check_agent_tool_use,
    check_agent_frontmatter,
    check_rule_paths_line,
    check_rule_binding_budget,
    check_components_manifest,
    check_rule_tiers,
    check_reference_graph,
    check_runtime_config,
)
CHECK_SETS = ("generic", "private", "all")


def run_all(root: Path, checks: str = "all") -> list[dict]:
    if checks not in CHECK_SETS:
        raise ValueError(f"checks must be one of {', '.join(CHECK_SETS)}, not {checks!r}")
    findings: list[dict] = []
    if checks in ("all", "generic"):
        for check in CHECKS:
            findings += check(root)
    if checks in ("all", "private"):
        findings += run_private(root)
    findings.sort(key=lambda item: (SEVERITY_ORDER.get(item.get("severity"), 3), str(item.get("check")), str(item.get("path"))))
    return findings


def format_finding(item: dict) -> str:
    return f"{item['severity']:<7} {item['check']:<26} {item['path']}: {item['message']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stratarc validate",
        description=(
            "Check a source root for mistakes before you sync it: agent and command tool names,\n"
            "references that point at nothing, rule length, tier membership, the shape of\n"
            "components.json and the runtimes named in stratarc.toml. Run it after editing the\n"
            "source and before `stratarc sync`; CI can run it with --strict as a gate.\n"
            "\n"
            "Every finding is printed as severity, check, path and message. Without --strict\n"
            "the command reports and exits 0."
        ),
        epilog=(
            "examples:\n"
            "  stratarc validate                          report every finding, exit 0\n"
            "  stratarc validate --strict                 exit 1 when any error is found\n"
            "  stratarc validate --checks generic --root ~/agent-source\n"
            "                                             run only the built in checks on another root"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=None, help="source root (default: the resolved source root)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any error-level finding exists")
    parser.add_argument("--checks", choices=CHECK_SETS, default="all", help="which class of checks to run (default: all)")
    args = parser.parse_args(argv)

    root = source_root(args.root)
    with bound_source(root):
        findings = run_all(root, args.checks)
    for item in findings:
        print(format_finding(item))
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = sum(item["severity"] == "warning" for item in findings)
    infos = len(findings) - errors - warnings
    print(f"validate: {len(findings)} findings, {errors} errors, {warnings} warnings, {infos} info")
    return 1 if args.strict and errors else 0


if __name__ == "__main__":
    sys.exit(main())
