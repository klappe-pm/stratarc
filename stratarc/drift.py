"""Drift between the control plane and what the checkouts hold, in one finding format.

`stratarc drift` runs the checks the engine already has and reports them together:

- the project delivery check (`projects --check`): a delivered file a sync would change;
- the manifest against the tree (`projects --verify`): checkouts under the wrong status folder, two checkouts, a checkout no row claims;
- surface drift: `AGENTS.md`, `CLAUDE.md`, `CODEX.md` and `GEMINI.md` missing from a checkout or differing from the master;
- skill drift: a project skill file missing, changed or extra;
- the reference graph (`source-graph check`): dangling references inside the source root.

Every finding carries a stable rule id so a waiver can name it. The command never changes a checkout or the source root; it only reads, and with `--report` it writes one Markdown file under the state home.

Exit codes: 0 clean, 1 drift at error level (the command line maps it to 6, as for `check`), 2 usage error.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import pathlib
import sys

from stratarc import changelog, paths

PROG = "stratarc drift"
SEVERITIES = ("error", "warn", "info")

# Rule ids from the drift design that this phase can report. cp-layout covers the two manifest against tree findings the design folds into other ids.
RULES = {
    "cp-missing": "a file the control plane delivers is absent from the checkout",
    "cp-stale": "a delivered file differs from what a sync would write now",
    "cp-unregistered": "a checkout under the projects root that no manifest row claims",
    "cp-layout": "a checkout under the wrong status folder, or more than one checkout for a project",
    "in-dangling": "a reference inside the source root that does not resolve",
    "in-retired-name": "text naming a retired rule",
}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    project: str
    path: str
    message: str
    hint: str

    def line(self) -> str:
        where = f"{self.project}: " if self.project else ""
        return f"{self.severity:<5} {self.rule:<16} {where}{self.message}"

    def record(self) -> dict:
        return dataclasses.asdict(self)


def _split(line: str) -> tuple[str, str]:
    """`name: text` into (name, text); a line with no project prefix is all text."""
    name, sep, text = line.partition(": ")
    return (name, text) if sep and " " not in name else ("", line)


def from_manifest(lines: list[str]) -> list[Finding]:
    found: list[Finding] = []
    for line in lines:
        project, text = _split(line)
        if "is not in the manifest" in text:
            rule, severity, hint = "cp-unregistered", "warn", "add the project to the control plane or move the checkout out of the projects root"
        elif "no checkout found" in text:
            rule, severity, hint = "cp-missing", "error", "clone the project or change its status in the control plane"
        else:
            rule, severity, hint = "cp-layout", "warn", "move the checkout to the folder its status names, or change the status"
        found.append(Finding(rule, severity, project, "", text, hint))
    return found


def from_surfaces(lines: list[str]) -> list[Finding]:
    found: list[Finding] = []
    for line in lines:
        project, text = _split(line)
        surface = text.split(" ", 1)[0]
        if text.endswith("is missing"):
            found.append(Finding("cp-missing", "error", project, surface, text, "run stratarc sync to deliver it"))
        else:
            found.append(Finding("cp-stale", "error", project, surface, text, "edit the project's AGENTS.md in the control plane and sync, or adopt the checkout edit into source"))
    return found


def from_skills(lines: list[str]) -> list[Finding]:
    found: list[Finding] = []
    for line in lines:
        project, text = _split(line)
        found.append(Finding("cp-stale", "error", project, "", f"skill {text}", "edit the skill in the control plane and sync"))
    return found


def from_delivery(project: str, actions: list[str]) -> list[Finding]:
    """What a sync would do for one project; a lone skip line is a fact, not drift."""
    if len(actions) == 1 and actions[0].startswith("skip"):
        return []
    return [Finding("cp-stale", "error", project, "", action, "run stratarc sync") for action in actions]


def from_graph(findings: list[dict]) -> list[Finding]:
    severity = {"error": "error", "warning": "warn"}
    found: list[Finding] = []
    for item in findings:
        rule = "in-retired-name" if item["check"] == "retired-reference" else "in-dangling"
        found.append(Finding(rule, severity.get(item["severity"], "info"), "", item["node"], f"{item['check']}: {item['message']}", f"evidence: {item['evidence']}"))
    return found


def collect(root: pathlib.Path) -> list[Finding]:
    """Run every check against the source root and return the findings. Writes nothing to a checkout."""
    from stratarc import projects, source_graph
    from stratarc.control_plane import ControlPlane
    from stratarc.staging import cleanup_all

    projects.configure_root(root)
    projects.load_renderer_extensions()
    cp = ControlPlane.load(paths.control_plane_file(root))
    found: list[Finding] = []
    try:
        found += from_manifest(projects.verify(cp))
        divergent, _shims = projects.surface_drift(cp)
        found += from_surfaces(divergent)
        skills, _notes = projects.skill_drift(cp)
        found += from_skills(skills)
        names = cp.projects() if cp.rows else sorted(p.name for p in projects.PROJECTS_SRC.iterdir() if p.is_dir())
        for name in names:
            try:
                found += from_delivery(name, projects.sync_project(name, True, cp if cp.rows else None))
            except projects.ProjectRefused as error:
                found.append(Finding("cp-layout", "error", name, "", str(error), "resolve the refusal, then rerun"))
    finally:
        cleanup_all()
    found += from_graph(source_graph.build_graph(root).check(live=False))
    return dedupe(found)


def dedupe(found: list[Finding]) -> list[Finding]:
    """The same fact can surface from two checks, such as a missing surface and a delivery action; keep the first."""
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[Finding] = []
    for finding in found:
        key = (finding.rule, finding.project, finding.path, finding.message)
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return sorted(unique, key=lambda f: (SEVERITIES.index(f.severity), f.rule, f.project, f.path))


def render_markdown(found: list[Finding], when: datetime.datetime) -> str:
    errors = sum(f.severity == "error" for f in found)
    lines = [f"# drift report", "", f"Run at {when.isoformat(timespec='seconds')}: {len(found)} findings, {errors} at error level.", ""]
    if not found:
        lines.append("No drift found.")
    else:
        lines += ["| severity | rule | project | path | finding | fix |", "|---|---|---|---|---|---|"]
        for f in found:
            cells = [f.severity, f"`{f.rule}`", f.project or "-", f"`{f.path}`" if f.path else "-", f.message.replace("|", "/"), f.hint.replace("|", "/")]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def report_dir() -> pathlib.Path:
    return changelog.state_home() / "state" / "drift"


def write_report(found: list[Finding], when: datetime.datetime) -> pathlib.Path:
    directory = report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    body = render_markdown(found, when)
    (directory / f"{when.strftime('%Y%m%d-%H%M%S')}.md").write_text(body, encoding="utf-8")
    latest = directory / "latest.md"
    latest.write_text(body, encoding="utf-8")
    return latest


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROG,
        description="Report where a checkout's agent files differ from what the control plane delivers, and where the source root's references break. Reads only; it never changes a checkout or the source root.",
        epilog="examples:\n  stratarc drift\n  stratarc drift --format json\n  stratarc drift --report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    ap.add_argument("--report", action="store_true", help="also write a Markdown report and a dated copy under the state home")
    ap.add_argument("--root", metavar="PATH", help="the source root (default: $STRATARC_SOURCE, then the nearest stratarc.toml, then the current directory)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = paths.source_root(pathlib.Path(args.root) if args.root else None)
    when = datetime.datetime.now().astimezone()
    found = collect(root)
    if args.format == "json":
        print(json.dumps({"findings": [f.record() for f in found]}, indent=1))
    else:
        for f in found:
            print(f.line())
        errors = sum(f.severity == "error" for f in found)
        print(f"{PROG}: {len(found)} findings, {errors} at error level")
    if args.report:
        print(f"{PROG}: report written to {write_report(found, when)}", file=sys.stderr)
    return 1 if any(f.severity == "error" for f in found) else 0


if __name__ == "__main__":
    sys.exit(main())
