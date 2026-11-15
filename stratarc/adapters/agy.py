"""Antigravity CLI (agy) runtime adapter: skills and the default model.

Target: ~/.gemini/antigravity-cli, where agy keeps settings.json and its global
skills/<name>/SKILL.md (agy's published settings schema,
https://antigravity.google/schemas/v1/settings.json, and its skills documentation).

Rendered:
  - skills/ to skills/, add and update only; a target-only skill directory is
    left for `prune`, which owned_outputs drives.
  - the default model: runtime_settings.agy.model of the staged components.json,
    translated through runtime_settings.agy.aliases, into the "model" key of
    settings.json. The schema defines that key as a string holding the model's
    label. Every other key in settings.json is left alone, and a settings.json
    that is not a JSON object is not touched.

agy serves models from several providers (Gemini, Claude, GPT-OSS), so an alias
maps a short name (opus, sonnet, haiku) or a provider/model id to the label agy
writes. A Claude short name with no alias is not written, because agy cannot read
it. Nothing is written while runtime_settings.agy.model is absent.

Not rendered, on purpose:
  - instructions: agy reads ~/.gemini/GEMINI.md, which the gemini adapter writes
    from AGENTS.md.
  - hooks, rules, commands, agents, permissions and MCP servers. hook_registry is
    None and every canonical hook event is a deliberate drop.
"""

from __future__ import annotations

import json
from pathlib import Path

from ._common import OwnedDir, mirror_skills, skill_excludes
from ._components import default_models
from ._inventory import Item, unreadable

# This runtime's entry in the runtime registry (_common.runtime_registry).
# hook_events lists what sync() handles, a deliberate drop included: agy has no
# hook registry this adapter renders, so every event is dropped.
RUNTIME = {
    "name": "agy",
    "target": ".gemini/antigravity-cli",
    "hook_registry": None,
    "hook_events": [
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "Stop",
        "UserPromptSubmit",
        "SessionStart",
        "SessionEnd",
        "SubagentStart",
        "SubagentStop",
    ],
}

_MODEL_KEY = "model"


def _render_model(source: Path, target: Path, dry_run: bool) -> list[str]:
    model = default_models(source, RUNTIME["name"]).get("model")
    if model is None:
        return []
    path = target / "settings.json"
    document: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(loaded, dict):
            return []
        document = loaded
    if document.get(_MODEL_KEY) == model:
        return []
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**document, _MODEL_KEY: model}, indent=2) + "\n", encoding="utf-8")
    return [f"set settings.json {_MODEL_KEY} to {model}"]


def sync(source: Path, target: Path, dry_run: bool = False) -> list[str]:
    """Sync the selected skills and the default model into Antigravity CLI."""
    actions: list[str] = []
    skills = source / "skills"
    if skills.is_dir():
        actions.extend(mirror_skills(skills, target / "skills", dry_run))
    actions.extend(_render_model(source, target, dry_run))
    return actions


def owned_outputs(source: Path, target: Path) -> list[OwnedDir]:
    """Directories this adapter owns in an Antigravity CLI target tree.

    Only skills/ is owned. The target root also holds agy's own state
    (settings.json, keybindings.json, plugins/), so it is not declared.
    """
    skills = source / "skills"
    if not skills.is_dir():
        return []
    excluded = skill_excludes(skills)
    names = frozenset(p.name for p in skills.iterdir() if p.is_dir() and p.name not in excluded)
    return [OwnedDir("skill", target / "skills", names, per_item=True, exclude=frozenset(excluded))]


_PLUGINS_UNCONFIRMED = (
    "unconfirmed plugin registry; plugins/ holds installed plugins but no confirmed "
    "list of them, and a live check confirms it"
)


def external_inventory(target: Path) -> list[Item]:
    """Every external item Antigravity CLI holds. Its plugins directory is not
    listed until its registry is confirmed live, so it is reported unreadable."""
    return [unreadable(RUNTIME["name"], "plugin", target / "plugins", _PLUGINS_UNCONFIRMED)]
