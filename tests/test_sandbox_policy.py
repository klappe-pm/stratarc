"""Exercise sandbox removal through runtime sync and the project sweep."""

import json
import tomllib

import pytest

from stratarc import permissions, project_permissions
from stratarc.adapters import claude, codex, gemini


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


@pytest.fixture
def source(source_root, stratarc_home):
    write_json(source_root / "permissions.json", {
        "schemaVersion": 1, "sandboxEnabled": False,
        "codexApprovalPolicy": "never",
        "allow": [], "deny": ["Read(**/.env)", "Bash(sudo *)"], "ask": [],
    })
    return source_root


@pytest.mark.parametrize("proxy", [
    "[features]\nnetwork_proxy = true\nother = true\n",
    '[features.network_proxy]\nenabled = true\n[features.network_proxy.domains]\n"github.com" = "allow"\n',
])
@pytest.mark.parametrize("marked", [False, True])
def test_codex_removes_old_profile_and_proxy(source, tmp_path, proxy, marked):
    target = tmp_path / "codex"
    target.mkdir()
    old_profile = '[permissions.stratarc]\nextends = ":workspace"\n[permissions.stratarc.network]\nenabled = true\n'
    if marked:
        old_profile = "# BEGIN stratarc permissions, generated from permissions.json\n" + old_profile + "# END stratarc permissions\n"
    before = (
        'model = "fixture"\ndefault_permissions = "stratarc"\n'
        + proxy + old_profile
        + '[permissions.custom]\nextends = ":read-only"\n'
        + '[mcp_servers.codegenome]\nurl = "https://api.codegenomeproject.org/mcp"\n'
    )
    config_path = target / "config.toml"
    config_path.write_text(before)
    assert codex.sync(source, target, dry_run=True)
    assert config_path.read_text() == before

    codex.sync(source, target)

    config = tomllib.loads(config_path.read_text())
    assert config.get("sandbox_mode") == "danger-full-access"
    assert "default_permissions" not in config
    assert "stratarc" not in config.get("permissions", {})
    proxy = config["features"]["network_proxy"]
    assert (proxy["enabled"] if isinstance(proxy, dict) else proxy) is False
    assert config["model"] == "fixture"
    assert config["permissions"]["custom"]["extends"] == ":read-only"
    assert config["mcp_servers"]["codegenome"]["url"].startswith("https://api.codegenomeproject.org/")
    assert 'decision="forbidden"' in (target / "rules/stratarc.rules").read_text()
    assert codex.sync(source, target) == []


def test_claude_policy_overrides_old_component_and_runtime_sandbox(source, tmp_path):
    target = tmp_path / "claude"
    write_json(source / "components.json", {
        "runtime_settings": {"claude": {"settings": {"sandbox": {"enabled": True}}}},
    })
    write_json(target / "settings.json", {"sandbox": {"enabled": True}, "theme": "light"})

    claude.sync(source, target)

    config = json.loads((target / "settings.json").read_text())
    assert config["sandbox"]["enabled"] is False
    assert config["theme"] == "light"
    assert "Read(**/.env)" in config["permissions"]["deny"]
    assert claude.sync(source, target) == []


def test_gemini_removes_existing_docker_sandbox(source, tmp_path):
    target = tmp_path / "gemini"
    write_json(target / "settings.json", {"tools": {"sandbox": "docker", "other": True}})

    gemini.sync(source, target)

    assert json.loads((target / "settings.json").read_text())["tools"] == {"sandbox": False, "other": True}
    assert gemini.sync(source, target) == []


