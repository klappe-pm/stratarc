"""Canonical approval reviewer settings use disposable homes only."""

import json
import tomllib

import pytest

from stratarc.adapters import codex
from stratarc.permissions import load
from stratarc.project_permissions import _codex_handler


@pytest.fixture
def source(tmp_path, stratarc_home):
    root = tmp_path / "source"
    root.mkdir()
    return root


def write_policy(source, **settings):
    policy = {
        "schemaVersion": 1,
        "codexApprovalPolicy": "on-request",
        "allow": [],
        "deny": [],
        "ask": [],
        **settings,
    }
    (source / "permissions.json").write_text(json.dumps(policy))
    return policy


@pytest.mark.parametrize("reviewer", ["user", "auto_review"])
def test_reviewer_replaces_native_setting_and_sync_is_idempotent(source, tmp_path, reviewer):
    write_policy(source, codexApprovalsReviewer=reviewer)
    target = tmp_path / "codex"
    target.mkdir()
    config = target / "config.toml"
    config.write_text('approvals_reviewer = "user"\n[profiles.manual]\napprovals_reviewer = "user"\n')

    codex.sync(source, target)

    rendered = tomllib.loads(config.read_text())
    assert rendered["approval_policy"] == "on-request"
    assert rendered["approvals_reviewer"] == reviewer
    assert rendered["profiles"]["manual"]["approvals_reviewer"] == "user"
    assert codex.sync(source, target) == []


def test_omitted_reviewer_preserves_runtime_choice(source, tmp_path):
    write_policy(source)
    target = tmp_path / "codex"
    target.mkdir()
    config = target / "config.toml"
    config.write_text('approvals_reviewer = "user"\n')

    codex.sync(source, target)

    assert tomllib.loads(config.read_text())["approvals_reviewer"] == "user"


def test_dry_run_leaves_existing_reviewer_untouched(source, tmp_path):
    write_policy(source, codexApprovalsReviewer="auto_review")
    target = tmp_path / "codex"
    target.mkdir()
    config = target / "config.toml"
    original = 'approvals_reviewer = "user"\n'
    config.write_text(original)

    assert codex.sync(source, target, dry_run=True)
    assert config.read_text() == original


def test_existing_project_reviewer_cannot_shadow_shared_setting(source, tmp_path):
    policy = write_policy(source, codexApprovalsReviewer="auto_review")
    config = tmp_path / "project.toml"
    config.write_text('approvals_reviewer = "user"\n[features]\nother = true\n')
    actions = []

    _codex_handler(config, policy, False, actions)

    rendered = tomllib.loads(config.read_text())
    assert rendered["approval_policy"] == "on-request"
    assert rendered["approvals_reviewer"] == "auto_review"
    assert rendered["features"]["other"] is True
    assert len(actions) == 1


@pytest.mark.parametrize("reviewer", [None, True, 1, {}, [], "", "always", "guardian_subagent"])
def test_invalid_reviewer_is_rejected(source, reviewer):
    write_policy(source, codexApprovalsReviewer=reviewer)

    with pytest.raises(ValueError, match="codexApprovalsReviewer"):
        load(source)
