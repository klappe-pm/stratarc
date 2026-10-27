"""Command line entry point for stratarc.

Every engine command calls the `main(argv)` of the module that owns it, after the global flags have been turned into the environment variables `stratarc.paths` reads. The flags are applied for the length of one command and undone afterwards, so a call from a test or another program leaves the process as it found it.

Exit statuses: 0 ok, 1 failure, 2 invalid input, 3 denied, 4 conflict, 5 unavailable, 6 drift, 130 interrupted. The constants live in `stratarc.messages`.
"""

from __future__ import annotations

import time

_LOADED = time.perf_counter()

import argparse
import contextlib
import io
import json
import os
import re
import sys
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path

from stratarc import __version__, messages, paths
from stratarc.messages import DRIFT, FAILURE, INTERRUPTED, UNAVAILABLE, CliError
from stratarc.setup import TEMPLATE
DOCS = "https://github.com/klappe-pm/stratarc/blob/main/docs"

# Commands that forward everything after their name to the module's own parser.
PASSTHROUGH = {
    "validate": "check a source root against the schemas and the engine's rules",
    "projects": "deliver projects-root/ into the managed project checkouts",
    "gen-rules-digest": "render or check the rules digest in instruction files",
    "components": "validate components.json and list what it declares",
    "drift": "report where checkouts differ from what the control plane delivers",
}

# Resources whose module prints its own result and error envelope. The command line forwards the arguments, adds --json when the global flag is set, resolves the module's string error code to a catalog message and maps the exit status.
RESOURCES = {
    "adapter": "manage the translators from the source to a runtime",
}

# The verbs of each resource that write to the home, so the home is checked first. A dry run writes nothing and is not checked.
WRITING_VERBS = {
    "adapter": {"register", "add", "remove", "deprecate"},
}

EXIT_NAMES = {
    1: "failure",
    2: "invalid-input",
    3: "denied",
    4: "conflict",
    5: "unavailable",
    6: "drift",
    INTERRUPTED: "interrupted",
}


class _UsageError(Exception):
    """A command line the parser cannot use, raised in place of argparse's print and exit so `--json` still gets one envelope."""

    def __init__(self, parser: argparse.ArgumentParser, message: str) -> None:
        super().__init__(message)
        self.parser = parser
        self.message = message


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # type: ignore[override]
        raise _UsageError(self, message)


# ----- the global flags -----


def _global_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    group = parser.add_argument_group("global options")
    group.add_argument("--root", metavar="PATH", help="the source root (sets STRATARC_SOURCE)")
    group.add_argument("--home", metavar="PATH", help="the home directory the runtime targets hang under (sets STRATARC_HOME)")
    group.add_argument("--projects-root", metavar="PATH", help="the directory that holds project checkouts (sets STRATARC_PROJECTS_DIR)")
    group.add_argument("--json", action="store_true", help="print one JSON envelope instead of text")
    group.add_argument("--debug", action="store_true", help="print a traceback when a command stops unexpectedly")
    return parser


def _flag_environment(flags: argparse.Namespace) -> dict[str, str]:
    updates: dict[str, str] = {}
    if flags.root:
        updates[paths.SOURCE_VARIABLE] = str(Path(flags.root).expanduser().resolve())
    if flags.home:
        updates[paths.HOME_VARIABLE] = str(Path(flags.home).expanduser().resolve())
    if flags.projects_root:
        updates[paths.PROJECTS_VARIABLE] = str(Path(flags.projects_root).expanduser())
    return updates


@contextlib.contextmanager
def _environment(updates: dict[str, str]) -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# ----- the checks every engine command shares -----


def _require_source_root() -> Path:
    """The resolved source root, after checking that it exists and its stratarc.toml parses."""
    from stratarc.config import ConfigError, load_config

    root, origin = paths.discover_source()
    if not root.is_dir():
        raise CliError("msg-1001", param="root", path=root)
    # Falling back to a directory with no stratarc.toml would treat any directory as a source root and write a control plane into it.
    if origin == paths.ORIGIN_CURRENT and not (root / paths.CONFIG_NAME).is_file():
        raise CliError("msg-1009", param="root", path=root)
    try:
        load_config(root)
    except ConfigError as error:
        raise CliError("msg-1002", param=paths.CONFIG_NAME, detail=error) from error
    return root


