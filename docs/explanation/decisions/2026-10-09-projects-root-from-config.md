# Projects Root from Config

## Status

accepted, 2026-10-09. Amended 2026-10-14: the default is `<home>/projects` and checkouts may sit directly in it.

## Context

The engine delivers configuration into project checkouts and finds them under one directory. The location of that directory was settable only by a flag or an environment variable, and three modules each carried their own copy of the rule that locates it.

## Decision

`projects_root` in `stratarc.toml` feeds `paths.projects_root()`, and the precedence is the command line flag, then `STRATARC_PROJECTS_DIR`, then `stratarc.toml`, then the default `<home>/projects`. `paths.projects_dir()` returns that directory for every caller. Its children are either the checkouts themselves (a flat layout, where every checkout is active) or status folders (`active/`, `new/`, `inactive/`, `archived/`, `external/`) that hold them, so shelving a project means moving it to `archived/`. A checkout may also sit one grouping folder down. Both functions are in [paths.py](../../../stratarc/paths.py), and the config key is read by [config.py](../../../stratarc/config.py).

## Alternatives

- Keep the flag and the environment variable only. Rejected: a source root could not state where its projects live, so every user and every script had to repeat it.
- Require status folders. Rejected: most people keep checkouts in one flat directory, and a layout rule should not decide whether a project is found.
- Leave the three copies in place. Rejected: one function is a single place to test and to change.

## Consequences

- A source root carries its own projects location, so the same command works on any machine that shares it.
- An explicit flag still overrides everything, which keeps tests and one-off runs simple.
- The two functions take their arguments in different orders, which the docstring of `projects_dir` warns about.
- A flat root that also holds unrelated non-repository folders is fine: only directories with a `.git` entry are checkouts.
