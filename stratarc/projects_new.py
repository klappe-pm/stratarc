"""stratarc projects --new and --registry-check: load a project and keep the registries current.

`--new NAME` automates the manual steps of templates/project/README.md for one project, idempotently:

  1. copy the source root's templates/project/roots/ to <project config dir>/NAME/ and fill in `<project>`;
  2. add the project's row and column to the control plane (or let the reconciler do it when the control plane is managed);
  3. add the slug to remotes.json (--remote) and to public-targets.json (--public);
  4. when the checkout exists, merge the .gitignore visibility block and add the local/ scaffolding;
  5. check the result with the reconciler, the registries and the drift checks for that one project.

Nothing is delivered into a checkout other than that scaffolding; delivery stays with `stratarc sync`. With --check or --dry-run it prints what would change and writes nothing.

`--registry-check` is read only: every project in the control plane has a root folder and a remotes.json entry, a public project has no row, and every root folder is in the control plane.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import re
import sys

from stratarc import paths
from stratarc.control_plane import ControlPlane, _cells, _option_id

PROG = "stratarc projects"
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REMOTE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
STATUS_FOLDERS = ("active", "new", "inactive", "archived", "external")
REMOTES = "remotes.json"
PUBLIC_TARGETS = "public-targets.json"
PLACEHOLDER = "<project>"
# Template files, relative to <source root>/templates/project/.
ROOTS_TEMPLATE = "roots"
CHECKOUT_TEMPLATE = "checkout"
WORKFLOWS_TEMPLATE = "workflows.toml"


class NewRefused(Exception):
    """The request cannot be carried out; the message says why and nothing was written."""


# ---- names and registries ---------------------------------------------------


def valid_name(name: str) -> bool:
    return bool(NAME_PATTERN.match(name))


def _load_json(path: pathlib.Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise NewRefused(f"{path} cannot be read ({type(error).__name__}: {error})") from None


def read_remotes(config_dir: pathlib.Path) -> dict[str, str]:
    path = config_dir / REMOTES
    if not path.is_file():
        return {}
    document = _load_json(path)
    if not isinstance(document, dict):
        raise NewRefused(f"{path} must hold an object of project name to owner/repo")
    return {k: v for k, v in document.items() if not k.startswith("$") and isinstance(v, str)}


def read_public(config_dir: pathlib.Path) -> list[str]:
    path = config_dir / PUBLIC_TARGETS
    if not path.is_file():
        return []
    document = _load_json(path)
    targets = document.get("targets") if isinstance(document, dict) else document
    if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
        raise NewRefused(f"{path} must hold a list of names, bare or under a targets key")
    return targets


def _dump(document: object) -> str:
    """JSON text in the shape of the file it replaces: two space indent, a final newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _sorted_like(keys: list[str]) -> bool:
    return keys == sorted(keys, key=str.casefold)


def add_remote(config_dir: pathlib.Path, name: str, slug: str, apply: bool) -> list[str]:
    path = config_dir / REMOTES
    document = _load_json(path) if path.is_file() else {}
    if not isinstance(document, dict):
        raise NewRefused(f"{path} must hold an object of project name to owner/repo")
    if document.get(name) == slug:
        return []
    if name in document:
        raise NewRefused(f"{REMOTES} already maps {name} to {document[name]}; not changing it to {slug}")
    keys = [k for k in document if not k.startswith("$")]
    document[name] = slug
    if _sorted_like(keys):
        head = {k: v for k, v in document.items() if k.startswith("$")}
        body = {k: v for k, v in document.items() if not k.startswith("$")}
        document = {**head, **{k: body[k] for k in sorted(body, key=str.casefold)}}
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(document), encoding="utf-8")
    return [f"{REMOTES}: add {name} = {slug}"]


def add_public(config_dir: pathlib.Path, name: str, apply: bool) -> list[str]:
    path = config_dir / PUBLIC_TARGETS
    document = _load_json(path) if path.is_file() else {"targets": []}
    targets = document.get("targets") if isinstance(document, dict) else document
    if not isinstance(targets, list):
        raise NewRefused(f"{path} must hold a list of names, bare or under a targets key")
    if name in targets:
        return []
    targets = sorted([*targets, name], key=str.casefold) if _sorted_like(targets) else [*targets, name]
    if isinstance(document, dict):
        document["targets"] = targets
    else:
        document = targets
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(document), encoding="utf-8")
    return [f"{PUBLIC_TARGETS}: add {name}"]


# ---- the project root --------------------------------------------------------


def _template_dir(root: pathlib.Path, *parts: str) -> pathlib.Path:
    return root / "templates" / "project" / pathlib.Path(*parts)