def _require_writable_home() -> None:
    home = paths.home()
    if not (home.is_dir() and os.access(home, os.W_OK | os.X_OK)):
        raise CliError("msg-1003", param="home", path=home)


def _require_known_runtime(name: str | None) -> None:
    if not name:
        return
    from stratarc.adapters._common import runtime_registry

    known = sorted(runtime_registry())
    if name not in known:
        raise CliError("msg-1004", param="only", name=name, known=", ".join(known))


# ----- commands -----


def cmd_init(args: argparse.Namespace) -> tuple[int, dict]:
    from stratarc import setup

    target = Path(args.target)
    count = setup.scaffold(target)
    text = "\n".join(
        [
            f"stratarc init: wrote {count} files to {target}",
            "next:",
            f"  set enabled = true for your runtimes in {target / paths.CONFIG_NAME}",
            f"  stratarc --root {target} reconcile",
            f"  stratarc --root {target} diff",
            f"  stratarc --root {target} sync",
            "or run `stratarc setup` to be walked through it and have the root remembered.",
        ]
    )
    return 0, {"target": str(target), "files": count, "text": text}


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cmd_setup(args: argparse.Namespace) -> tuple[int, dict]:
    from stratarc import setup

    if args.global_flags.json or not _interactive():
        raise CliError("msg-1012")
    return setup.run(), {}


def cmd_help(args: argparse.Namespace) -> tuple[int, dict]:
    topic = args.topic
    if topic is None:
        build_parser().print_help()
        return 0, {}
    if topic in PASSTHROUGH or topic in RESOURCES:
        with contextlib.suppress(SystemExit):
            main([topic, "--help"])
        return 0, {}
    parser = _subparsers(build_parser()).get(topic)
    if parser is None:
        raise _unknown_command(topic)
    parser.print_help()
    return 0, {}


def _home_start(flags: argparse.Namespace) -> tuple[int, dict]:
    """A bare `stratarc`: setup when no source root is found in a terminal, a status summary when one is, help otherwise."""
    from stratarc import setup

    if flags.json:
        raise CliError("msg-1011")
    if not _interactive():
        build_parser().print_help()
        return 0, {}
    root, origin = paths.discover_source()
    if origin != paths.ORIGIN_CURRENT or (root / paths.CONFIG_NAME).is_file():
        # A root named by --root or STRATARC_SOURCE is used as given, the way every engine command uses it, so a stale one never sends the user back into setup.
        if not root.is_dir():
            raise CliError("msg-1001", param="root", path=root)
        return 0, {"text": setup.status(root, "--root" if flags.root else origin)}
    return setup.run(), {}


def cmd_doctor(args: argparse.Namespace) -> tuple[int, dict]:
    from stratarc import doctor

    started_ms = (time.perf_counter() - _LOADED) * 1000
    data, problems = doctor.collect(root_flag=bool(args.global_flags.root), started_ms=started_ms)
    sections = [doctor.render(data, problems)]
    if args.permissions:
        data["permissions"] = doctor.permissions_table()
        sections.append(doctor.render_permissions(data["permissions"]))
    if args.clean:
        from stratarc.home_layout import ToolError

        try:
            data["clean"] = doctor.clean(args.yes)
        except ToolError as error:
            raise CliError("msg-1118", param="home", detail=error.message) from error
        sections.append(doctor.render_clean(data["clean"]))
    if args.report:
        from stratarc.home_layout import ToolError

        try:
            report = doctor.write_report(data, problems)
        except ToolError as error:
            raise CliError("msg-1118", param="home", detail=error.message) from error
        data["report"] = str(report)
        sections.append(f"report: {data['report']}")
    data["text"] = "\n".join(sections)
    if problems:
        data["problems"] = [{"code": p.id, "message": p.problem, "hint": p.recovery} for p in problems]
        raise _Reported(problems[0], data)
    return 0, data


class _Reported(Exception):
    """A failure that still carries data to print: the error, then the report."""

    def __init__(self, error: CliError, data: dict) -> None:
        super().__init__(error.problem)
        self.error = error
        self.data = data


