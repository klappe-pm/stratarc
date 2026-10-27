"""Folder level drift: instruction files below a checkout root, and what they say against their ancestors.

The rules read one checkout and need no control plane, so a session start can run them in milliseconds.

- lv-undeclared-nested: an instruction file below the root that the project root does not declare in `surfaces.json` under `"nested"`;
- lv-surface-split: sibling surfaces in one nested folder that differ where the project's copy list says they are copies of `AGENTS.md`;
- lv-fact-conflict: a nested file and an ancestor give different commands for the same job (package manager, test, build, lint);
- lv-restated: a nested file repeats a paragraph of an ancestor word for word;
- lv-dead-reference: a Markdown link or backticked path in an instruction file that does not resolve.

Facts come from fixed patterns over fenced blocks and inline code, never from a model. A run is repeatable and changes nothing.
"""

from __future__ import annotations

import os
import pathlib
import re

SURFACES = ("AGENTS.md", "CLAUDE.md", "CODEX.md", "GEMINI.md")
EXTENSIONS = (".md", ".py", ".json", ".toml", ".sh", ".yml", ".yaml", ".ts", ".js", ".txt")
MIN_RESTATED_WORDS = 12

FENCE = re.compile(r"^(```|~~~)")
INLINE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
TOOLS = ("npm", "pnpm", "yarn", "bun", "uv", "pip", "pip3", "poetry", "pipenv")
JOBS = {
    "test": re.compile(r"\b(pytest|jest|vitest|go test|cargo test|make test|npm test|pnpm test|yarn test|npm run test|python3? -m unittest)\b"),
    "build": re.compile(r"\b(npm run build|pnpm build|pnpm run build|yarn build|make build|cargo build|go build|uv build|python3? -m build)\b"),
    "lint": re.compile(r"\b(eslint|ruff|flake8|golangci-lint|make lint|npm run lint|pnpm lint|pnpm run lint|yarn lint)\b"),
}
PRUNE = {"node_modules", "venv", "__pycache__", "dist", "build"}


def instruction_files(checkout: pathlib.Path) -> list[pathlib.Path]:
    """Every surface file in the checkout, root first. Dot folders, vendored folders and nested repositories are skipped."""
    found: list[pathlib.Path] = []
    for folder, dirs, files in os.walk(checkout):
        here = pathlib.Path(folder)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in PRUNE and not (here / d / ".git").exists())
        found += [here / name for name in SURFACES if name in files]
    return sorted(found, key=lambda p: (len(p.relative_to(checkout).parts), p.as_posix()))


def _prose_and_code(text: str) -> tuple[list[str], list[str]]:
    """The paragraphs outside fences and the command lines inside fences and inline code."""
    paragraphs: list[str] = []
    commands: list[str] = []
    current: list[str] = []
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line.strip()):
            fenced = not fenced
            continue
        if fenced:
            command = line.strip().removeprefix("$ ").strip()
            if command and not command.startswith("#"):
                commands.append(command)
            continue
        commands += [m.group(1).strip() for m in INLINE.finditer(line)]
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs, commands


def facts(commands: list[str]) -> dict[str, set[str]]:
    """job -> the distinct commands a file gives for it."""
    out: dict[str, set[str]] = {}
    for command in commands:
        words = command.split()
        if not words:
            continue
        normal = " ".join(words)
        if words[0] in TOOLS:
            out.setdefault("package-manager", set()).add(words[0])
        for job, pattern in JOBS.items():
            if pattern.search(normal):
                out.setdefault(job, set()).add(normal)
    return out