def _template_files(base: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in base.rglob("*") if p.is_file() and p.name != ".DS_Store")


def copy_root(root: pathlib.Path, name: str, apply: bool, workflows: bool) -> list[str]:
    """Copy the source root's own project template into the new project's folder, never replacing a file."""
    template = _template_dir(root, ROOTS_TEMPLATE)
    if not template.is_dir():
        raise NewRefused(f"the source root has no {template.relative_to(root).as_posix()}/; add the project template there first")
    target = paths.project_config_dir(root) / name
    pairs = [(f, target / f.relative_to(template)) for f in _template_files(template)]
    if workflows:
        extra = _template_dir(root, WORKFLOWS_TEMPLATE)
        if extra.is_file():
            pairs.append((extra, target / WORKFLOWS_TEMPLATE))
    actions: list[str] = []
    for source, dest in pairs:
        if dest.exists():
            continue
        body = source.read_bytes()
        if source.name == "AGENTS.md":
            body = body.decode("utf-8").replace(PLACEHOLDER, name).encode("utf-8")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
        actions.append(f"root: add {dest.relative_to(root).as_posix()}")
    return actions


# ---- the control plane -------------------------------------------------------


def _split_line(raw: str) -> tuple[str, str]:
    body = raw.rstrip("\r\n")
    return body, raw[len(body) :]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(c) <= {"-", ":", " "} for c in cells)


def _manifest_row(header: list[str], name: str, status: str, origin: str, link: str) -> str:
    values = {"status": status, "tier": "normal", "root": link, "origin": origin or "-", "template": "base"}
    return "| " + " | ".join([name, *(values.get(h.lower(), "-") for h in header[1:])]) + " |"


def _column_cell(option: str, cp: ControlPlane) -> bool:
    """The default for a new project's cell, the reconciler's own: the project's instruction file is on, a rule follows its tier, a hook follows the projects, the rest is off."""
    from stratarc.reconcile import project_default

    if option.startswith("project:"):
        return option == "project:AGENTS.md"
    return project_default(option, cp, cp.rule_tier(option) or None)


def add_to_control_plane(text: str, cp: ControlPlane, name: str, status: str, origin: str, link: str) -> str:
    """Return *text* with the project's row and (when active) its column added, every other byte unchanged."""
    lines = text.splitlines(keepends=True)
    out = list(lines)
    # Edits to a line never move another; the one new row is inserted last, by its recorded index.
    pending_row: tuple[int, str] | None = None
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        end = index
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        header = _cells(lines[index].rstrip("\r\n"))
        head = header[0].lower() if header else ""
        if head == "project":
            rows = [
                (n, _option_id(_cells(lines[n].rstrip("\r\n"))[0]))
                for n in range(index + 1, end)
                if not _is_separator(_cells(lines[n].rstrip("\r\n")))
            ]
            if not any(key == name for _n, key in rows):
                ending = _split_line(lines[index])[1] or "\n"
                new = _manifest_row(header, name, status, origin, link) + ending
                after = next((n for n, key in rows if key.casefold() > name.casefold()), None)
                if after is None and not lines[end - 1].endswith(("\n", "\r")):
                    out[end - 1] = lines[end - 1] + ending
                pending_row = (after if after is not None else end, new)
        elif head == "option" and status == "active" and name not in header:
            has_tier = len(header) > 1 and header[1].strip().lower() == "tier"
            offset = 2 if has_tier else 1
            position = offset
            for i, column in enumerate(header[offset:]):
                if column == "global" or column.casefold() < name.casefold():
                    position = offset + i + 1
            for n in range(index, end):
                body, ending = _split_line(lines[n])
                cells = _cells(body)
                parts = body.split("|")
                if n == index:
                    cell = f" {name} "
                elif _is_separator(cells):
                    cell = "---"
                else:
                    cell = " x " if _column_cell(_option_id(cells[0]), cp) else "  "
                parts.insert(min(position + 1, len(parts) - 1 if body.rstrip().endswith("|") else len(parts)), cell)
                out[n] = "|".join(parts) + ending
        index = end
    if pending_row is not None:
        out.insert(*pending_row)
    return "".join(out)