def _engine_main(command: str) -> Callable[[list[str] | None], int]:
    if command in ("sync", "check", "diff", "prune"):
        from stratarc import sync

        return sync.main
    if command == "reconcile":
        from stratarc import reconcile

        return reconcile.main
    if command == "validate":
        from stratarc import validate

        return validate.main
    if command == "projects":
        from stratarc import projects

        return projects.main
    if command == "gen-rules-digest":
        from stratarc import gen_rules_digest

        return gen_rules_digest.main
    if command == "drift":
        from stratarc import drift

        return drift.main
    from stratarc import components

    return components.main


def _check_passthrough_usage(command: str, argv: list[str]) -> None:
    """Parse a forwarded command line with the module's own parser, so an argument it does not take is reported before the source root is looked for."""
    import importlib

    if any(flag in argv for flag in ("-h", "--help")):
        return
    module = importlib.import_module(f"stratarc.{command.replace('-', '_')}")
    parser = module.build_parser()

    def error(message: str):
        raise _UsageError(parser, message)

    # argparse reports a missing required argument before an unknown one, so a first pass with nothing required finds the unknown one.
    loose = module.build_parser()
    loose.error = error  # type: ignore[method-assign]
    for action in loose._actions:
        action.required = False
    for group in loose._mutually_exclusive_groups:
        group.required = False
    _, extras = loose.parse_known_args(argv)
    if extras:
        error(f"unrecognized arguments: {' '.join(extras)}")
    parser.error = error  # type: ignore[method-assign]
    parser.parse_args(argv)


def _sync_family_argv(args: argparse.Namespace) -> list[str]:
    command = args.command
    argv: list[str] = {"check": ["--check"], "diff": ["--diff"], "prune": ["--prune"]}.get(command, [])
    if getattr(args, "list", False):
        argv.append("--list")
    if getattr(args, "dry_run", False):
        argv.append("--dry-run")
    if getattr(args, "verify", False):
        argv.append("--verify")
    if getattr(args, "rollback_on_drift", False):
        argv.append("--rollback-on-drift")
    if args.only:
        argv += ["--only", args.only]
    return argv


def _reports_drift(command: str, argv: list[str]) -> bool:
    """True when this command's exit 1 means the deployed state differs, not that it failed."""
    if command == "check":
        return True
    if command == "reconcile":
        return "--check" in argv
    if command == "projects":
        return "--check" in argv or "--verify" in argv
    if command == "gen-rules-digest":
        return "--check" in argv
    return command == "drift"


def cmd_engine(args: argparse.Namespace, rest: list[str]) -> tuple[int, dict]:
    command = args.command
    if command in PASSTHROUGH:
        argv = rest
    elif command == "reconcile":
        argv = (["--check"] if args.check else []) + (["--root", str(paths.source_root())] if args.global_flags.root else [])
    else:
        argv = _sync_family_argv(args)

    if not any(flag in rest for flag in ("-h", "--help")):
        _require_source_root()
        if command in ("sync", "check", "diff", "prune"):
            _require_known_runtime(args.only)
        writes = (command == "sync" and not args.dry_run and not args.list) or (command == "prune" and not args.dry_run)
        if writes:
            _require_writable_home()

    entry = _engine_main(command)
    if args.global_flags.json:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            raw = _call(entry, argv)
        data = {"command": command, "stdout": out.getvalue(), "stderr": err.getvalue()}
    else:
        raw = _call(entry, argv)
        data = {"command": command}
    code = DRIFT if raw == 1 and _reports_drift(command, argv) else raw
    if code not in (0, *EXIT_NAMES):
        code = FAILURE
    # The status stratarc exits with, after the drift and failure mapping, so it agrees with the error message and the process status.
    data["exit"] = code
    return code, data


_ERROR_LINE = re.compile(r"^error (?P<code>[\w-]+):?\s+(?P<message>.*)$")


def _resource_main(resource: str) -> Callable[[list[str] | None], int]:
    from stratarc import registry

    return registry.main


