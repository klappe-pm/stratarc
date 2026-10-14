<p align="center">
  <a href="https://github.com/klappe-pm/stratarc"><img src="https://raw.githubusercontent.com/klappe-pm/stratarc/main/.github/stratarc-banner.svg" alt="A terminal window: stratarc sync is typed, the stratarc wordmark appears, and each runtime is checked off" width="760"></a>
</p>

<h1 align="center">Stratarc</h1>

<p align="center">
  One agent configuration source, rendered into any agent runtime you use.
</p>

<p align="center">
  <a href="https://pypi.org/project/stratarc/"><img src="https://img.shields.io/pypi/v/stratarc?style=flat-square&color=3ddc84&labelColor=162233&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/stratarc/"><img src="https://img.shields.io/pypi/pyversions/stratarc?style=flat-square&color=5aa9ff&labelColor=162233&label=Python" alt="Python versions"></a>
  <a href="https://github.com/klappe-pm/stratarc/releases"><img src="https://img.shields.io/github/v/release/klappe-pm/stratarc?style=flat-square&color=3ddc84&labelColor=162233&label=release" alt="Latest release"></a>
  <a href="https://github.com/klappe-pm/stratarc/blob/main/LICENSE"><img src="https://img.shields.io/github/license/klappe-pm/stratarc?style=flat-square&color=5aa9ff&labelColor=162233&label=license" alt="MIT license"></a>
  <a href="https://github.com/klappe-pm/stratarc/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/dependencies-none-3ddc84?style=flat-square&labelColor=162233" alt="No runtime dependencies"></a>
  <a href="https://github.com/klappe-pm/stratarc/blob/main/docs/README.md"><img src="https://img.shields.io/badge/runtimes-5-5aa9ff?style=flat-square&labelColor=162233" alt="Five supported runtimes"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#commands">Commands</a> ·
  <a href="https://github.com/klappe-pm/stratarc/blob/main/docs/README.md">Docs</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

If you use more than one coding agent, you already know the problem. Claude Code wants a `CLAUDE.md` and a `settings.json`. Codex wants `AGENTS.md`. Gemini CLI, Cursor and OpenCode each want their own layout, their own hook format and their own idea of what a rule or a skill looks like. You end up with five copies of the same instructions, and they drift apart the moment you stop paying attention.

Stratarc gives you one place to write it all down. You keep a single source tree of instructions, rules, hooks, skills, commands, agents and permissions. Stratarc compiles that tree into the native format of any runtime you enable and deploys it into the right directory. Edit once, sync, and every agent sees the same configuration.

## Highlights

- **Any runtime, one source.** Claude Code, Codex, Gemini CLI, Cursor and OpenCode are all rendered from the same tree; enable the ones you use.
- **Everything agents read.** Instructions, rules, hooks, skills, commands, subagents and permissions, each translated into the form the runtime expects.
- **Safe by default.** `diff` and `check` show exactly what would change before `sync` writes anything, and Stratarc only ever touches files it owns.
- **Validated before deploy.** The source root is checked against bundled JSON Schemas and the engine's own rules on every run.
- **Projects too.** Managed project checkouts receive their configuration alongside the user-level runtime directories.
- **Bring your own runtime.** A runtime Stratarc does not ship with is one Python file in your source root; `stratarc adapter new` writes the starting point, and it is managed like the rest.
- **Nothing to install but Python.** Pure standard library at runtime, no dependencies.

## Installation

