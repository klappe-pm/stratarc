"""Canonical lifecycle compatibility checks."""

import json
from pathlib import Path

import pytest

from stratarc import projects, projects_new, reconcile
from stratarc.control_plane import ControlPlane
from stratarc.project_registry import ProjectRecord, RegistryError, load_locations, load_registry


def registry(root: Path, entries: list[dict], revision: int = 1) -> None:
    file = root / "projects" / "registry.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"schemaVersion": 1, "revision": revision, "projects": entries}), encoding="utf-8")


def entry(name: str, state: str) -> dict:
    return {"id": name, "name": name.title(), "state": state, "repository": None}


def test_registry_state_wins_and_dormant_cells_survive(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    (root / "AGENTS.md").write_text("# Source\n", encoding="utf-8")
    registry(root, [entry("alpha", "active"), entry("beta", "inactive"), entry("gamma", "archived")])
    plane = root / "control-plane.md"
    plane.write_text("# control-plane\n\n| project | status | tier | template | origin |\n|---|---|---|---|---|\n| alpha | inactive | normal | base | - |\n| beta | active | normal | base | - |\n| gamma | active | normal | base | - |\n\n| option | global | alpha | beta | gamma |\n|---|---|---|---|---|\n| AGENTS.md | x | x | x | x |\n", encoding="utf-8")
    monkeypatch.setattr(reconcile, "_root_flag", root)
    cp = ControlPlane.load(plane)
    assert [cp.status(name) for name in ("alpha", "beta", "gamma")] == ["active", "inactive", "archived"]
    manifest = reconcile.project_manifest(cp, {}, records={})
    assert [manifest[name]["status"] for name in ("alpha", "beta", "gamma")] == ["active", "inactive", "archived"]
    assert reconcile.render_columns(manifest, {}) == ["global", "alpha", "beta", "gamma"]
    assert all(cp.enabled(name, "AGENTS.md") for name in ("alpha", "beta", "gamma"))


def test_invalid_present_registry_fails_closed(tmp_path):
    registry(tmp_path, [entry("alpha", "active")], revision=0)
    with pytest.raises(RegistryError):
        load_registry(tmp_path)


def test_registry_dangling_symlink_hardlink_and_large_file_refuse_legacy_fallback(tmp_path):
    root = tmp_path / "source"
    registry(root, [entry("alpha", "active")])
    file = root / "projects" / "registry.json"
    file.unlink()
    file.symlink_to(tmp_path / "missing")
    with pytest.raises(RegistryError):
        load_registry(root)
    file.unlink()
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"schemaVersion": 1, "revision": 1, "projects": []}), encoding="utf-8")
    file.hardlink_to(other)
    with pytest.raises(RegistryError):
        load_registry(root)
    file.unlink()
    file.write_bytes(b" " * 1_048_577)
    with pytest.raises(RegistryError):
        load_registry(root)


