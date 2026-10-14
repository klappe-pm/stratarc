"""Guided setup: the first thing a bare `stratarc` does on a machine with no source root.

Setup asks where the source root should live, scaffolds it from the bundled template (or adopts one that already holds `stratarc.toml`), enables the runtimes whose directories exist, records the root in the home's `config.toml` so later commands find it from any directory, previews the first deploy and deploys only on an explicit yes. Every prompt goes through the `ask` and `say` callables, so a test drives it without a terminal.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from stratarc import paths
from stratarc.messages import INTERRUPTED, CliError
from stratarc.resources import data_dir

TEMPLATE = "templates/source-root"
DEFAULT_TARGET = "~/stratarc-source"
DOCS = "https://github.com/klappe-pm/stratarc/blob/main/docs"

Ask = Callable[[str], str]
Say = Callable[[str], None]


# ----- scaffolding and the files setup writes -----


def _copy_tree(src, dest: Path) -> int:
    """Copy a Traversable tree into ``dest``; return the number of files written."""
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for child in sorted(src.iterdir(), key=lambda c: c.name):
        if child.name == "__pycache__":
            continue
        target = dest / child.name
        if child.is_dir():
            count += _copy_tree(child, target)
        elif child.is_file():
            target.write_bytes(child.read_bytes())
            count += 1
    return count


def check_target(target: Path) -> None:
    """Refuse a target that is a file or a non-empty directory."""
    if target.exists():
        if not target.is_dir():
            raise CliError("msg-1006", param="target", path=target)
        if any(target.iterdir()):
            raise CliError("msg-1005", param="target", path=target)


def scaffold(target: Path) -> int:
    """Write the bundled source-root template into an absent or empty ``target``; return the file count."""
    check_target(target)
    template = data_dir(TEMPLATE)
    if not template.is_dir():
        raise CliError("msg-1007")
    return _copy_tree(template, target)


def set_enabled(config_file: Path, enabled: set[str]) -> None:
    """Set `enabled` in every `[runtimes.NAME]` table of ``config_file`` by editing its text, so its comments survive."""
    lines = config_file.read_text(encoding="utf-8").splitlines()
    table = None
    for index, line in enumerate(lines):
        header = re.match(r"\s*\[runtimes\.([A-Za-z0-9_-]+)\]\s*$", line)
        if header:
            table = header.group(1)
            continue
        if line.lstrip().startswith("["):
            table = None
            continue
        if table is not None and re.match(r"\s*enabled\s*=", line):
            lines[index] = f"enabled = {'true' if table in enabled else 'false'}"
    config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remember(root: Path) -> Path:
    """Record ``root`` as `source_root` in the home's config.toml, keeping every other key; return the file."""
    from stratarc import home_layout

    home_layout.ensure_layout()
    path = paths.remembered_config()
    data = home_layout.read_toml(path)
    data[paths.REMEMBERED_KEY] = str(root)
    home_layout.write_toml(path, data)
    return path


# ----- the conversation -----


def _display(path: Path) -> str:
    home = paths.home()
    try:
        return "~/" + path.relative_to(home).as_posix()
    except ValueError:
        return str(path)


def _expand(answer: str) -> Path:
    """A typed path, with `~` resolved against the stratarc home so a redirected home is honored."""
    text = answer.strip()
    if text == "~" or text.startswith("~/"):
        text = str(paths.home()) + text[1:]
    return Path(text).expanduser().resolve()


def _yes(answer: str, default: bool = False) -> bool:
    text = answer.strip().lower()
    if not text:
        return default
    return text in ("y", "yes")


def _choose_root(ask: Ask, say: Say) -> tuple[Path, bool]:
    """Ask until the answer is a usable directory; return it and whether it already holds a source root."""
    while True:
        answer = ask(f"Where should your source root live? [{DEFAULT_TARGET}] ") or DEFAULT_TARGET
        target = _expand(answer)
        if (target / paths.CONFIG_NAME).is_file():
            if _yes(ask(f"{_display(target)} already holds a source root. Use it? [Y/n] "), default=True):
                return target, True
            continue
        try:
            check_target(target)
        except CliError as error:
            say(f"  {error.problem} {error.recovery}")
            continue
        return target, False


def _choose_runtimes(root: Path, ask: Ask, say: Say) -> set[str]:
    from stratarc.config import load_config
    from stratarc.sync import load_runtimes

    found = load_runtimes(root=root)
    configured = load_config(root).runtimes
    installed = sorted(name for name, (_module, target) in found.items() if target.is_dir())
    current = sorted(name for name, runtime in configured.items() if runtime.enabled)
    say("")
    say("Runtimes stratarc can configure:")
    for name, (_module, target) in sorted(found.items()):
        state = "installed" if target.is_dir() else "not found"
        say(f"  {name:<10} {_display(target):<24} {state}")
    default = installed or current
    say("A runtime that is not installed is skipped by sync until its directory exists.")
    while True:
        answer = ask(f"Runtimes to enable, separated by commas, or none [{', '.join(default) or 'none'}] ").strip()
        if not answer:
            return set(default)
        if answer.lower() == "none":
            return set()
        chosen = {part.strip() for part in answer.split(",") if part.strip()}
        unknown = sorted(chosen - set(found))
        if not unknown:
            return chosen
        say(f"  Not a runtime stratarc knows: {', '.join(unknown)}. Choose from {', '.join(sorted(found))}.")