def update_control_plane(root: pathlib.Path, name: str, status: str, origin: str, apply: bool) -> list[str]:
    from stratarc.config import load_config

    plane = paths.control_plane_file(root)
    relative = plane.relative_to(root).as_posix()
    if load_config(root).layout.control_plane_managed:
        # The reconciler derives the row and column from the root folder and the checkout, so it is the one writer.
        from stratarc.reconcile import main as reconcile_main

        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            reconcile_main(["--root", str(root)] + (["--check"] if not apply else []), snapshots=False)
        notes = [line for line in captured.getvalue().splitlines() if line.strip()]
        if not apply and not notes and name not in ControlPlane.load(plane).manifest:
            notes = ["the reconciler will list the new root"]
        return [f"control plane: {line}" for line in notes]
    if not plane.is_file():
        raise NewRefused(f"{relative} does not exist; create the control plane first")
    text = plane.read_bytes().decode("utf-8")
    cp = ControlPlane.load(plane)
    link = f"[{name}/]({pathlib.PurePath(os.path.relpath(paths.project_config_dir(root) / name / 'AGENTS.md', plane.parent)).as_posix()})"
    updated = add_to_control_plane(text, cp, name, status, origin, link)
    if updated == text:
        return []
    if apply:
        plane.write_bytes(updated.encode("utf-8"))
    parts = []
    if name not in cp.manifest:
        parts.append("row")
    if name not in cp.columns and status == "active":
        parts.append("column")
    return [f"control plane: add the {' and '.join(parts) or 'entries'} for {name} to {relative}"]


# ---- the checkout ------------------------------------------------------------


def merge_gitignore(template: pathlib.Path, target: pathlib.Path, apply: bool) -> list[str]:
    """Add the template's missing lines to the checkout's .gitignore, group by group; no line is removed or reordered."""
    wanted = template.read_text(encoding="utf-8")
    if not target.exists():
        if apply:
            target.write_text(wanted, encoding="utf-8")
        return [".gitignore: create from the visibility block"]
    current = target.read_text(encoding="utf-8")
    have = {line.strip() for line in current.splitlines()}
    additions: list[str] = []
    for group in re.split(r"\n\s*\n", wanted.strip("\n")):
        lines = group.splitlines()
        rules = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
        missing = [line for line in rules if line.strip() not in have]
        if not missing:
            continue
        comments = [line for line in lines if line.lstrip().startswith("#")]
        additions.append("\n".join([*comments, *missing]))
        have.update(line.strip() for line in missing)
    if not additions:
        return []
    if apply:
        lead = "" if current.endswith("\n") or not current else "\n"
        spacer = "\n" if current.strip() else ""
        target.write_text(current + lead + spacer + "\n\n".join(additions) + "\n", encoding="utf-8")
    return [f".gitignore: add {sum(len(a.splitlines()) for a in additions)} lines of the visibility block"]


def scaffold_checkout(root: pathlib.Path, checkout: pathlib.Path, apply: bool) -> list[str]:
    template = _template_dir(root, CHECKOUT_TEMPLATE)
    if not template.is_dir():
        return []
    actions: list[str] = []
    gitignore = template / ".gitignore"
    if gitignore.is_file():
        actions += merge_gitignore(gitignore, checkout / ".gitignore", apply)
    local = template / paths.local_dir_name(root)
    if local.is_dir():
        for source in _template_files(local):
            dest = checkout / paths.local_dir_name(root) / source.relative_to(local)
            if dest.exists():
                continue
            if apply:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
            actions.append(f"checkout: add {dest.relative_to(checkout).as_posix()}")
    return actions


# ---- checks ------------------------------------------------------------------


def registry_problems(root: pathlib.Path) -> list[str]:
    """Disagreement between the control plane, the root folders and the registries, one line each."""
    config_dir = paths.project_config_dir(root)
    cp = ControlPlane.load(paths.control_plane_file(root))
    remotes = read_remotes(config_dir)
    public = set(read_public(config_dir))
    folders = (
        {p.name for p in config_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))}
        if config_dir.is_dir()
        else set()
    )
    problems: list[str] = []
    for name in sorted(cp.manifest, key=str.casefold):
        if name in public:
            problems.append(f"{name}: is in {PUBLIC_TARGETS} but also has a control plane row")
            continue
        if name not in folders:
            problems.append(f"{name}: in the control plane but has no root folder")
        if name not in remotes:
            problems.append(f"{name}: in the control plane but has no {REMOTES} entry")
    for name in sorted(public, key=str.casefold):
        if name not in remotes:
            problems.append(f"{name}: in {PUBLIC_TARGETS} but has no {REMOTES} entry")
    for name in sorted(folders - set(cp.manifest), key=str.casefold):
        problems.append(f"{name}: has a root folder but is not in the control plane")
    return problems


