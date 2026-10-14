"""The documentation under docs/ stays accurate, linked and consistently styled."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
GENERATOR = REPO_ROOT / "scripts" / "docs" / "generate-reference.py"

SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "nor", "of", "on", "or", "the", "to", "vs", "via", "with", "into", "from"}
FENCE = re.compile(r"^\s*```")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def markdown_files() -> list[Path]:
    root_files = [REPO_ROOT / name for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md", "CHANGELOG.md", "CODE_OF_CONDUCT.md") if (REPO_ROOT / name).is_file()]
    return sorted(DOCS.rglob("*.md")) + root_files + sorted((REPO_ROOT / "examples").rglob("README.md"))


def headings(path: Path) -> list[tuple[int, str]]:
    found, fenced = [], False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match:
            found.append((number, match.group(2)))
    return found


def prose(path: Path) -> str:
    """The page without fenced blocks and code spans, where an example link is not a link."""
    kept, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept)


def slug(text: str) -> str:
    text = re.sub(r"[`*]", "", text.lower())
    return re.sub(r"[^a-z0-9 _-]", "", text).strip().replace(" ", "-")


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_reference", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_generated_pages_match_the_code():
    stale = load_generator().check_generated(REPO_ROOT)
    assert not stale, f"run python3 scripts/docs/generate-reference.py: {stale}"


def test_the_generator_check_fails_with_status_6_after_a_generated_page_is_edited(tmp_path):
    copy = tmp_path / "repo"
    (copy / "docs" / "reference" / "generated").mkdir(parents=True)
    for name in ("commands.md", "errors.md"):
        (copy / "docs" / "reference" / "generated" / name).write_text((DOCS / "reference" / "generated" / name).read_text(encoding="utf-8"), encoding="utf-8")
    command = [sys.executable, "-I", str(GENERATOR), "--repo", str(copy), "--check"]
    assert subprocess.run(command, capture_output=True, text=True).returncode == 0
    page = copy / "docs" / "reference" / "generated" / "commands.md"
    page.write_text(page.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
    assert subprocess.run(command, capture_output=True, text=True).returncode == 6


@pytest.mark.parametrize("path", markdown_files(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_every_relative_link_resolves(path):
    text = prose(path)
    anchors_of: dict[Path, set[str]] = {}

    def anchors(target: Path) -> set[str]:
        if target not in anchors_of:
            anchors_of[target] = {slug(text) for _n, text in headings(target)}
        return anchors_of[target]

    for target in LINK.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue
        name, _, fragment = target.partition("#")
        resolved = (path.parent / name).resolve() if name else path
        assert resolved.exists(), f"{path.relative_to(REPO_ROOT)} links to {target}, which does not exist"
        if fragment and resolved.suffix == ".md":
            assert fragment in anchors(resolved), f"{path.relative_to(REPO_ROOT)} links to {target}, which has no such heading"


@pytest.mark.parametrize("path", sorted(DOCS.rglob("*.md")), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_every_heading_is_title_case(path):
    bad = []
    for number, text in headings(path):
        outside_code = re.sub(r"`[^`]*`", "", text)
        for index, word in enumerate(outside_code.split()):
            core = re.sub(r"^[^A-Za-z]*|[^A-Za-z]*$", "", word)
            if not core or core[0].isupper() or any(ch.isdigit() for ch in core):
                continue
            if core.lower() in SMALL_WORDS and index > 0:
                continue
            bad.append(f"{number}: {text}")
            break
    assert not bad, f"{path.relative_to(REPO_ROOT)} has headings that are not Title Case: {bad}"


@pytest.mark.parametrize("path", sorted(DOCS.rglob("*.md")), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_no_page_records_session_provenance(path):
    text = path.read_text(encoding="utf-8")
    front = text.split("---", 2)[1] if text.startswith("---") else ""
    assert not re.search(r"^(models|providers|session-link)\s*:", front, re.MULTILINE)


def test_no_page_is_hard_wrapped():
    wrapped = []
    for path in sorted(DOCS.rglob("*.md")):
        fenced, previous = False, ""
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                fenced = not fenced
                previous = ""
                continue
            plain = bool(line.strip()) and not fenced and not re.match(r"^\s*([-*>|#]|\d+\.)", line) and not line.startswith("<!--")
            if plain and previous:
                wrapped.append(f"{path.relative_to(REPO_ROOT)}:{number}")
            previous = line if plain else ""
    assert not wrapped, wrapped[:10]
