"""Load and check components.json, the one manifest of external components.

The manifest declares what the source root does not author itself: MCP servers, plugins, foreign hook groups, third-party skills, command-line dependencies and per-runtime settings.

Every entry carries a name, the runtimes it applies to, its owner, and wanted (false for a component known and deliberately unwanted), and each section adds its own shape (SECTION_KEYS): an MCP server a command (with args and env) or a url unless hosted, a plugin its marketplace (an OpenCode file plugin its path), a foreign hook group the match that finds it and, optionally, the registration an adapter renders when the source root is the one installing the group rather than only recognizing it, a third-party skill its installer and, where one entry installs several directories, their names, a dependency its command, install line and pinned version. runtime_settings.<runtime> holds exactly model, subagent_model, aliases, settings and provider (opencode only, a custom OpenAI-compatible provider) (RUNTIME_SETTINGS_KEYS). An unknown key is an error. Runtime names are the adapters' registry (stratarc.adapters._common.runtime_registry), not a list kept here. Secrets appear only as secret:// references; a literal the token-shaped detector matches is refused, and the message never repeats the value.

    python3 -m stratarc.components            validate, exit 1 on any problem
    python3 -m stratarc.components --list     print what is declared
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from importlib.resources import as_file
from typing import Any, Dict, List, Optional, Sequence, Tuple

from stratarc.adapters._common import runtime_registry
from stratarc.paths import source_root
from stratarc.resources import data_dir

MANIFEST_NAME = "components.json"

SECTIONS = (
    "mcp_servers",
    "plugins",
    "foreign_hooks",
    "third_party_skills",
    "dependencies",
)
TOP_LEVEL = ("version", "runtime_settings") + SECTIONS

# Per-section shapes: every section has a checked shape. Every entry carries the
# common keys; each section adds its own. A key in neither list is an error,
# so a typo cannot silently disable a check. Conditional requirements (a
# command or a url, a marketplace or a path) are checked in _check_section below.
COMMON_KEYS = ("name", "runtimes", "owner", "wanted", "description")
SECTION_KEYS: Dict[str, Tuple[str, ...]] = {
    "mcp_servers": ("command", "args", "env", "cwd", "url", "transport", "hosted"),
    "plugins": ("marketplace", "path"),
    "foreign_hooks": ("match", "registration"),
    "third_party_skills": ("installer", "skills"),
    "dependencies": ("command", "install", "version", "version_command", "platform"),
}
REQUIRED_STRINGS: Dict[str, Tuple[str, ...]] = {
    "foreign_hooks": ("match",),
    "third_party_skills": ("installer",),
    "dependencies": ("command", "install", "version"),
}
_MCP_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
# runtime_settings.<runtime>: the default model
# and subagent model, an alias map from the short names agent files use
# (opus, sonnet, haiku) to this runtime's model identifiers, and settings, a
# runtime-native passthrough object.
RUNTIME_SETTINGS_KEYS = ("model", "subagent_model", "aliases", "settings", "provider")
PLATFORMS = ("darwin", "linux")


def known_runtimes(adapters_dir: Optional[pathlib.Path] = None) -> Tuple[str, ...]:
    """The runtime names the adapters' registry declares."""
    return tuple(runtime_registry(adapters_dir))


class ManifestError(ValueError):
    """The manifest exists but cannot be read as JSON."""