def project_findings(root: pathlib.Path, name: str, public: bool) -> tuple[list[str], list[str]]:
    """(problems, pending) for one project: stale control plane, registry disagreement, drift findings.

    Findings that only say the checkout has not received its config yet are returned as pending, since delivery is `stratarc sync`'s job.
    """
    from stratarc import drift
    from stratarc.reconcile import main as reconcile_main

    problems: list[str] = []
    pending: list[str] = []
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        code = reconcile_main(["--root", str(root), "--check"], snapshots=False)
    if code:
        problems += [f"reconcile: {line}" for line in captured.getvalue().splitlines() if line.strip()] or ["reconcile: the control plane is stale"]
    problems += [line for line in registry_problems(root) if line.startswith(f"{name}:")]
    if public:
        return problems, pending
    for finding in drift.collect(root):
        if finding.project != name:
            continue
        if finding.rule in ("cp-stale", "cp-missing") and finding.severity != "info":
            pending.append(finding.line())
        else:
            problems.append(finding.line())
    return problems, pending


# ---- the commands ------------------------------------------------------------


def run_registry_check(root: pathlib.Path) -> int:
    try:
        problems = registry_problems(root)
    except NewRefused as error:
        print(f"{PROG}: {error}", file=sys.stderr)
        return 2
    for line in problems:
        print(f"registry: {line}")
    if not problems:
        print(f"registry: control plane, root folders and {REMOTES} agree")
    return 1 if problems else 0


def checkout_path(root: pathlib.Path, name: str, explicit: str | None) -> pathlib.Path:
    if explicit:
        return pathlib.Path(explicit).expanduser()
    return paths.projects_dir(root) / "active" / name


def project_status(checkout: pathlib.Path, base: pathlib.Path) -> str:
    try:
        first = checkout.relative_to(base).parts[0]
    except (ValueError, IndexError):
        return "active"
    return first if first in STATUS_FOLDERS else "active"


def run_new(
    root: pathlib.Path,
    name: str,
    *,
    checkout: str | None = None,
    remote: str | None = None,
    public: bool = False,
    workflows: bool = False,
    dry: bool = False,
) -> int:
    apply = not dry
    try:
        if not valid_name(name):
            raise NewRefused(f"{name!r} is not lowercase kebab-case (letters, digits and single hyphens)")
        if remote is not None and not REMOTE_PATTERN.match(remote):
            raise NewRefused(f"--remote {remote!r} must look like OWNER/REPO")
        config_dir = paths.project_config_dir(root)
        target = config_dir / name
        plane = paths.control_plane_file(root)
        cp = ControlPlane.load(plane)
        registered = name in cp.manifest or name in read_public(config_dir)
        complete = (target / "AGENTS.md").is_file()
        if public:
            if target.exists() or name in cp.manifest:
                raise NewRefused(f"{name} already has project configuration; a public repository gets none, so it cannot be added as public")
        elif complete and not registered:
            raise NewRefused(f"{name} already has a project root at {target.relative_to(root).as_posix()}/ that the control plane does not list; reconcile it instead of creating it")
        elif name in read_public(config_dir):
            raise NewRefused(f"{name} is listed in {PUBLIC_TARGETS}; remove it there first")

        actions: list[str] = []
        base = paths.projects_dir(root)
        where = checkout_path(root, name, checkout)
        status = project_status(where, base)
        if public:
            actions += add_public(config_dir, name, apply)
        else:
            actions += copy_root(root, name, apply, workflows)
            actions += update_control_plane(root, name, status, remote or "-", apply)
        if remote:
            actions += add_remote(config_dir, name, remote, apply)
        notes: list[str] = []
        if public:
            notes.append("public repository: no project configuration, row, column or checkout scaffolding")
        elif where.is_dir():
            actions += scaffold_checkout(root, where, apply)
        else:
            notes.append(f"checkout {where} does not exist; create it, then run this command again to add its .gitignore and local/ scaffolding")
    except NewRefused as error:
        print(f"{PROG}: refusing; {error}; nothing was written", file=sys.stderr)
        return 2

    verb = "would" if dry else "did"
    if actions:
        print(f"{PROG}: --new {name} {verb}:")
        for action in actions:
            print(f"  {action}")
    else:
        print(f"{PROG}: --new {name}: nothing to change, already set up")
    for note in notes:
        print(f"  note: {note}")
    if dry:
        return 0
    try:
        problems, pending = project_findings(root, name, public)
    except NewRefused as error:
        print(f"{PROG}: {error}", file=sys.stderr)
        return 2
    for line in problems:
        print(f"  problem: {line}")
    for line in pending:
        print(f"  pending: {line}")
    print(f"{PROG}: configuration is not delivered by this command; run `stratarc sync` (preview with `stratarc diff`) to deliver it to the checkout")
    print(f"{PROG}: {name} is {'clean' if not problems else f'not clean, {len(problems)} problems'}")
    return 1 if problems else 0
