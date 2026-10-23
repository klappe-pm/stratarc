"""The published tree names no private tool, personal path or work item code.

The patterns are built from fragments so this file does not match itself.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = {
    "private config repository": "llm" + r"[-_]root",
    "private env prefix": "LLM" + "_ROOT",
    "owner login": "kl" + "appe" + r"(?!-pm\b)",
    "owner email": "kevin" + r"\d+",
    "mail host": "proton" + "mail",
    "linter": "ly" + "nter",
    "tool a": r"\bor" + r"ca\b",
    "tool b": r"\bgr" + r"aft\b",
    "owner name": "Kevin" + r"\s+Lap" + "pe",
    "agent graph": "agent" + r"[-_]graph",
    "hook state directory": "agent" + r"[-_]hooks",
    "work item code": r"\bW" + r"I-\d+",
    "work item term": "work" + r"[- ]item",
    "integration": r"\bKa" + r"ta\b",
    "code review tool": "robo" + "rev",
    "provider renderer": "free" + "llmapi",
    "terminal tool": "node" + "term",
}


# The published author and the repository owner appear where a licence and a package need them.
ALLOWED = {"owner name": {"LICENSE", "pyproject.toml"}}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True
    )
    names = [name for name in result.stdout.decode().split("\0") if name]
    return [ROOT / name for name in names if (ROOT / name).is_file() and (ROOT / name) != Path(__file__).resolve()]


def test_no_tracked_file_names_a_private_term():
    compiled = {label: re.compile(pattern, re.IGNORECASE) for label, pattern in FORBIDDEN.items()}
    hits = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT)
        for label, pattern in compiled.items():
            if str(relative) in ALLOWED.get(label, ()):
                continue
            if pattern.search(str(relative)):
                hits.append(f"{relative}: path ({label})")
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{relative}:{number}: {label}")
    assert not hits, "\n".join(hits[:400])
