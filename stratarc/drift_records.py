"""Plan and decision record drift: pointers, supersede pairs, stale plans and two homes for one document.

- dc-pointer-dangling: a `.pointer` file whose target is missing, or that names no path or more than one;
- dc-dated-reference: an instruction file, hook or script cites a dated file name that a pointer already names;
- dc-superseded-cited: a record marked superseded is still cited as current by an instruction file;
- dc-supersede-unpaired: record A says it supersedes B, but B does not name A, or the reverse;
- dc-two-homes: a plan or decision with the same file name sits in the project root and in the checkout with different content;
- dc-plan-stale: a plan with status INPRG or REVIEW whose date-revised is older than a set number of days.

A `.pointer` file holds comment lines that start with `#` and one path relative to its own folder. A record's frontmatter may carry `status`, `date-revised`, `type` or `types`, `supersedes` and `superseded-by`. Everything is read with fixed patterns, and a run changes nothing.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import re

from stratarc import drift_levels

DATED = re.compile(r"\b(\d{4}-\d{2}-\d{2}-[\w.-]+\.md)\b")
KINDS = {"plan", "plans", "decision", "decisions", "adr"}
LIVE_STATUSES = {"INPRG", "REVIEW"}
STALE_DAYS = 14
SCAN_SUFFIXES = (".md", ".sh", ".py", ".toml", ".json", ".yml", ".yaml")
PRUNE = {"node_modules", "venv", "__pycache__", "dist", "build"}


def frontmatter(text: str) -> dict[str, list[str]]:
    """Top level keys of a leading `---` block, every value as a list of strings."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        block.append(line)
    else:
        return {}
    data: dict[str, list[str]] = {}
    key = ""
    for line in block:
        match = re.match(r"^([\w-]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                data[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                data[key] = [value.strip("'\"")] if value else []
        elif key and re.match(r"^\s+-\s+", line):
            data[key].append(re.sub(r"^\s+-\s+", "", line).strip().strip("'\""))
    return data


def _walk(checkout: pathlib.Path) -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for folder, dirs, files in os.walk(checkout):
        here = pathlib.Path(folder)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in PRUNE and not (here / d / ".git").exists())
        found += [here / name for name in sorted(files)]
    return found


def _stem(reference: str) -> str:
    return pathlib.PurePosixPath(reference.strip()).name.removesuffix(".md")


def _is_record(data: dict[str, list[str]]) -> bool:
    return bool(KINDS & {v.lower() for key in ("type", "types") for v in data.get(key, [])})


def pointer_targets(path: pathlib.Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def check(checkout: pathlib.Path, config_dir: pathlib.Path | None = None, today: datetime.date | None = None, stale_days: int = STALE_DAYS) -> list[dict]:
    """Findings for one checkout as dicts of rule, severity, path, message and hint; the caller adds the project."""
    today = today or datetime.date.today()
    found: list[dict] = []

    def add(rule: str, severity: str, path: pathlib.Path, message: str, hint: str) -> None:
        found.append({"rule": rule, "severity": severity, "path": path.relative_to(checkout).as_posix(), "message": message, "hint": hint})

    files = _walk(checkout)
    pointed: set[str] = set()
    for path in (p for p in files if p.suffix == ".pointer"):
        targets = pointer_targets(path)
        if len(targets) != 1:
            add("dc-pointer-dangling", "error", path, f"{path.name} must name exactly one path, it names {len(targets)}", "keep one path line and move the rest into comments")
            continue
        if not (path.parent / targets[0]).exists():
            add("dc-pointer-dangling", "error", path, f"{path.name} points at {targets[0]}, which does not exist", "point it at the current file")
        else:
            pointed.add(pathlib.PurePosixPath(targets[0]).name)

    records: dict[str, tuple[pathlib.Path, dict[str, list[str]]]] = {}
    for path in (p for p in files if p.suffix == ".md"):
        data = frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if _is_record(data):
            records.setdefault(path.name.removesuffix(".md"), (path, data))

    for stem, (path, data) in records.items():
        status = (data.get("status") or [""])[0].upper()
        kinds = {v.lower() for key in ("type", "types") for v in data.get(key, [])}
        revised = (data.get("date-revised") or [""])[0]
        if status in LIVE_STATUSES and kinds & {"plan", "plans"} and re.fullmatch(r"\d{4}-\d{2}-\d{2}", revised):
            age = (today - datetime.date.fromisoformat(revised)).days
            if age > stale_days:
                add("dc-plan-stale", "info", path, f"{path.name} is {status} and was last revised {age} days ago", "revise the plan or change its status")
        for other in (_stem(v) for v in data.get("supersedes", [])):
            theirs = records.get(other)
            if theirs and stem not in {_stem(v) for v in theirs[1].get("superseded-by", [])}:
                add("dc-supersede-unpaired", "warn", path, f"{path.name} supersedes {other}, which does not name it in superseded-by", f"add superseded-by: {stem} to {other}")
        for other in (_stem(v) for v in data.get("superseded-by", [])):
            theirs = records.get(other)
            if theirs and stem not in {_stem(v) for v in theirs[1].get("supersedes", [])}:
                add("dc-supersede-unpaired", "warn", path, f"{path.name} is superseded by {other}, which does not name it in supersedes", f"add {stem} to supersedes in {other}")

    superseded = {stem for stem, (_p, data) in records.items() if data.get("superseded-by")}
    for path in files:
        if path.suffix not in SCAN_SUFFIXES:
            continue
        relative = path.relative_to(checkout)
        surface = path.name in drift_levels.SURFACES
        script = relative.parts[0] in ("hooks", "scripts", ".githooks") if len(relative.parts) > 1 else False
        if not (surface or script):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in dict.fromkeys(DATED.findall(text)):
            if name in pointed:
                add("dc-dated-reference", "warn", path, f"{path.name} cites {name}, which a pointer already names", "cite the pointer file instead of the dated name")
        if surface:
            for stem in sorted(superseded):
                if re.search(rf"(?<![\w-]){re.escape(stem)}(?:\.md)?(?![\w-])", text):
                    add("dc-superseded-cited", "warn", path, f"{path.name} cites {stem}, which is marked superseded", "cite the record that replaced it")

    if config_dir is not None and config_dir.is_dir():
        for source in (p for p in config_dir.rglob("*.md") if p.name not in drift_levels.SURFACES):
            data = frontmatter(source.read_text(encoding="utf-8", errors="replace"))
            twin = records.get(source.name.removesuffix(".md"))
            if _is_record(data) and twin and twin[0].read_bytes() != source.read_bytes():
                add("dc-two-homes", "error", twin[0], f"{twin[0].name} exists in the project root and in the checkout with different content", "keep one home for the document and remove the other copy")
    return found
