"""Pins the message catalog as a table, so a dropped id, a changed exit status or a code mapped to the wrong message fails here."""

from __future__ import annotations

import re
from pathlib import Path

import stratarc
from stratarc import messages

DENIED = {"msg-1003", "msg-1118"}
CONFLICT = {"msg-1005", "msg-1126", "msg-1154"}
UNAVAILABLE = {"msg-1007", "msg-1112", "msg-1114", "msg-1115", "msg-1116", "msg-1119", "msg-1138"}
DRIFT = {"msg-1117"}
FAILURE = {"msg-1008"}

EXPECTED_IDS = {
    "msg-1001",
    "msg-1002",
    "msg-1003",
    "msg-1004",
    "msg-1005",
    "msg-1006",
    "msg-1007",
    "msg-1008",
    "msg-1009",
    "msg-1010",
    "msg-1011",
    "msg-1012",
    "msg-1013",
    "msg-1014",
    "msg-1110",
    "msg-1112",
    "msg-1114",
    "msg-1115",
    "msg-1116",
    "msg-1117",
    "msg-1118",
    "msg-1119",
    "msg-1120",
    "msg-1121",
    "msg-1122",
    "msg-1123",
    "msg-1124",
    "msg-1125",
    "msg-1126",
    "msg-1127",
    "msg-1128",
    "msg-1129",
    "msg-1130",
    "msg-1137",
    "msg-1138",
    "msg-1143",
    "msg-1145",
    "msg-1154",
}

# Codes a module raises that the catalog deliberately does not map. None today: a code a module raises is shown as a catalog message.
INTENTIONALLY_UNMAPPED: set[str] = set()

SCANNED_MODULES = ("registry.py",)

EXPECTED_CODES = {
    "source-root-missing": "msg-1110",
    "newer-schema": "msg-1112",
    "adapter-unsupported": "msg-1114",
    "drift": "msg-1117",
    "home-unwritable": "msg-1118",
    "range-invalid": "msg-1121",
    "manifest-invalid": "msg-1122",
    "manifest-unreadable": "msg-1123",
    "manifest-missing": "msg-1124",
    "adapter-unknown": "msg-1125",
    "adapter-exists": "msg-1126",
    "deprecation-reason": "msg-1127",
    "deprecation-date": "msg-1128",
    "deprecation-unknown": "msg-1129",
    "runtime-version": "msg-1130",
    "invalid-input": "msg-1137",
    "unavailable": "msg-1138",
    "invalid-name": "msg-1143",
    "invalid-path": "msg-1145",
    "conflict": "msg-1154",
}


def _raised_codes() -> dict[str, set[str]]:
    package = Path(stratarc.__file__).parent
    pattern = re.compile(r'code="([a-z]+(?:-[a-z]+)+)"')
    return {name: set(pattern.findall((package / name).read_text(encoding="utf-8"))) for name in SCANNED_MODULES}


def test_every_code_the_command_modules_raise_is_mapped_or_listed_as_unmapped():
    raised = _raised_codes()
    # The scan must find the codes, or it proves nothing.
    assert all(raised.values()), raised
    for module, codes in raised.items():
        for code in sorted(codes):
            assert code in messages.CODE_MESSAGES or code in INTENTIONALLY_UNMAPPED, f"{module} raises {code}, which has no catalog message"


def test_the_unmapped_list_holds_only_codes_that_are_raised_and_not_mapped():
    raised = set().union(*_raised_codes().values())
    for code in INTENTIONALLY_UNMAPPED:
        assert code in raised and code not in messages.CODE_MESSAGES, code


def test_the_catalog_holds_exactly_the_published_ids():
    assert set(messages.CATALOG) == EXPECTED_IDS


def test_every_message_ends_with_its_published_exit_status():
    expected = {}
    for message_id in EXPECTED_IDS:
        for status, group in ((messages.DENIED, DENIED), (messages.CONFLICT, CONFLICT), (messages.UNAVAILABLE, UNAVAILABLE), (messages.DRIFT, DRIFT), (messages.FAILURE, FAILURE)):
            if message_id in group:
                expected[message_id] = status
                break
        else:
            expected[message_id] = messages.INVALID_INPUT
    assert {message_id: message.exit for message_id, message in messages.CATALOG.items()} == expected


def test_every_module_code_maps_to_its_published_message():
    assert messages.CODE_MESSAGES == EXPECTED_CODES


def test_from_code_returns_the_message_each_code_maps_to():
    for code, message_id in EXPECTED_CODES.items():
        error = messages.from_code(code, "x")
        assert error is not None and error.id == message_id, code
        # Rendering must never raise, even when the code's text names placeholders the caller did not supply.
        assert error.problem and error.recovery, code


def test_a_message_with_unsupplied_placeholders_renders_without_raising():
    error = messages.CliError("msg-1119")
    assert "{" not in error.problem and "{" not in error.recovery


def test_the_param_fills_the_path_and_name_placeholders():
    error = messages.from_code("adapter-unknown", "no adapter named notes-cli", param="notes-cli")
    assert error is not None
    assert "notes-cli" in error.problem