def _normal(paragraph: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", paragraph)).strip().lower()


def ancestors(checkout: pathlib.Path, path: pathlib.Path) -> list[pathlib.Path]:
    """AGENTS.md files of every folder above the file's own, root first."""
    chain: list[pathlib.Path] = []
    folder = path.parent
    while folder != checkout and checkout in folder.parents:
        folder = folder.parent
        candidate = folder / "AGENTS.md"
        if candidate.is_file():
            chain.append(candidate)
    return list(reversed(chain))


def _candidates(text: str) -> list[tuple[str, bool]]:
    """Link targets and backticked paths worth resolving, each with whether it is a firm reference.

    A Markdown link, or a path with a folder part, is firm. A bare file name or a lone folder name is often a description of a layout, so it is reported at info level.
    """
    found: list[tuple[str, bool]] = []
    for target in LINK.findall(text):
        target = target.split("#", 1)[0]
        if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            found.append((target, True))
    for span in INLINE.findall(text):
        if re.fullmatch(r"[\w./-]+", span) and (("/" in span) or span.endswith(EXTENSIONS)) and not span.startswith(("/", "~")) and "..." not in span and span != ".":
            found.append((span, "/" in span.rstrip("/")))
    return found


def dead_references(checkout: pathlib.Path, path: pathlib.Path, text: str) -> list[tuple[str, bool]]:
    """(target, firm) for every reference that resolves neither beside the file nor from the checkout root."""
    missing: dict[str, bool] = {}
    for target, firm in _candidates(text):
        if target.startswith(("/", "~")):
            continue
        if not ((path.parent / target).exists() or (checkout / target).exists()):
            missing[target] = missing.get(target, False) or firm
    return list(missing.items())


def check(checkout: pathlib.Path, declared: set[str], copies: tuple[str, ...] = SURFACES) -> list[dict]:
    """Findings for one checkout as dicts of rule, severity, path, message and hint; the caller adds the project."""
    found: list[dict] = []

    def add(rule: str, severity: str, path: pathlib.Path, message: str, hint: str) -> None:
        found.append({"rule": rule, "severity": severity, "path": path.relative_to(checkout).as_posix(), "message": message, "hint": hint})

    files = instruction_files(checkout)
    by_folder: dict[pathlib.Path, list[pathlib.Path]] = {}
    for path in files:
        by_folder.setdefault(path.parent, []).append(path)

    for path in files:
        rel = path.relative_to(checkout).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        nested = path.parent != checkout
        if nested and rel not in declared and path.parent.relative_to(checkout).as_posix() not in declared:
            add("lv-undeclared-nested", "warn", path, f"{rel} is an instruction file below the root that the project root does not declare", 'list it under "nested" in the project root\'s surfaces.json, or remove it')
        sibling = path.parent / "AGENTS.md"
        mirror = path.name != "AGENTS.md" and sibling.is_file() and sibling.read_bytes() == path.read_bytes()
        for target, firm in ([] if mirror else dead_references(checkout, path, text)):
            add("lv-dead-reference", "warn" if firm else "info", path, f"{rel} names {target}, which does not exist", "fix the path or remove the reference")
        if not nested:
            continue
        paragraphs, commands = _prose_and_code(text)
        own = facts(commands)
        for ancestor in ancestors(checkout, path):
            parent_text = ancestor.read_text(encoding="utf-8", errors="replace")
            parent_paragraphs, parent_commands = _prose_and_code(parent_text)
            theirs = facts(parent_commands)
            for job, values in own.items():
                other = theirs.get(job)
                if other and values.isdisjoint(other):
                    add("lv-fact-conflict", "error", path, f"{rel} gives {job} as {sorted(values)[0]!r} but {ancestor.relative_to(checkout).as_posix()} gives {sorted(other)[0]!r}", "make the nested file agree with its ancestor, or state the difference as an explicit exception")
            seen = {_normal(p) for p in parent_paragraphs if len(p.split()) >= MIN_RESTATED_WORDS}
            for paragraph in paragraphs:
                if len(paragraph.split()) >= MIN_RESTATED_WORDS and _normal(paragraph) in seen:
                    add("lv-restated", "warn", path, f"{rel} repeats a paragraph of {ancestor.relative_to(checkout).as_posix()}: {paragraph[:60]}", "link to the ancestor instead of copying it")

    for folder, members in by_folder.items():
        if folder == checkout:
            continue
        master = folder / "AGENTS.md"
        if not master.is_file():
            continue
        for member in members:
            if member.name != "AGENTS.md" and member.name in copies and member.read_bytes() != master.read_bytes():
                add("lv-surface-split", "error", member, f"{member.relative_to(checkout).as_posix()} differs from {master.relative_to(checkout).as_posix()} where the project lists it as a copy", "regenerate the copy from AGENTS.md or take it off the copy list")
    return found


def explain(checkout: pathlib.Path, target: pathlib.Path) -> list[str]:
    """Every instruction file that applies to a path, from the checkout root to its folder, with conflicts marked."""
    folder = target if target.is_dir() else target.parent
    chain = [checkout]
    chain += [checkout / part for part in _walk_down(checkout, folder)]
    lines: list[str] = []
    for level in chain:
        for name in SURFACES:
            if (level / name).is_file():
                lines.append((level / name).relative_to(checkout).as_posix())
    conflicts = [f for f in check(checkout, set()) if f["rule"] in ("lv-fact-conflict", "lv-surface-split") and any(f["path"] == line for line in lines)]
    return lines + [f"conflict {f['rule']}: {f['message']}" for f in conflicts]


def _walk_down(checkout: pathlib.Path, folder: pathlib.Path) -> list[str]:
    parts = folder.relative_to(checkout).parts
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]
