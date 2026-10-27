# CLI

This page describes how the `stratarc` command behaves as a whole: how it finds your source root, what the global options do, the JSON output and the exit statuses. Every command and option is listed in the generated [Commands](generated/commands.md) page, and every message in [Errors](generated/errors.md). For when to use a command, see the [how-to guides](../how-to-guides/README.md).

## Running Stratarc with No Command

`stratarc` on its own adapts to where it runs. In a terminal with no source root found, it starts `stratarc setup`. In a terminal with a source root found, it prints where the source root is, which runtimes are enabled and the commands to run next, and exits 0. A root named by `--root` or `STRATARC_SOURCE` is used as given and never starts setup; one that does not exist is refused with `msg-1001`. Outside a terminal it prints the help and exits 0, so a script never waits on a prompt. With `--json` it is invalid input (`msg-1011`) and exits 2.

## Commands

| command | does |
| --- | --- |
| `help [COMMAND]` | lists every command, or explains one with examples; `stratarc help sync` is the same as `stratarc sync --help` |
| `setup` | walks through creating or adopting a source root, choosing runtimes from those installed, previewing the first deploy and deploying on an explicit yes; records the source root in `~/.stratarc/config.toml`; needs a terminal |
| `init TARGET` | writes a new source root from the bundled template into an absent or empty directory |
| `doctor` | reports the health of the install, the home and the source root; `--permissions`, `--clean` and `--report` extend it |
| `sync` | renders the source into every enabled runtime and managed project |
| `check` | reports what is out of date, writes nothing and exits 6 on drift |
| `diff` | prints what a sync would change, writes nothing and exits 0 |
| `prune` | deletes files a runtime holds that the source no longer produces |
| `reconcile` | refreshes `control-plane.md` from the source tree |
| `validate` | checks a source root against the schemas and the engine's rules |
| `projects` | delivers `projects-root/` into the managed project checkouts |
| `gen-rules-digest` | renders or checks the rules digest in instruction files |
| `components` | validates `components.json` and lists what it declares |
| `drift` | reports where checkouts differ from what the control plane delivers, writes nothing to them and exits 6 on drift |
| `workflows` | checks and shows the optional workflow module configuration, in the control plane `[workflows]` table and each project's `workflows.toml`, and exits 1 on a problem |
| `adapter` | lists, shows, creates, registers and deprecates adapters |

## Global Options

Global options are accepted before or after the command, and each lasts for that one command.

| option | effect |
| --- | --- |
| `--root PATH` | the source root; sets `STRATARC_SOURCE` |
| `--home PATH` | the home every runtime target and `~` hangs under; sets `STRATARC_HOME` |
| `--projects-root PATH` | the directory that holds project checkouts; sets `STRATARC_PROJECTS_DIR` |
| `--json` | print one JSON envelope instead of text |
| `--debug` | print a traceback when a command stops unexpectedly |
| `--version` | print `stratarc <version>` and exit 0 |
| `--help` | print the usage summary, a short start here list and the exit statuses, and exit 0 |

## How the Source Root Is Found

In order: `--root`, the `STRATARC_SOURCE` environment variable, the nearest directory at or above the current one that holds `stratarc.toml`, the source root `stratarc setup` recorded in `~/.stratarc/config.toml` when it still holds `stratarc.toml`, and the current directory. A command that reads the source refuses the current directory when it holds no `stratarc.toml` (`msg-1009`), so running `stratarc sync` in the wrong directory writes nothing. `stratarc doctor` prints which of these decided. The home is `STRATARC_HOME`, then `HOME`. The projects root is `--projects-root`, then `STRATARC_PROJECTS_DIR`, then `projects_root` in `stratarc.toml`, then `~/projects`. See [Configuration](configuration.md).

## The JSON Envelope

With `--json` a command prints exactly one object on standard output and exits with the same status as without it.

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "msg-1001",
    "message": "The source root /tmp/nowhere does not exist or is not a directory.",
    "param": "root",
    "hint": "Pass an existing directory with --root, or create one with `stratarc init /tmp/nowhere`."
  }
}
```

`ok` is true and `error` is null on success, and `data` then holds the command's result. For `sync`, `check`, `diff`, `prune`, `reconcile`, `validate`, `projects`, `gen-rules-digest`, `components`, `drift` and `workflows`, `data` holds `command`, `exit`, `stdout` and `stderr` whenever the command ran, whatever its status; a refusal before it runs, such as `msg-1001`, leaves `data` null. `exit` is the status stratarc exits with, after the drift mapping under [Exit Statuses](#exit-statuses), so `stratarc --json check` on a drifted deployment reports `"exit": 6`. Without `--json`, a refusal prints one line headed by its message id, one line of recovery and a link to the message's entry in [Errors](generated/errors.md) to standard error.

## Mistyped Commands and Arguments

An unknown command is refused with `msg-1010`, which names the closest command when one is near (`stratarc synk` suggests `stratarc sync`). An argument a command does not take is refused with `msg-1014`, after that command's own usage line, and its recovery names `stratarc help COMMAND`. The arguments are checked before the source root is looked for, so a mistyped option is reported as such in any directory. Both exit 2, and with `--json` both print one envelope like any other refusal.

## Exit Statuses

| status | meaning |
| --- | --- |
| 0 | ok |
| 1 | failure: the command ran and did not succeed |
| 2 | invalid input: a bad argument, an unknown source root, an invalid `stratarc.toml`, or a refusal by the engine |
| 3 | denied: the home is missing or not writable |
| 4 | conflict: the target already holds something |
| 5 | unavailable: a packaged resource is missing, a file in the home is newer than this stratarc, an adapter does not support the installed runtime, or the change log database is locked |
| 6 | drift: the deployed files differ from what the source renders |
| 130 | interrupted |

A command that reports drift (`check`, `reconcile --check`, `projects --check`, `projects --verify`, `gen-rules-digest --check`, `drift`) exits 6 where its module returns 1.

## Environment Variables

| variable | effect |
| --- | --- |
| `STRATARC_SOURCE` | the source root |
| `STRATARC_HOME` | the directory the home and every `~` in a target resolve under |
| `STRATARC_PROJECTS_DIR` | the projects root |
| `STRATARC_NAME` | the name Stratarc puts on what it generates; see [Configuration](configuration.md) |
| `STRATARC_HELD_PROJECTS` | the projects this machine holds: unset or `all`, `present`, or a comma separated list of names |
| `STRATARC_LOG` | set to `1` to turn on the change log database |
