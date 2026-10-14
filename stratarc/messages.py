"""The error messages the command line raises, in one place so the wording is reviewed as a set.

Each message has an id (`msg-` and a number), the exit status it ends the command with, one sentence that states the problem and one sentence that states the recovery. Placeholders in braces are filled by the caller. A message is raised as `CliError(id, name=value, ...)`; `stratarc.cli` prints it and exits with the catalog's status.
"""

from __future__ import annotations

from dataclasses import dataclass

OK = 0
FAILURE = 1
INVALID_INPUT = 2
DENIED = 3
CONFLICT = 4
UNAVAILABLE = 5
DRIFT = 6
INTERRUPTED = 130


@dataclass(frozen=True)
class Message:
    id: str
    exit: int
    problem: str
    recovery: str


_MESSAGES = (
    Message(
        "msg-1001",
        INVALID_INPUT,
        "The source root {path} does not exist or is not a directory.",
        "Pass an existing directory with --root, or create one with `stratarc init {path}`.",
    ),
    Message(
        "msg-1002",
        INVALID_INPUT,
        "The configuration cannot be used: {detail}",
        "Fix stratarc.toml in the source root; an empty file uses the defaults.",
    ),
    Message(
        "msg-1003",
        DENIED,
        "The home directory {path} is missing or cannot be written to.",
        "Make it writable, or point at another one with --home or STRATARC_HOME.",
    ),
    Message(
        "msg-1004",
        INVALID_INPUT,
        "The runtime {name} is not known.",
        "Use one of: {known}.",
    ),
    Message(
        "msg-1005",
        CONFLICT,
        "{path} exists and is not empty.",
        "Choose a path that does not exist, or empty the directory first.",
    ),
    Message(
        "msg-1006",
        INVALID_INPUT,
        "{path} exists and is not a directory.",
        "Choose a path that does not exist, or an empty directory.",
    ),
    Message(
        "msg-1007",
        UNAVAILABLE,
        "The packaged source-root template is missing from this install.",
        "Reinstall stratarc.",
    ),
    Message(
        "msg-1008",
        FAILURE,
        "The command {command} stopped unexpectedly: {detail}",
        "Run it again with --debug to see the traceback, and include it in an issue report.",
    ),
    Message(
        "msg-1009",
        INVALID_INPUT,
        "No stratarc.toml was found in {path} or any directory above it.",
        "Run `stratarc` in a terminal to set up a source root, change into your source root, or pass --root.",
    ),
    Message(
        "msg-1010",
        INVALID_INPUT,
        "{name} is not a stratarc command.{suggestion}",
        "Run `stratarc help` to list every command.",
    ),
    Message(
        "msg-1011",
        INVALID_INPUT,
        "No command was given.",
        "Run `stratarc help` to list every command, or run `stratarc` in a terminal for guided setup.",
    ),
    Message(
        "msg-1012",
        INVALID_INPUT,
        "Setup needs an interactive terminal, and this one is not.",
        "Run `stratarc setup` in a terminal, or scaffold with `stratarc init DIR` and edit its stratarc.toml.",
    ),
    Message(
        "msg-1013",
        INVALID_INPUT,
        "The remembered source root {path} no longer holds stratarc.toml.",
        "Run `stratarc setup` to choose a source root again, or pass --root.",
    ),
    Message(
        "msg-1014",
        INVALID_INPUT,
        "The arguments cannot be used: {detail}",
        "Run `{help}` to see what the command accepts.",
    ),
    # 11xx: the failures the adapter commands, the deploy gate and the files in the home can hit.
    Message(
        "msg-1110",
        INVALID_INPUT,
        "The source root cannot be read: {detail}",
        "Pass an existing directory with --root, or create one with `stratarc init`.",
    ),
    Message(
        "msg-1112",
        UNAVAILABLE,
        "A file was written by a newer stratarc and was left unchanged: {detail}",
        "Upgrade stratarc, then run the command again.",
    ),
    Message(
        "msg-1114",
        UNAVAILABLE,
        "An adapter does not support this install: {detail}",
        "Update the adapter with `stratarc adapter register`, or pin the runtime to a supported version.",
    ),
    Message(
        "msg-1115",
        UNAVAILABLE,
        "An adapter is older than the installed runtime: {detail}",
        "Update the adapter with `stratarc adapter register`; the deploy continues.",
    ),
    Message(
        "msg-1116",
        UNAVAILABLE,
        "The change log database is locked or unusable: {detail}",
        "Close the other process that uses the database and run the command again; the event is kept in the human readable log.",
    ),
    Message(
        "msg-1117",
        DRIFT,
        "The deployed files differ from what the source renders: {detail}",
        "Run `stratarc sync` to redeploy, or inspect the plan with `stratarc diff`.",
    ),
    Message(
        "msg-1118",
        DENIED,
        "The home directory cannot be created or written to: {detail}",
        "Make it writable, or point at another one with --home or STRATARC_HOME.",
    ),
    Message(
        "msg-1119",
        UNAVAILABLE,
        "The backup of {path} is missing from the home backups.",
        "Restore the file by hand, or run `stratarc sync` again to redeploy it.",
    ),
    Message(
        "msg-1120",
        INVALID_INPUT,
        "The project {name} was not delivered because {path} is not valid JSON ({detail}).",
        "Fix or remove the file and run the command again; nothing was delivered to this project.",
    ),
    Message(
        "msg-1121",
        INVALID_INPUT,
        "A version range is not valid: {detail}",
        "Use comma separated comparators such as >=0.4,<0.9, or *.",
    ),
    Message(
        "msg-1122",
        INVALID_INPUT,
        "An adapter manifest is not valid: {detail}",
        "Fix the fields the message lists; the adapter manifest schema describes each one.",
    ),
    Message(
        "msg-1123",
        INVALID_INPUT,
        "An adapter manifest cannot be read: {detail}",
        "Fix or replace the file, then register the adapter again.",
    ),
    Message(
        "msg-1124",
        INVALID_INPUT,
        "No adapter manifest was found: {detail}",
        "Pass a manifest.json file, a directory that holds one, or an installed package that ships one.",
    ),
    Message(
        "msg-1125",
        INVALID_INPUT,
        "The adapter is not known: {detail}",
        "List the registered adapters with `stratarc adapter list`.",
    ),
    Message(
        "msg-1126",
        CONFLICT,
        "The adapter already exists: {detail}",
        "Choose another name, or pass --replace to register a manifest again.",
    ),
    Message(
        "msg-1127",
        INVALID_INPUT,
        "A deprecation has no reason: {detail}",
        "Pass --reason with the explanation users should read.",
    ),
    Message(
        "msg-1128",
        INVALID_INPUT,
        "The end date of a deprecation is not a date: {detail}",
        "Pass --end-date as YYYY-MM-DD.",
    ),
    Message(
        "msg-1129",
        INVALID_INPUT,
        "The adapter is not deprecated: {detail}",
        "Check the name, or mark the adapter first with `stratarc adapter deprecate`.",
    ),
    Message(
        "msg-1130",
        INVALID_INPUT,
        "A runtime version is not in the form RUNTIME=VERSION: {detail}",
        "Pass it as, for example, --runtime-version codex=0.9.1.",
    ),
    Message(
        "msg-1137",
        INVALID_INPUT,
        "The command was given input it cannot use: {detail}",
        "Check the arguments against `stratarc COMMAND --help`, then run it again.",
    ),
    Message(
        "msg-1138",
        UNAVAILABLE,
        "The data the command needs is not available: {detail}",
        "Run the command that produces it first, or check that the path exists and can be read.",
    ),
    Message(
        "msg-1143",
        INVALID_INPUT,
        "The name cannot be used: {detail}",
        "Use lowercase letters, digits and hyphens, starting with a letter.",
    ),
    Message(
        "msg-1145",
        INVALID_INPUT,
        "The path cannot be used: {detail}",
        "Choose a path the command allows, which `stratarc COMMAND --help` describes.",
    ),
    Message(
        "msg-1154",
        CONFLICT,
        "The change conflicts with what already exists: {detail}",
        "Resolve the conflict, or choose another name or path, then run the command again.",
    ),
)

