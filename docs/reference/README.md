# Reference

Reference pages describe the machinery: the commands, the keys, the files each runtime receives. They are for looking something up while you work, so they are organised around the thing described and state facts without instruction.

## Pages

- [CLI](cli.md): how the `stratarc` command finds its source root, its global options, the JSON envelope, exit statuses and environment variables.
- [Configuration](configuration.md): every key in `stratarc.toml`, how values are resolved and the home directory.
- [Source Layout](source-layout.md): every file and directory in a source root, and the keys of `permissions.json`, `components.json` and `rules/tiers.json`.
- [Control Plane](control-plane.md): the format of `control-plane.md`, its tables, cells and defaults.
- [Adapter Files](adapter-files.md): the contract for an adapter, whether packaged or added in a source root.
- [Runtimes](runtimes/README.md): the supported runtimes, their default targets and one page per runtime: [Claude](runtimes/claude.md), [Codex](runtimes/codex.md), [Cursor](runtimes/cursor.md), [Gemini](runtimes/gemini.md) and [OpenCode](runtimes/opencode.md).
- [Package Data](package-data.md): how the templates, schemas and hook libraries under `stratarc/data/` are packaged and resolved.

## Generated Pages

These two pages are generated from the code, so they cannot drift from it. Regenerate them with `python3 scripts/docs/generate-reference.py`.

- [Commands](generated/commands.md): every command, option and argument, generated from the argument parser.
- [Errors](generated/errors.md): the error catalog, one entry per message id.