Stratarc needs Python 3.11 or newer. [pipx](https://pipx.pypa.io/) is the easiest way to get a command-line tool onto your path:

```bash
pipx install stratarc
```

Or pin a tagged release straight from GitHub:

```bash
pipx install git+https://github.com/klappe-pm/stratarc@v0.2.0
```

Then check the install and see which runtimes Stratarc found on your machine:

```bash
stratarc doctor
```

## Quick Start

Scaffold a source root wherever you like to keep it:

```bash
stratarc init ~/stratarc-source
```

Open `~/stratarc-source/stratarc.toml` and enable the runtimes you use. Then fill in the rules, skills and hooks under the same directory; every file the scaffold writes is commented, so it shows you where each piece goes.

Preview what a deploy would change. `diff` is read only, so run it as often as you like:

```bash
cd ~/stratarc-source && stratarc diff
```

When the diff looks right, write it out to the enabled runtimes:

```bash
cd ~/stratarc-source && stratarc sync
```

That is the whole loop. From here on, changing your agent setup means editing one tree and running `sync`.

## How It Works

A source root is an ordinary directory. This is roughly what `stratarc init` gives you:

```text
stratarc-source/
├── stratarc.toml        which runtimes are enabled and where they live
├── AGENTS.md            shared instructions any runtime receives
├── rules/               one Markdown file per rule, plus tiers.json
├── hooks/               hook scripts and hooks.json, the hook registry
├── skills/              one folder per skill
├── commands/            slash commands
├── agents/              subagent definitions
├── permissions.json     the single permission policy
├── components.json      MCP servers, plugins and other external components
└── projects-root/       per-project configuration overrides
```

On `sync`, Stratarc validates the tree, hands it to one adapter per enabled runtime, and each adapter renders the files that runtime expects into its target directory:

| Runtime | Target | Receives |
| --- | --- | --- |
| Claude Code | `~/.claude` | `CLAUDE.md`, `settings.json`, hooks, skills, commands, agents |
| Codex | `~/.codex` | `AGENTS.md`, `config.toml`, rules, hooks, skills, prompts |
| Gemini CLI | `~/.gemini` | `GEMINI.md`, `settings.json`, policies, hooks, skills |
| Cursor | `~/.cursor` | rules, hooks, `hooks.json` |
| OpenCode | `~/.config/opencode` | `AGENTS.md`, `opencode.jsonc`, rules, hooks, skills |

The runtime directories are generated output. Change the source, run `sync`, and they are rebuilt.

A complete worked example lives in [examples/notes-cli](https://github.com/klappe-pm/stratarc/tree/main/examples/notes-cli): a small source root beside the exact output each runtime receives from it.

## Commands

| Command | What it does |
| --- | --- |
| `stratarc init TARGET` | Scaffolds a new source root from the bundled template. |
| `stratarc doctor` | Reports the health of the install without changing anything. |
| `stratarc validate` | Checks the source root against the bundled schemas and engine rules. |
| `stratarc diff` | Prints what a sync would change and writes nothing. |
| `stratarc check` | Compares each runtime directory with the source and exits non-zero when anything is stale. |
| `stratarc sync` | Renders the source root into the enabled runtimes and managed projects. |
| `stratarc prune` | Removes files a runtime holds that the source no longer produces. |
| `stratarc reconcile` | Refreshes `control-plane.md`, the table that records which item reaches which scope. |
| `stratarc projects` | Delivers each project's configuration from `projects-root/` into its checkout. `sync` runs it for you. |
| `stratarc gen-rules-digest` | Renders the rules digest, or embeds and checks it inside hand-authored instruction files. |
| `stratarc components` | Validates `components.json` and, with `--list`, prints what it declares. |
| `stratarc adapter` | Lists the adapters, and writes the starting point for a runtime of your own. |

Running `stratarc` with no arguments starts a guided setup the first time; after that it shows the status of the install and the commands to run next. `stratarc help COMMAND` shows one command's help, the same as `stratarc COMMAND --help`.

Every command accepts `--help` and `--json`. The [CLI reference](https://github.com/klappe-pm/stratarc/blob/main/docs/reference/cli.md) covers the full surface, including exit statuses and the JSON envelope, and the [command reference](https://github.com/klappe-pm/stratarc/blob/main/docs/reference/generated/commands.md) lists every command and option, generated from the parser.

## Documentation

The docs live in one tree under `docs/`, following the [Diátaxis](https://diataxis.fr/) layout: tutorials, how-to guides, reference and explanation.

- **Using it:** start with [getting started](https://github.com/klappe-pm/stratarc/blob/main/docs/tutorials/getting-started.md), then browse the rest of [docs](https://github.com/klappe-pm/stratarc/blob/main/docs/README.md).
- **Hacking on it:** start with [first contribution](https://github.com/klappe-pm/stratarc/blob/main/docs/tutorials/first-contribution.md), which sits in the same tree.
- **What ships:** the [changelog](https://github.com/klappe-pm/stratarc/blob/main/CHANGELOG.md).

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](https://github.com/klappe-pm/stratarc/blob/main/CONTRIBUTING.md) first; it will save you a round trip. If you are stuck or have found a bug, [SUPPORT.md](https://github.com/klappe-pm/stratarc/blob/main/SUPPORT.md) says where to ask and where to file an issue.

## Security

Please report vulnerabilities privately as described in [SECURITY.md](https://github.com/klappe-pm/stratarc/blob/main/SECURITY.md) rather than opening a public issue.

## License

Stratarc is released under the [MIT License](https://github.com/klappe-pm/stratarc/blob/main/LICENSE).