CATALOG: dict[str, Message] = {message.id: message for message in _MESSAGES}

# The stable string codes the config, provider, adapter, log and verify modules put in their error bodies, and the catalog message each one is shown as. A module keeps raising its own code and wording; the command line resolves the code here and shows the catalog message with the module's text as {detail}. A code absent from this table is shown as the module wrote it.
CODE_MESSAGES: dict[str, str] = {
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


class CliError(Exception):
    """A failure the command line reports by catalog id, then exits with that message's status."""

    def __init__(self, message_id: str, *, param: str | None = None, **values: object) -> None:
        self.message = CATALOG[message_id]
        self.param = param
        self.values = values
        super().__init__(self.problem)

    @property
    def id(self) -> str:
        return self.message.id

    @property
    def exit(self) -> int:
        return self.message.exit

    @property
    def problem(self) -> str:
        return self.message.problem.format_map(_Values(self.values))

    @property
    def recovery(self) -> str:
        return self.message.recovery.format_map(_Values(self.values))


class _Values(dict):
    """Format values where a placeholder the caller did not supply reads as "it" rather than raising."""

    def __missing__(self, key: str) -> str:
        return "it"


def from_code(code: str, detail: object, *, param: str | None = None) -> CliError | None:
    """The catalog error for a module's string code, with the module's own text as the detail, or None when the code has no entry.

    The param, when given, also fills the {path} and {name} placeholders some messages carry, so a code raised with only a detail still renders a complete sentence.
    """
    message_id = CODE_MESSAGES.get(code)
    if message_id is None:
        return None
    values: dict[str, object] = {"detail": detail}
    if param is not None:
        values["path"] = param
        values["name"] = param
    return CliError(message_id, param=param, **values)
