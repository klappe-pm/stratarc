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
import fnmatch
import json
import pathlib
import subprocess
import sys

from stratarc import changelog, drift_levels, drift_records, paths

PROG = "stratarc drift"
SEVERITIES = ("error", "warn", "info")

# Rule ids from the drift design that this phase can report. cp-layout covers the two manifest against tree findings the design folds into other ids.
RULES = {
    "cp-missing": "a file the control plane delivers is absent from the checkout",
    "cp-stale": "a delivered file differs from what a sync would write now",
    "cp-unregistered": "a checkout under the projects root that no manifest row claims",
    "cp-layout": "a checkout under the wrong status folder, or more than one checkout for a project",
    "lv-undeclared-nested": "an instruction file below the checkout root that the project root does not declare",
    "lv-surface-split": "sibling surfaces in a nested folder that differ where one should be a copy of the other",
    "lv-fact-conflict": "a nested file and an ancestor give different commands for the same job",
    "lv-restated": "a nested file repeats a paragraph of an ancestor word for word",
    "lv-dead-reference": "a link or path in an instruction file that does not resolve",
    "dc-pointer-dangling": "a .pointer file whose target is missing, or that names no path or more than one",
    "dc-dated-reference": "an instruction file, hook or script cites a dated file name that a pointer already names",
    "dc-superseded-cited": "a record marked superseded is still cited as current by an instruction file",
    "dc-supersede-unpaired": "record A supersedes B but B does not name A, or the reverse",
    "dc-two-homes": "the same plan or decision sits in the project root and in the checkout with different content",
    "dc-plan-stale": "a plan with status INPRG or REVIEW that has not been revised for a set number of days",
    "dc-waiver": "a drift waiver that has expired or is missing its rule, reason or expiry date",
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


def declared(config_dir: pathlib.Path) -> tuple[set[str], tuple[str, ...]]:
    """The nested files a project root declares and its copy list, from its surfaces.json."""
    file = config_dir / "surfaces.json"
    data = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    return set(data.get("nested", [])), tuple(data.get("copy", drift_levels.SURFACES))


def from_levels(project: str, items: list[dict]) -> list[Finding]:
    return [Finding(i["rule"], i["severity"], project, i["path"], i["message"], i["hint"]) for i in items]


def load_waivers(root: pathlib.Path) -> list[dict]:
    """The waivers in drift-waivers.json beside the control plane file, or none."""
    file = paths.control_plane_file(root).parent / "drift-waivers.json"
    if not file.is_file():
        return []
    return list(json.loads(file.read_text(encoding="utf-8")).get("waivers", []))


def apply_waivers(found: list[Finding], waivers: list[dict], today: datetime.date) -> list[Finding]:
    """Drop the findings a live waiver covers. An expired or incomplete waiver covers nothing and is itself a finding.

    A waiver names a rule and may narrow it by project and by a path pattern; it must carry a reason and an expiry date.
    """
    live: list[dict] = []
    notes: list[Finding] = []
    for waiver in waivers:
        label = f"{waiver.get('rule', '?')} {waiver.get('project', '')} {waiver.get('path', '')}".strip()
        try:
            expires = datetime.date.fromisoformat(str(waiver["expires"]))
            if not waiver.get("rule") or not waiver.get("reason"):
                raise KeyError("reason")
        except (KeyError, ValueError):
            notes.append(Finding("dc-waiver", "warn", waiver.get("project", ""), waiver.get("path", ""), f"waiver {label} needs a rule, a reason and an expiry date", "complete the entry in drift-waivers.json"))
            continue
        if expires < today:
            notes.append(Finding("dc-waiver", "warn", waiver.get("project", ""), waiver.get("path", ""), f"waiver {label} expired on {expires.isoformat()}", "renew it with a new date and reason, or fix the finding"))
            continue
        live.append(waiver)

    def waived(f: Finding) -> bool:
        return any(w["rule"] == f.rule and w.get("project", f.project) == f.project and fnmatch.fnmatch(f.path, w.get("path", "*")) for w in live)

    return [f for f in found if not waived(f)] + notes


def from_graph(findings: list[dict]) -> list[Finding]:
    severity = {"error": "error", "warning": "warn"}
    found: list[Finding] = []
    for item in findings:
        rule = "in-retired-name" if item["check"] == "retired-reference" else "in-dangling"
        found.append(Finding(rule, severity.get(item["severity"], "info"), "", item["node"], f"{item['check']}: {item['message']}", f"evidence: {item['evidence']}"))
    return found


def collect(root: pathlib.Path, today: datetime.date | None = None) -> list[Finding]:
    """Run every check against the source root and return the findings. Writes nothing to a checkout."""
    from stratarc import projects, source_graph
    from stratarc.control_plane import ControlPlane
    from stratarc.staging import cleanup_all

    today = today or datetime.date.today()
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
    for name in cp.manifest:
        if cp.status(name) != "active":
            continue
        checkout, _why = projects.resolve(name, cp)
        if checkout is not None and checkout.is_dir():
            nested, copies = declared(paths.project_config_dir(root) / name)
            found += from_levels(name, drift_levels.check(checkout, nested, copies))
            found += from_levels(name, drift_records.check(checkout, paths.project_config_dir(root) / name, today))
    found += from_levels("", drift_records.check(root, None, today))
    found += from_graph(source_graph.build_graph(root).check(live=False))
    return dedupe(apply_waivers(found, load_waivers(root), today))


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


def checkout_of(path: pathlib.Path) -> pathlib.Path | None:
    """The nearest folder at or above a path that is a git repository."""
    path = path.resolve()
    for folder in [path, *path.parents]:
        if (folder / ".git").exists():
            return folder
    return None


def fingerprint(checkout: pathlib.Path, config_dir: pathlib.Path) -> str:
    """Changes whenever an instruction file or the project's surfaces.json does."""
    parts = [f"{p.relative_to(checkout)}:{p.stat().st_mtime_ns}:{p.stat().st_size}" for p in drift_levels.instruction_files(checkout)]
    surfaces = config_dir / "surfaces.json"
    if surfaces.is_file():
        parts.append(f"surfaces:{surfaces.stat().st_mtime_ns}")
    return "|".join(parts)


def session_line(root: pathlib.Path, start: pathlib.Path) -> str:
    """One line for a session start, empty when the checkout is clean. Cached by file mtime under the state home."""
    checkout = checkout_of(start)
    if checkout is None:
        return ""
    config_dir = paths.project_config_dir(root) / checkout.name
    key = fingerprint(checkout, config_dir)
    cache_file = report_dir() / "session-cache.json"
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    entry = cache.get(str(checkout))
    if entry and entry.get("key") == key:
        line = entry["line"]
    else:
        nested, copies = declared(config_dir)
        items = drift_levels.check(checkout, nested, copies)
        errors = sum(i["severity"] == "error" for i in items)
        line = f"{PROG}: {len(items)} drift findings ({errors} at error level) in {checkout.name}, run stratarc drift explain <path>" if items else ""
        cache[str(checkout)] = {"key": key, "line": line}
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass
    return line


def staged_paths(checkout: pathlib.Path) -> set[str]:
    result = subprocess.run(["git", "-C", str(checkout), "diff", "--cached", "--name-only"], capture_output=True, text=True, timeout=30)
    return {line for line in result.stdout.splitlines() if line}


def staged_findings(root: pathlib.Path, start: pathlib.Path) -> list[Finding]:
    """Folder level and record findings for the staged files of the checkout holding `start`. For a pre-commit hook."""
    checkout = checkout_of(start)
    if checkout is None:
        return []
    config_dir = paths.project_config_dir(root) / checkout.name
    nested, copies = declared(config_dir)
    staged = staged_paths(checkout)
    items = drift_levels.check(checkout, nested, copies) + drift_records.check(checkout, config_dir)
    return dedupe(apply_waivers(from_levels(checkout.name, [i for i in items if i["path"] in staged]), load_waivers(root), datetime.date.today()))


def repo_findings(start: pathlib.Path) -> list[Finding]:
    """The folder level and record rules over the whole checkout holding `start`, with no source root. For a project's own CI."""
    checkout = checkout_of(start)
    if checkout is None:
        return []
    items = drift_levels.check(checkout, None) + drift_records.check(checkout)
    return dedupe(from_levels(checkout.name, items))


def source_findings(root: pathlib.Path) -> list[Finding]:
    """The reference graph and the record rules over the source root alone, with no checkouts. For the control plane's CI."""
    from stratarc import source_graph

    found = from_levels("", drift_records.check(root)) + from_graph(source_graph.build_graph(root).check(live=False))
    return dedupe(apply_waivers(found, load_waivers(root), datetime.date.today()))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROG,
        description="Report where a checkout's agent files differ from what the control plane delivers, and where the source root's references break. Reads only; it never changes a checkout or the source root.",
        epilog="examples:\n  stratarc drift\n  stratarc drift --format json\n  stratarc drift --report\n  stratarc drift --here\n  stratarc drift explain docs/guide/AGENTS.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    ap.add_argument("--report", action="store_true", help="also write a Markdown report and a dated copy under the state home")
    ap.add_argument("--here", action="store_true", help="session start mode: check only the checkout holding the current folder, print one line when it has findings, always exit 0")
    ap.add_argument("--staged", action="store_true", help="pre-commit mode: check only the staged files of the checkout holding the current folder, exit 1 on an error level finding")
    ap.add_argument("--repo", action="store_true", help="project CI mode: check the whole checkout holding the current folder with no source root, exit 1 on an error level finding")
    ap.add_argument("--source", action="store_true", help="control plane CI mode: check the source root alone with no checkouts, exit 1 on an error level finding")
    ap.add_argument("--root", metavar="PATH", help="the source root (default: $STRATARC_SOURCE, then the nearest stratarc.toml, then the current directory)")
    modes = ap.add_subparsers(dest="mode")
    explain = modes.add_parser("explain", help="list every instruction file that applies to a path, with conflicts marked")
    explain.add_argument("path", help="a file or folder inside a checkout")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repo:
        found = repo_findings(pathlib.Path.cwd())
        for f in found:
            print(f.line())
        return 1 if any(f.severity == "error" for f in found) else 0
    root = paths.source_root(pathlib.Path(args.root) if args.root else None)
    if args.source:
        found = source_findings(root)
        for f in found:
            print(f.line())
        return 1 if any(f.severity == "error" for f in found) else 0
    if args.mode == "explain":
        target = pathlib.Path(args.path).expanduser().resolve()
        checkout = checkout_of(target)
        if checkout is None:
            print(f"{PROG}: {args.path} is not inside a git checkout", file=sys.stderr)
            return 2
        for line in drift_levels.explain(checkout, target):
            print(line)
        return 0
    if args.staged:
        found = staged_findings(root, pathlib.Path.cwd())
        for f in found:
            print(f.line())
        return 1 if any(f.severity == "error" for f in found) else 0
    if args.here:
        line = session_line(root, pathlib.Path.cwd())
        if line:
            print(line)
        return 0
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