def _occupied(root: Path, enabled: set[str]) -> list[str]:
    """The enabled runtime targets that already hold files stratarc has not deployed."""
    from stratarc.sync import load_runtimes

    occupied = []
    for name, (_module, target) in sorted(load_runtimes(root=root).items()):
        if name not in enabled or not target.is_dir():
            continue
        if any(target.iterdir()) and not any(target.glob(".*-deploy.json")):
            occupied.append(f"{name} ({_display(target)})")
    return occupied


def _next_steps(say: Say) -> None:
    say("")
    say("Next:")
    say("  stratarc            show where your source root is and what to run")
    say("  stratarc diff       preview what a deploy would change")
    say("  stratarc sync       deploy the source into every enabled runtime")
    say("  stratarc doctor     check the install, the home and the source root")
    say("  stratarc help CMD   explain one command")
    say(f"Guides: {DOCS}/README.md")


def run(ask: Ask = input, say: Say = print) -> int:
    """Walk through setup; return the exit status. Raises `CliError` for a refusal that ends it."""
    written: list[str] = []
    try:
        return _run(ask, say, written)
    except (EOFError, KeyboardInterrupt):
        say("")
        say("Setup stopped." + (" Already written: " + "; ".join(written) + "." if written else " Nothing was written."))
        say("Run `stratarc setup` to start again.")
        return INTERRUPTED


def _run(ask: Ask, say: Say, written: list[str]) -> int:
    from stratarc import reconcile, sync

    say("Welcome to stratarc. One source of agent configuration, deployed to every runtime you use.")
    say("Setup creates a source root (a directory you keep in git), picks your runtimes and previews the first deploy.")
    say("Nothing is deployed until you say yes. Press Ctrl+C to stop at any time.")
    say("")
    root, adopted = _choose_root(ask, say)
    if adopted:
        say(f"Using the source root in {_display(root)}.")
    else:
        count = scaffold(root)
        written.append(f"{count} files in {_display(root)}")
        say(f"Wrote {count} files to {_display(root)}.")
        enabled = _choose_runtimes(root, ask, say)
        set_enabled(root / paths.CONFIG_NAME, enabled)
        say(f"Enabled: {', '.join(sorted(enabled)) or 'none'}. Change this any time in {_display(root / paths.CONFIG_NAME)}.")

    config = remember(root)
    written.append(f"the source root in {_display(config)}")
    say(f"Recorded the source root in {_display(config)}, so `stratarc` finds it from any directory.")

    root_args = ["--root", str(root)]
    if reconcile.main(root_args) not in (0, None):
        say("The control plane could not be refreshed; run `stratarc reconcile` to see why.")
        _next_steps(say)
        return 1

    from stratarc.config import load_config

    enabled_now = {name for name, runtime in load_config(root).runtimes.items() if runtime.enabled}
    if not enabled_now:
        say("No runtime is enabled, so there is nothing to deploy yet.")
        _next_steps(say)
        return 0

    say("")
    say("Preview of the first deploy (nothing is written):")
    preview = sync.main(["--diff", *root_args])
    if preview not in (0, None):
        say("The preview failed; fix what it reports, then run `stratarc diff`.")
        _next_steps(say)
        return preview
    occupied = _occupied(root, enabled_now)
    if occupied:
        say("")
        say(f"These runtimes already hold configuration stratarc did not write: {', '.join(occupied)}.")
        say(f"A deploy writes only the files the preview lists and leaves everything else in those directories alone. To bring your existing configuration into the source first, see {DOCS}/how-to-guides/migrate-existing-config.md")
    say("")
    if not _yes(ask("Deploy now? [y/N] ")):
        say("Not deployed. Run `stratarc sync` when you are ready.")
        _next_steps(say)
        return 0
    from stratarc.cli import _require_writable_home

    _require_writable_home()
    code = sync.main(root_args)
    if code not in (0, None):
        say(f"The deploy did not finish (exit {code}). See {DOCS}/how-to-guides/troubleshooting.md")
        return code
    say("Deployed.")
    _next_steps(say)
    return 0


# ----- the status a bare `stratarc` prints once set up -----


def status(root: Path, origin: str) -> str:
    """A short summary of where the source root is, what is enabled and what to run next."""
    from stratarc.config import load_config
    from stratarc.sync import load_runtimes

    lines = [f"source root   {_display(root)} (from {origin})"]
    configured = load_config(root).runtimes
    for name, (_module, target) in sorted(load_runtimes(root=root).items()):
        declared = configured.get(name)
        if declared is not None and not declared.enabled:
            continue
        state = "installed" if target.is_dir() else "not installed, skipped"
        lines.append(f"  {name:<10} {_display(target)} ({state})")
    lines += [
        "",
        "Common commands:",
        "  stratarc diff       preview what a deploy would change",
        "  stratarc sync       deploy the source into every enabled runtime",
        "  stratarc check      exit 6 when anything deployed is out of date",
        "  stratarc doctor     check the install, the home and the source root",
        "  stratarc setup      set up another source root",
        "  stratarc help       list every command; `stratarc help CMD` explains one",
    ]
    return "\n".join(lines)
