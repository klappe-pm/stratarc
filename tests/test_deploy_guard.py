"""deploy_guard: the stamp and the refusal to write an older policy over a newer one."""

from __future__ import annotations

import json
from pathlib import Path


from stratarc import deploy_guard

REPO_ROOT = Path(__file__).resolve().parent.parent



class TestStampAndVersion:
    def test_no_stamp_means_version_zero_and_no_refusal(self, tmp_path):
        assert deploy_guard.read_stamp(tmp_path) is None
        assert deploy_guard.deployed_version(tmp_path) == 0
        assert deploy_guard.refusal(tmp_path, 0) is None
        assert deploy_guard.refusal(tmp_path, 3) is None

    def test_write_then_read_round_trips(self, tmp_path):
        target = tmp_path / "runtime"
        path = deploy_guard.write_stamp(target, 4, tmp_path)
        assert path.name == deploy_guard.stamp_name() == ".stratarc-deploy.json"
        stamp = deploy_guard.read_stamp(target)
        assert stamp["policyVersion"] == 4
        assert stamp["source"] == str(tmp_path)
        assert "written" in stamp
        assert deploy_guard.deployed_version(target) == 4

    def test_older_source_is_refused_and_names_both_versions(self, tmp_path):
        deploy_guard.write_stamp(tmp_path, 5, Path("/checkouts/newer"))
        message = deploy_guard.refusal(tmp_path, 4)
        assert message is not None
        assert "version 5" in message
        assert "version 4" in message
        assert "/checkouts/newer" in message

    def test_equal_or_newer_source_is_allowed(self, tmp_path):
        deploy_guard.write_stamp(tmp_path, 5, tmp_path)
        assert deploy_guard.refusal(tmp_path, 5) is None
        assert deploy_guard.refusal(tmp_path, 6) is None

    def test_unreadable_stamp_counts_as_absent(self, tmp_path):
        (tmp_path / deploy_guard.stamp_name()).write_text("not json")
        assert deploy_guard.read_stamp(tmp_path) is None
        assert deploy_guard.refusal(tmp_path, 1) is None
        (tmp_path / deploy_guard.stamp_name()).write_text(json.dumps({"policyVersion": "9"}))
        assert deploy_guard.deployed_version(tmp_path) == 0