def _map_error_body(body: dict) -> dict:
    """The error body of a module's envelope with its string code resolved to the catalog message."""
    mapped = messages.from_code(str(body.get("code", "")), body.get("message", ""), param=body.get("param"))
    if mapped is None:
        return body
    return _error_body(mapped)


def _map_envelope(text: str) -> str:
    try:
        body = json.loads(text)
    except ValueError:
        return text
    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return text
    body["error"] = _map_error_body(body["error"])
    return json.dumps(body, indent=2) + "\n"


def _map_error_text(text: str) -> str:
    """Standard error of a module with a leading `error <code>  <message>` line shown as the catalog message."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        found = _ERROR_LINE.match(line)
        if found is None:
            continue
        mapped = messages.from_code(found.group("code"), found.group("message"))
        if mapped is None:
            return text
        # The module's hint line, when it wrote one, is replaced by the catalog's recovery.
        rest = lines[index + 2 :] if index + 1 < len(lines) and lines[index + 1].startswith("  ") else lines[index + 1 :]
        return "\n".join([*lines[:index], f"error {mapped.id}  {mapped.problem}", f"  {mapped.recovery}", *rest]) + "\n"
    return text


def _print_json_result(args: argparse.Namespace, code: int, text: str, err: str) -> int:
    """Print exactly one envelope: the module's own, with the error resolved to the catalog, or one built from what the module wrote when it printed none (a usage error, help)."""
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    if isinstance(body, dict) and "ok" in body:
        sys.stdout.write(_map_envelope(text))
        if err:
            sys.stderr.write(err)
        return code
    lines = err.strip().splitlines()
    error = None
    if code:
        error = {"code": EXIT_NAMES.get(code, "failure"), "message": lines[-1] if lines else f"stratarc {args.command} exited {code}", "param": None, "hint": None}
    print(_envelope(code == 0, {"stdout": text} if text else None, error))
    return code


def cmd_resource(args: argparse.Namespace, rest: list[str]) -> int:
    """Forward a resource command to its module and print the result with catalog wording and the mapped status."""
    resource = args.command
    asking_for_help = any(flag in rest for flag in ("-h", "--help"))
    verb = next((token for token in rest if not token.startswith("-")), None)
    if not asking_for_help and verb in WRITING_VERBS.get(resource, set()) and "--dry-run" not in rest:
        _require_writable_home()
    argv = list(rest) + (["--json"] if args.global_flags.json and not asking_for_help else [])
    entry = _resource_main(resource)
    # JSON mode captures the envelope and standard error; text mode captures standard error only, so an interactive prompt on standard output still reaches the terminal.
    captured = io.StringIO()
    captured_err = io.StringIO()
    if args.global_flags.json:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured_err):
            raw = _call(entry, argv)
    else:
        with contextlib.redirect_stderr(captured):
            raw = _call(entry, argv)
    code = raw if raw in (0, *EXIT_NAMES) else FAILURE
    text = captured.getvalue()
    if args.global_flags.json:
        return _print_json_result(args, code, text, captured_err.getvalue())
    if text:
        sys.stderr.write(_map_error_text(text))
    return code


def _call(entry: Callable[[list[str] | None], int], argv: list[str]) -> int:
    """Run a module's main; an argparse exit inside it becomes its return value."""
    try:
        result = entry(argv)
    except SystemExit as stop:
        if stop.code is None:
            return 0
        return stop.code if isinstance(stop.code, int) else FAILURE
    return result or 0


# ----- the parser -----


EPILOG = f"""start here:
  stratarc              guided setup the first time; afterwards, where your source root is and what to run
  stratarc help CMD     explain one command, with examples
  stratarc diff         preview what a deploy would change
  stratarc sync         deploy the source into every enabled runtime

Global options are accepted before or after the command.
Exit statuses: 0 ok, 1 failure, 2 invalid input, 3 denied, 4 conflict, 5 unavailable, 6 drift, 130 interrupted.
Docs: {DOCS}/reference/cli.md"""

GLOBAL_NOTE = "Global options such as --root, --home and --json also work here; `stratarc help` lists them."