def load(path: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """The manifest (default `<source root>/components.json`), or an empty one when the file does not exist yet."""
    if path is None:
        path = source_root() / MANIFEST_NAME
    if not path.exists():
        return {"version": 1}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ManifestError(f"cannot read {path.name}: {error}") from None
    if not isinstance(document, dict):
        raise ManifestError(f"{path.name} must hold a JSON object")
    return document


def _token_shaped(text: str) -> bool:
    """True when the packaged detector labels the text. Fails closed."""
    try:
        with as_file(data_dir("hooks/lib/secret-scan.sh")) as detector:
            result = subprocess.run(
                ["bash", str(detector), "label-stdin"],
                input=text,
                capture_output=True,
                text=True,
                timeout=10,
            )
    except (OSError, subprocess.SubprocessError):
        return True
    return result.returncode != 1


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def nonempty_string_list(value: Any) -> bool:
    """A non-empty list of non-empty strings."""
    return isinstance(value, list) and bool(value) and all(_nonempty_string(v) for v in value)


def _check_registration(entry: Dict[str, Any], label: str, runtimes_known: Sequence[str]) -> List[str]:
    """A foreign hook's registration map, checked for shape when the entry
    carries one.

    A wanted foreign hook is not always rendered: a hook that is rendered by
    every adapter carries a registration naming the captured file per runtime.
    A wanted foreign hook this repository does not render,
    only recognizes when another tool installs it, carries none, and its
    absence is not an error. Only a registration that is present is checked
    here. An unwanted entry is only ever found and removed by its match and
    is refused one entirely, in _check_section below.
    """
    registration = entry.get("registration")
    if not isinstance(registration, dict) or not registration:
        return [f"{label}: registration must be an object mapping each runtime to its captured file"]
    declared = entry.get("runtimes") if isinstance(entry.get("runtimes"), list) else []
    errors: List[str] = []
    for runtime, path in registration.items():
        if runtime not in runtimes_known:
            errors.append(f"{label}: registration: unknown runtime {runtime}")
        elif runtime not in declared:
            errors.append(f"{label}: registration: {runtime} is not in runtimes")
        if not _nonempty_string(path):
            errors.append(f"{label}: registration {runtime} must name the captured file, relative to the repository root")
    return errors


def _check_section(section: str, entry: Dict[str, Any], label: str, runtimes_known: Sequence[str] = ()) -> List[str]:
    """The checks one section adds to the common keys."""
    errors: List[str] = []
    for key in REQUIRED_STRINGS.get(section, ()):
        if not _nonempty_string(entry.get(key)):
            errors.append(f"{label}: needs {key}")
    if section == "foreign_hooks":
        if entry.get("wanted") is True:
            if "registration" in entry:
                errors.extend(_check_registration(entry, label, runtimes_known))
        elif "registration" in entry:
            errors.append(f"{label}: an unwanted foreign hook is found and removed by its match; it renders nothing")
    elif section == "third_party_skills":
        # A tool may install several skill directories under one entry, so the
        # entry may name them; the adapters' inventory matches the entry's own
        # name or any name here.
        skills = entry.get("skills")
        if "skills" in entry and not (
            isinstance(skills, list) and skills and all(_nonempty_string(name) for name in skills)
        ):
            errors.append(f"{label}: skills must be a list of directory names")
    elif section == "mcp_servers":
        # The adapters write the name as a TOML table key ([mcp_servers.<name>])
        # and a JSON key (the adapters' component renderer); a dot, space or
        # bracket would name a different table. A hosted connector is never
        # rendered, so it keeps the provider's name.
        if entry.get("hosted") is not True and not _MCP_NAME.match(str(entry.get("name") or "")):
            errors.append(f"{label}: name must be letters, digits, - or _ (it becomes a configuration key)")
        if "hosted" in entry and not isinstance(entry["hosted"], bool):
            errors.append(f"{label}: hosted must be true or false")
        # An account-level connector (hosted: true) is started by the
        # runtime's provider, not by a command or url this manifest names.
        if not entry.get("command") and not entry.get("url") and entry.get("hosted") is not True:
            errors.append(f"{label}: needs a command or a url")
        args = entry.get("args")
        if args is not None and not (isinstance(args, list) and all(isinstance(a, str) for a in args)):
            errors.append(f"{label}: args must be a list of strings")
        env = entry.get("env") or {}
        if not isinstance(env, dict):
            errors.append(f"{label}: env must be an object")
            env = {}
        for key, value in env.items():
            if not isinstance(value, str):
                errors.append(f"{label}: env {key} must be a string")
            elif not value.startswith("secret://") and _token_shaped(f"{key}={value}"):
                errors.append(f"{label}: env {key} holds a token-shaped literal; use a secret:// reference")
    elif section == "plugins":
        if "path" in entry:
            if not _nonempty_string(entry["path"]):
                errors.append(f"{label}: path must name the plugin file")
            if entry.get("runtimes") != ["opencode"]:
                errors.append(f"{label}: path is only for OpenCode file plugins; runtimes must be [\"opencode\"]")
        elif not _nonempty_string(entry.get("marketplace")):
            errors.append(f"{label}: needs marketplace")
    elif section == "dependencies":
        if "version_command" in entry and not _nonempty_string(entry["version_command"]):
            errors.append(f"{label}: version_command must be a command string")
        # platform: this dependency's command exists only on one platform
        # (for example a daemon that exists only on Linux). Absent means every
        # platform. The adapters' inventory skips a mismatched entry so one
        # machine's inventory does not report another platform's tool missing.
        if "platform" in entry and entry["platform"] not in PLATFORMS:
            errors.append(f"{label}: platform must be darwin or linux")
    return errors


def _check_runtime_settings(runtime: str, block: Dict[str, Any]) -> List[str]:
    """The shape of runtime_settings.<runtime> (RUNTIME_SETTINGS_KEYS)."""
    label = f"runtime_settings {runtime}"
    errors: List[str] = []
    for key in block:
        if key not in RUNTIME_SETTINGS_KEYS:
            errors.append(f"{label}: unknown key {key}")
    for key in ("model", "subagent_model"):
        if key in block and (not _nonempty_string(block[key]) or (runtime != "claude" and block[key].strip().lower() in ("inherit", "default"))):
            errors.append(f"{label}: {key} must be a model name")
    aliases = block.get("aliases")
    if "aliases" in block and not (
        isinstance(aliases, dict) and all(_nonempty_string(k) and _nonempty_string(v) for k, v in aliases.items())
    ):
        errors.append(f"{label}: aliases must map each short name to a model name")
    if "settings" in block and not isinstance(block["settings"], dict):
        errors.append(f"{label}: settings must be an object")
    if "provider" in block:
        provider = block["provider"]
        # A custom OpenAI-compatible provider is OpenCode's own config
        # concept (provider.<id>.npm/options/models, rendered by the opencode
        # adapter); no other runtime reads this key.
        if runtime != "opencode":
            errors.append(f"{label}: unknown key provider")
        elif not isinstance(provider, dict) or not all(isinstance(value, dict) for value in provider.values()):
            errors.append(f"{label}: provider must map each provider id to an object")
    return errors


def _check_entry(section: str, entry: Any, seen: set, runtimes_known: Sequence[str]) -> List[str]:
    if not isinstance(entry, dict):
        return [f"{section}: every entry must be an object"]
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        return [f"{section}: an entry has no name"]
    label = f"{section} {name}"
    errors: List[str] = []
    if name in seen:
        errors.append(f"{label}: declared twice")
    seen.add(name)
    allowed = set(COMMON_KEYS) | set(SECTION_KEYS[section])
    for key in entry:
        if key not in allowed:
            errors.append(f"{label}: unknown key {key}")
    runtimes = entry.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        errors.append(f"{label}: runtimes must be a non-empty list")
    else:
        for runtime in runtimes:
            if runtime not in runtimes_known:
                errors.append(f"{label}: unknown runtime {runtime}")
    if not isinstance(entry.get("owner"), str) or not entry.get("owner"):
        errors.append(f"{label}: owner must name this repository or the tool that installs it")
    if not isinstance(entry.get("wanted"), bool):
        errors.append(f"{label}: wanted must be true or false")
    if "description" in entry and not isinstance(entry["description"], str):
        errors.append(f"{label}: description must be a string")
    errors.extend(_check_section(section, entry, label, runtimes_known))
    return errors


def validate(document: Dict[str, Any], adapters_dir: Optional[pathlib.Path] = None) -> List[str]:
    """Every problem in the manifest; empty when it is well formed.

    Runtime names are checked against the adapters' registry; adapters_dir
    points it at another adapter directory (a test fixture).
    """
    runtimes_known = known_runtimes(adapters_dir)
    errors: List[str] = []
    if document.get("version") != 1:
        errors.append("version must be 1")
    for key in document:
        if key not in TOP_LEVEL:
            errors.append(f"unknown section {key}")
    settings = document.get("runtime_settings")
    if settings is not None and not isinstance(settings, dict):
        errors.append("runtime_settings must be an object keyed by runtime")
    elif settings:
        for runtime, value in settings.items():
            if runtime not in runtimes_known:
                errors.append(f"runtime_settings: unknown runtime {runtime}")
            elif not isinstance(value, dict):
                errors.append(f"runtime_settings: {runtime} must be an object")
            else:
                errors.extend(_check_runtime_settings(runtime, value))
    for section in SECTIONS:
        entries = document.get(section)
        if entries is None:
            continue
        if not isinstance(entries, list):
            errors.append(f"{section} must be a list")
            continue
        seen: set = set()
        for entry in entries:
            errors.extend(_check_entry(section, entry, seen, runtimes_known))
    return errors


def declared(
    document: Dict[str, Any], section: str, runtime: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """Name to entry for each wanted entry in a section, optionally for one runtime."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in document.get(section) or []:
        if not isinstance(entry, dict) or entry.get("wanted") is not True:
            continue
        if runtime and runtime not in (entry.get("runtimes") or []):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            out[name] = entry
    return out


def build_parser() -> argparse.ArgumentParser:
    """The command's parser; `stratarc` checks a command line against it before it looks for a source root."""
    parser = argparse.ArgumentParser(
        prog="stratarc components",
        description=(
            "Validate components.json, the one manifest of what the source root does not author\n"
            "itself: MCP servers, plugins, foreign hook groups, third party skills, command line\n"
            "dependencies and per runtime settings. It reports every unknown key, missing field,\n"
            "unknown runtime and literal secret (secrets belong in secret:// references), and\n"
            "exits 1 when it finds any. With --list it also prints each declared component as\n"
            "section, name and runtimes."
        ),
        epilog=(
            "examples:\n"
            "  stratarc components                                   validate the manifest\n"
            "  stratarc components --list                            validate, then list each component\n"
            "  stratarc components --manifest ./components.json      validate a manifest at another path"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manifest", type=pathlib.Path, default=None, help="manifest to read (default: <source root>/components.json)")
    parser.add_argument("--list", action="store_true", help="print what is declared")
    parser.add_argument("--root", type=pathlib.Path, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = args.manifest or source_root(args.root) / MANIFEST_NAME
    try:
        document = load(manifest_path)
    except ManifestError as error:
        print(f"components: {error}", file=sys.stderr)
        return 1
    errors = validate(document)
    for error in errors:
        print(f"components: {error}", file=sys.stderr)
    if args.list:
        for section in SECTIONS:
            for name, entry in sorted(declared(document, section).items()):
                print(f"{section}\t{name}\t{','.join(entry.get('runtimes') or [])}")
    if not errors:
        print(f"components: {manifest_path.name} is valid")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