@pytest.mark.parametrize("scoped", [False, True])
def test_project_sweep_cannot_restore_sandbox(source, tmp_path, scoped):
    root = tmp_path.resolve() / "projects"
    project = root / "sample"
    (project / ".git").mkdir(parents=True)
    if scoped:
        write_json(source / "projects-root/sample/permissions.json", {
            "schemaVersion": 1, "defaultMode": "default",
            "allow": [], "deny": [], "ask": [],
            "projectScope": {"root": str(project), "worktrees": []},
        })
    write_json(project / ".claude/settings.json", {"sandbox": {"enabled": True}, "hooks": {}})
    write_json(project / ".gemini/settings.json", {"tools": {"sandbox": "docker", "other": True}})
    config_path = project / ".codex/config.toml"
    config_path.parent.mkdir()
    config_path.write_text(
        'default_permissions = "sample"\nsandbox_mode = "workspace-write"\n'
        '[permissions.sample]\nextends = ":read-only"\n'
        '[features.network_proxy]\nenabled = true\n'
        '[mcp_servers.fixture]\ncommand = "fixture"\n'
    )
    before = {path: path.read_bytes() for path in project.rglob("*") if path.is_file()}
    assert project_permissions.sweep(source, root, dry_run=True)
    assert all(path.read_bytes() == value for path, value in before.items())

    project_permissions.sweep(source, root)

    assert json.loads((project / ".claude/settings.json").read_text())["sandbox"]["enabled"] is False
    gemini_config = json.loads((project / ".gemini/settings.json").read_text())
    assert gemini_config["tools"]["sandbox"] is False
    assert gemini_config["tools"]["other"] is True
    codex_config = tomllib.loads(config_path.read_text())
    assert codex_config.get("sandbox_mode") == "danger-full-access"
    assert "default_permissions" not in codex_config
    assert codex_config["features"]["network_proxy"]["enabled"] is False
    assert codex_config["mcp_servers"]["fixture"]["command"] == "fixture"
    assert project_permissions.sweep(source, root) == []


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("existing_reviewer", [None, "user"])
def test_disabled_project_sandbox_respects_explicit_codex_reviewer(tmp_path, scoped, existing_reviewer):
    policy = {
        "sandboxEnabled": False,
        "codexApprovalPolicy": "on-request",
        "codexApprovalsReviewer": "auto_review",
    }
    before = 'approval_policy = "never"\nsandbox_mode = "workspace-write"\n'
    if existing_reviewer is not None:
        before += f'approvals_reviewer = "{existing_reviewer}"\n'
    before += '[mcp_servers.fixture]\ncommand = "fixture"\n'
    if scoped:
        rendered = project_permissions._scoped_codex("sample", before, policy, tmp_path / "sample")
    else:
        config_path = tmp_path / "config.toml"
        config_path.write_text(before)
        project_permissions._codex_handler(config_path, policy, True, [])
        assert config_path.read_text() == before
        project_permissions._codex_handler(config_path, policy, False, [])
        rendered = config_path.read_text()
    config = tomllib.loads(rendered)
    assert config["approvals_reviewer"] == "auto_review"
    assert config["approval_policy"] == "on-request"
    assert config["sandbox_mode"] == "danger-full-access"
    assert config["mcp_servers"]["fixture"]["command"] == "fixture"


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("reviewer,existing_reviewer,expected", [
    ("auto_review", "user", "auto_review"),
    ("user", "auto_review", "user"),
    (None, "user", "user"),
    (None, "auto_review", "auto_review"),
])
def test_disabled_sandbox_sweep_preserves_reviewer_policy(source, tmp_path, scoped, reviewer, existing_reviewer, expected):
    policy_path = source / "permissions.json"
    shared = json.loads(policy_path.read_text())
    shared["codexApprovalPolicy"] = "on-request"
    if scoped or reviewer is not None:
        shared["codexApprovalsReviewer"] = "auto_review" if scoped else reviewer
    write_json(policy_path, shared)
    root = tmp_path.resolve() / "projects"
    project = root / "sample"
    (project / ".git").mkdir(parents=True)
    if scoped:
        policy = {
            "schemaVersion": 1, "defaultMode": "default",
            "allow": [], "deny": [], "ask": [],
            "codexApprovalPolicy": "on-request",
            "projectScope": {"root": str(project), "worktrees": []},
        }
        if reviewer is not None:
            policy["codexApprovalsReviewer"] = reviewer
        write_json(source / "projects-root/sample/permissions.json", policy)
    config_path = project / ".codex/config.toml"
    config_path.parent.mkdir()
    before = f'approval_policy = "never"\napprovals_reviewer = "{existing_reviewer}"\n'
    config_path.write_text(before)
    project_permissions.sweep(source, root, dry_run=True)
    assert config_path.read_text() == before
    project_permissions.sweep(source, root)
    config = tomllib.loads(config_path.read_text())
    assert config["approvals_reviewer"] == expected
    assert config["approval_policy"] == "on-request"
    assert config["sandbox_mode"] == "danger-full-access"
    assert project_permissions.sweep(source, root) == []


@pytest.mark.parametrize("value", [None, False, "always"])
def test_codex_reviewer_requires_a_supported_value(source, value):
    policy_path = source / "permissions.json"
    policy = json.loads(policy_path.read_text())
    policy["codexApprovalsReviewer"] = value
    write_json(policy_path, policy)
    with pytest.raises(ValueError, match="codexApprovalsReviewer"):
        permissions.load(source)


@pytest.mark.parametrize("value", [None, "false", 0, [], {}])
def test_sandbox_switch_requires_boolean(source, value):
    policy_path = source / "permissions.json"
    policy = json.loads(policy_path.read_text())
    policy["sandboxEnabled"] = value
    write_json(policy_path, policy)
    with pytest.raises(ValueError, match="sandboxEnabled"):
        permissions.load(source)