EXAMPLES = {
    "help": ["stratarc help", "stratarc help sync"],
    "setup": ["stratarc setup"],
    "init": ["stratarc init ~/stratarc-source"],
    "doctor": ["stratarc doctor", "stratarc doctor --permissions", "stratarc doctor --clean --yes"],
    "sync": ["stratarc sync", "stratarc sync --dry-run", "stratarc sync --only claude", "stratarc sync --verify --rollback-on-drift"],
    "check": ["stratarc check", "stratarc check --only codex"],
    "diff": ["stratarc diff", "stratarc diff --only claude"],
    "prune": ["stratarc prune --dry-run", "stratarc prune --only gemini"],
    "reconcile": ["stratarc reconcile", "stratarc reconcile --check"],
}


def _add_command(sub, name: str, help: str):
    epilog = "examples:\n" + "\n".join(f"  {line}" for line in EXAMPLES[name]) + "\n\n" + GLOBAL_NOTE
    return sub.add_parser(name, help=help, description=help[0].upper() + help[1:] + ".", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def command_names() -> list[str]:
    return list(_subparsers(build_parser()))


def _unknown_command(name: str) -> CliError:
    import difflib

    close = difflib.get_close_matches(name, command_names(), n=1, cutoff=0.6)
    suggestion = f" Did you mean `stratarc {close[0]}`?" if close else ""
    return CliError("msg-1010", param="command", name=name, suggestion=suggestion)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="stratarc",
        description="One agent configuration source, rendered into every agent runtime.",
        parents=[_global_parser()],
        allow_abbrev=False,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"stratarc {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = _add_command(sub, "help", "explain one command, or list them all")
    p.add_argument("topic", nargs="?", metavar="COMMAND", help="the command to explain")
    p.set_defaults(func=cmd_help)

    p = _add_command(sub, "setup", "walk through creating a source root, choosing runtimes and the first deploy")
    p.set_defaults(func=cmd_setup)

    p = _add_command(sub, "init", "scaffold a new source root into TARGET")
    p.add_argument("target", help="directory to create; must be absent or empty")
    p.set_defaults(func=cmd_init)

    p = _add_command(sub, "doctor", "report the health of the install, the home and the source root")
    p.add_argument("--permissions", action="store_true", help="also print what each command reads and writes")
    p.add_argument("--clean", action="store_true", help="also list the old backups and cache the home can shed")
    p.add_argument("--yes", action="store_true", help="with --clean, remove what it lists")
    p.add_argument("--report", action="store_true", help="also write a redacted bundle for an issue report under state/debug")
    p.set_defaults(func=cmd_doctor)

    p = _add_command(sub, "sync", "render the source into every enabled runtime and managed project")
    p.add_argument("--verify", action="store_true", help="after the write, verify the change against what is deployed; exit 6 on drift")
    p.add_argument("--rollback-on-drift", action="store_true", help="when verification finds drift, restore the runtime files from the home backups (implies --verify)")
    p.add_argument("--only", metavar="RUNTIME", help="sync one runtime and skip project delivery")
    p.add_argument("--dry-run", action="store_true", help="print what a sync would change and write nothing")
    p.add_argument("--list", action="store_true", help="list the runtimes and whether each target exists")

    p = _add_command(sub, "check", "report what is out of date, write nothing, exit 6 on drift")
    p.add_argument("--only", metavar="RUNTIME", help="check one runtime")

    p = _add_command(sub, "diff", "print what a sync would change, write nothing, exit 0")
    p.add_argument("--only", metavar="RUNTIME", help="diff one runtime")

    p = _add_command(sub, "prune", "delete files a runtime holds that the source no longer produces")
    p.add_argument("--only", metavar="RUNTIME", help="prune one runtime")
    p.add_argument("--dry-run", action="store_true", help="list what would be deleted")

    p = _add_command(sub, "reconcile", "refresh control-plane.md from the source tree")
    p.add_argument("--check", action="store_true", help="report what is stale, write nothing, exit 6 if any")

    for name, text in {**PASSTHROUGH, **RESOURCES}.items():
        sub.add_parser(name, help=text, add_help=False)
    return parser


# ----- output -----


def _print_error(error: CliError) -> None:
    print(f"error {error.id}  {error.problem}", file=sys.stderr)
    print(f"  {error.recovery}", file=sys.stderr)
    print(f"  more: {DOCS}/reference/generated/errors.md#{error.id}", file=sys.stderr)


def _envelope(ok: bool, data: dict | None, error: dict | None) -> str:
    return json.dumps({"ok": ok, "data": data, "error": error}, indent=2)


def _error_body(error: CliError) -> dict:
    return {"code": error.id, "message": error.problem, "param": error.param, "hint": error.recovery}


def _finish(args: argparse.Namespace, flags: argparse.Namespace, code: int, data: dict, error: CliError | None = None) -> int:
    text = data.pop("text", None)
    if flags.json:
        body = None
        if error is not None:
            body = _error_body(error)
        elif code:
            stderr = str(data.get("stderr", "")).strip().splitlines()
            body = {
                "code": EXIT_NAMES.get(code, "failure"),
                "message": stderr[-1] if stderr else f"stratarc {args.command} exited {code}",
                "param": None,
                "hint": None,
            }
        print(_envelope(code == 0, data or None, body))
        return code
    if error is not None:
        if text:
            print(text)
        _print_error(error)
    elif text:
        print(text)
    return code


# ----- entry -----


def _parse(tokens: list[str]) -> argparse.Namespace:
    """Parse a built-in command; an argument the command does not take is reported against that command's usage, not the top-level one."""
    parser = build_parser()
    args, extras = parser.parse_known_args(tokens)
    if extras:
        target = _subparsers(parser).get(args.command or "", parser)
        target.error(f"unrecognized arguments: {' '.join(extras)}")
    return args


def _finish_usage(args: argparse.Namespace, flags: argparse.Namespace, usage: _UsageError) -> int:
    if not flags.json:
        usage.parser.print_usage(sys.stderr)
    name = args.command if args.command and not args.command.startswith("-") else None
    guide = f"stratarc help {name}" if name else "stratarc help"
    return _finish(args, flags, 2, {}, CliError("msg-1014", param=name or "option", detail=usage.message, help=guide))


def main(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    flags, rest = _global_parser().parse_known_args(tokens)

    command = rest[0] if rest else None
    args = argparse.Namespace(command=command, global_flags=flags)
    try:
        if command in PASSTHROUGH or command in RESOURCES:
            forwarded = rest[1:]
        elif command is not None and not command.startswith("-") and command not in command_names():
            raise _unknown_command(command)
        else:
            args = _parse(rest)
            args.global_flags = flags
            forwarded = []
    except CliError as error:
        return _finish(args, flags, error.exit, {}, error)
    except _UsageError as usage:
        return _finish_usage(args, flags, usage)

    try:
        with _environment(_flag_environment(flags)):
            # Inside the flag environment, because a forwarded module can read the source root when it is imported.
            if args.command in PASSTHROUGH:
                _check_passthrough_usage(args.command, forwarded)
            if args.command is None:
                code, data = _home_start(flags)
                return _finish(args, flags, code, data)
            if args.command in RESOURCES:
                return cmd_resource(args, forwarded)
            if args.command in PASSTHROUGH or not hasattr(args, "func"):
                code, data = cmd_engine(args, forwarded)
            else:
                code, data = args.func(args)
        return _finish(args, flags, code, data)
    except CliError as error:
        return _finish(args, flags, error.exit, {}, error)
    except _UsageError as usage:
        return _finish_usage(args, flags, usage)
    except _Reported as reported:
        # The report text already lists the problem and its recovery, so text mode prints no second copy.
        return _finish(args, flags, reported.error.exit, reported.data, reported.error if flags.json else None)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return INTERRUPTED
    except Exception as exc:
        from stratarc import changelog
        from stratarc.config import ConfigError

        if isinstance(exc, ConfigError):
            return _finish(args, flags, 2, {}, CliError("msg-1002", param=paths.CONFIG_NAME, detail=exc))
        if isinstance(exc, changelog.DatabaseUnavailable):
            return _finish(args, flags, UNAVAILABLE, {}, CliError("msg-1116", param="database", detail=exc))
        if flags.debug:
            traceback.print_exc()
        return _finish(args, flags, FAILURE, {}, CliError("msg-1008", command=args.command, detail=exc))


if __name__ == "__main__":
    sys.exit(main())