def test_stale_active_plane_cannot_deliver_after_deactivation(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    (root / "projects" / "roots").mkdir(parents=True)
    plane = root / "control-plane.md"
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| alpha | active | normal | base | - |\n", encoding="utf-8")
    registry(root, [entry("alpha", "active")])
    stale = ControlPlane.load(plane)
    registry(root, [entry("alpha", "inactive")], revision=2)
    monkeypatch.setattr(projects, "ROOT", root)
    monkeypatch.setattr(projects, "PROJECTS_SRC", root / "projects" / "roots")
    monkeypatch.setattr(projects, "_sync_project_unlocked", lambda *_: pytest.fail("delivery ran after deactivation"))
    assert "inactive" in projects.sync_project("alpha", False, stale)[0]


def test_delivery_refuses_busy_source_lock(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "projects" / "roots" / ".control-plane-write-lock").mkdir(parents=True)
    registry(root, [entry("alpha", "active")])
    monkeypatch.setattr(projects, "ROOT", root)
    with pytest.raises(projects.ProjectRefused, match="lock"):
        projects.sync_project("alpha", False)


def test_new_project_registry_write_rejects_revision_race(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "projects" / "roots").mkdir(parents=True)
    registry(root, [entry("alpha", "active")], revision=2)
    before = (root / "projects" / "registry.json").read_bytes()
    monkeypatch.setattr(projects_new, "registry_revision", lambda *_: 1)
    with pytest.raises(projects_new.NewRefused, match="changed"):
        projects_new.add_registry_project(root, "beta", None, True)
    assert (root / "projects" / "registry.json").read_bytes() == before


def test_new_project_registry_write_rechecks_identity_after_revision_capture(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "projects" / "roots").mkdir(parents=True)
    registry(root, [entry("alpha", "active")], revision=1)

    def competing_create(_root):
        registry(root, [entry("alpha", "active"), entry("beta", "active")], revision=2)
        return 2

    monkeypatch.setattr(projects_new, "registry_revision", competing_create)
    assert projects_new.add_registry_project(root, "beta", None, True) == []
    data = json.loads((root / "projects" / "registry.json").read_text(encoding="utf-8"))
    assert data["revision"] == 2
    assert [row["id"] for row in data["projects"]] == ["alpha", "beta"]


def test_new_project_registry_write_rejects_competing_repository_claim(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "projects" / "roots").mkdir(parents=True)
    registry(root, [entry("alpha", "active")], revision=1)

    def competing_create(_root):
        claimed = entry("gamma", "active")
        claimed["repository"] = "owner/shared"
        registry(root, [entry("alpha", "active"), claimed], revision=2)
        return 2

    monkeypatch.setattr(projects_new, "registry_revision", competing_create)
    with pytest.raises(projects_new.NewRefused, match="reserves"):
        projects_new.add_registry_project(root, "beta", "owner/shared", True)
    data = json.loads((root / "projects" / "registry.json").read_text(encoding="utf-8"))
    assert [row["id"] for row in data["projects"]] == ["alpha", "gamma"]


def test_external_exclusion_survives_two_registry_reconciles(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text('[layout]\nproject_config_dir = "projects/roots"\ncontrol_plane_managed = true\n', encoding="utf-8")
    (root / "AGENTS.md").write_text("# Source\n", encoding="utf-8")
    config = root / "projects" / "roots" / "third-party"
    config.mkdir(parents=True)
    (config / "AGENTS.md").write_text("# External\n", encoding="utf-8")
    registry(root, [entry("third-party", "active")])
    plane = root / "control-plane.md"
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| third-party | external | low | base | - |\n", encoding="utf-8")
    monkeypatch.setattr(reconcile, "_root_flag", root)
    for _ in range(2):
        reconcile.reconcile(check=False, snapshots=False)
        cp = ControlPlane.load(plane)
        assert cp.field("third-party", "status") == "external"
        assert cp.status("third-party") == "active"
        assert "third-party" not in cp.projects()
        assert "third-party" not in reconcile.active_checkout_paths()


def test_location_binding_rejects_symlink_and_escape(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    projects = tmp_path / "projects"
    projects.mkdir()
    records = {"alpha": ProjectRecord("alpha", "Alpha", "active", None)}
    file = root / "local" / "project-locations.json"
    file.parent.mkdir()
    file.write_text(json.dumps({"schemaVersion": 1, "checkouts": [{"projectId": "alpha", "checkoutId": "primary", "path": str(tmp_path / "outside"), "primary": True}]}), encoding="utf-8")
    with pytest.raises(RegistryError):
        load_locations(root, projects, records)
    alias = projects / "alias"
    alias.symlink_to(tmp_path / "outside")
    file.write_text(json.dumps({"schemaVersion": 1, "checkouts": [{"projectId": "alpha", "checkoutId": "primary", "path": str(alias), "primary": True}]}), encoding="utf-8")
    with pytest.raises(RegistryError):
        load_locations(root, projects, records)


def test_binding_resolves_renamed_checkout_without_status_folder_drift(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    registry(root, [entry("alpha", "inactive")])
    plane = root / "control-plane.md"
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| alpha | active | normal | base | - |\n", encoding="utf-8")
    base = tmp_path / "projects"
    checkout = base / "active" / "renamed"
    (checkout / ".git").mkdir(parents=True)
    file = root / "local" / "project-locations.json"
    file.parent.mkdir()
    file.write_text(json.dumps({"schemaVersion": 1, "checkouts": [{"projectId": "alpha", "checkoutId": "primary", "path": str(checkout), "primary": True}]}), encoding="utf-8")
    monkeypatch.setattr(projects, "ROOT", root)
    monkeypatch.setattr(projects, "PROJECTS_SRC", root / "projects" / "roots")
    monkeypatch.setenv("STRATARC_PROJECTS_DIR", str(base))
    cp = ControlPlane.load(plane)
    assert cp.find_checkout("alpha", base) == [checkout]
    assert projects.verify(cp) == []


def test_missing_explicit_binding_does_not_discover_same_named_checkout(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    registry(root, [entry("alpha", "active")])
    plane = root / "control-plane.md"
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| alpha | active | normal | base | - |\n", encoding="utf-8")
    base = tmp_path / "projects"
    (base / "alpha" / ".git").mkdir(parents=True)
    file = root / "local" / "project-locations.json"
    file.parent.mkdir()
    file.write_text(json.dumps({"schemaVersion": 1, "checkouts": [{"projectId": "alpha", "checkoutId": "primary", "path": str(base / "missing"), "primary": True}]}), encoding="utf-8")
    assert ControlPlane.load(plane).find_checkout("alpha", base) == []


def test_rootless_registry_member_does_not_enroll_for_private_delivery(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    registry(root, [entry("third-party", "active")])
    plane = root / "control-plane.md"
    plane.write_text("# control-plane\n", encoding="utf-8")
    base = tmp_path / "projects"
    (base / "third-party" / ".git").mkdir(parents=True)
    monkeypatch.setattr(reconcile, "_root_flag", root)
    monkeypatch.setenv("STRATARC_PROJECTS_DIR", str(base))
    cp = ControlPlane.load(plane)
    assert reconcile.checkout_records() == {}
    manifest = reconcile.project_manifest(cp, {}, records={})
    assert manifest == {}
    assert reconcile.render_columns(manifest, {}) == ["global"]
    monkeypatch.setattr(projects, "ROOT", root)
    monkeypatch.setattr(projects, "PROJECTS_SRC", root / "projects" / "roots")
    assert projects.resolve("third-party", cp)[0] is None
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| third-party | external | low | base | - |\n", encoding="utf-8")
    cp = ControlPlane.load(plane)
    excluded = reconcile.project_manifest(cp, {}, records={})
    assert excluded["third-party"]["status"] == "external"
    assert reconcile.render_columns(excluded, {}) == ["global"]
    assert projects.resolve("third-party", cp)[0] is None


def test_explicit_binding_wins_over_a_same_named_test_copy(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "stratarc.toml").write_text("", encoding="utf-8")
    registry(root, [entry("alpha", "active")])
    plane = root / "control-plane.md"
    plane.write_text("| project | status | tier | template | origin |\n|---|---|---|---|---|\n| alpha | active | normal | base | - |\n", encoding="utf-8")
    base = tmp_path / "projects"
    primary = base / "active" / "alpha"
    (primary / ".git").mkdir(parents=True)
    (base / "tests" / "alpha" / ".git").mkdir(parents=True)
    cp = ControlPlane.load(plane)
    assert len(cp.find_checkout("alpha", base)) == 2, "without a binding two checkouts stay ambiguous"
    file = root / "local" / "project-locations.json"
    file.parent.mkdir()
    file.write_text(json.dumps({"schemaVersion": 1, "checkouts": [{"projectId": "alpha", "checkoutId": "primary", "path": str(primary), "primary": True}]}), encoding="utf-8")
    assert ControlPlane.load(plane).find_checkout("alpha", base) == [primary.resolve()]


def test_registry_check_and_verify_accept_rootless_canonical_members_and_support_folders(tmp_path, monkeypatch):
    root = tmp_path / "source"
    config = root / "projects" / "roots"
    (config / "alpha").mkdir(parents=True)
    (config / "alpha" / "AGENTS.md").write_text("# alpha\n", encoding="utf-8")
    (root / "stratarc.toml").write_text(
        '[layout]\nproject_config_dir = "projects/roots"\ncontrol_plane = "projects/roots/control-plane.md"\ncontrol_plane_managed = false\n',
        encoding="utf-8",
    )
    registry(
        root,
        [
            {"id": "source", "name": "Source", "state": "active", "repository": "acme/source"},
            {"id": "alpha", "name": "Alpha", "state": "active", "repository": "acme/alpha"},
            {"id": "retired", "name": "Retired", "state": "archived", "repository": "acme/retired"},
            {"id": "maptapbeer", "name": "MapTap.beer", "state": "active", "repository": None},
        ],
    )
    plane = config / "control-plane.md"
    plane.write_text(
        "## projects\n\n| project | status | tier | root | origin |\n|---|---|---|---|---|\n| alpha | active | normal | [alpha/](alpha/AGENTS.md) | acme/alpha |\n",
        encoding="utf-8",
    )
    (config / "remotes.json").write_text(
        json.dumps({"source": "acme/source", "alpha": "acme/alpha", "maptapbeer": "acme/maptap-beer"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (config / "public-targets.json").write_text(json.dumps({"targets": ["acme/maptap-beer"]}) + "\n", encoding="utf-8")
    assert projects_new.registry_problems(root) == []

    base = tmp_path / "projects"
    for rel in ("active/alpha", "inactive/retired", "active/MapTap.beer/maptapbeer", "external/third-party", "vendor/worklog", "tests/Alpha"):
        (base / rel / ".git").mkdir(parents=True)
    (root / "local").mkdir(exist_ok=True)
    (root / "local" / "project-locations.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "checkouts": [
                    {"projectId": "alpha", "checkoutId": "primary", "path": str((base / "active/alpha").resolve()), "primary": True},
                    {"projectId": "maptapbeer", "checkoutId": "primary", "path": str((base / "active/MapTap.beer/maptapbeer").resolve()), "primary": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(projects, "ROOT", root)
    monkeypatch.setattr(projects, "PROJECTS_SRC", config)
    monkeypatch.setenv("STRATARC_PROJECTS_DIR", str(base))
    assert projects.verify(ControlPlane.load(plane)) == []
