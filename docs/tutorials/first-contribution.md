# First Contribution

This tutorial takes you from a fresh clone to a change that is ready for review. You set up a development environment, run the test suite, make one small change and check it. It follows one path and explains only what that path needs; [Contributing](../../CONTRIBUTING.md) holds the guidelines it applies, and the [how-to guides](../how-to-guides/README.md) cover each step in more depth.

## What You Need

- Python 3.11 or newer.
- `git`, and a GitHub account if you intend to open a pull request.

## Clone and Install

```bash
git clone https://github.com/klappe-pm/stratarc && cd stratarc && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[test]'
```

This installs Stratarc as an editable package with `pytest` and `jsonschema`, the only test dependencies. The command itself has no runtime dependencies.

## Run the Tests

```bash
cd stratarc && python3 -m pytest
```

The full suite includes one slow test that builds a wheel, installs it into a fresh virtual environment and checks that the installed command scaffolds a source root and syncs a runtime of your own. While iterating, skip it:

```bash
cd stratarc && python3 -m pytest -m 'not slow'
```

Run the full suite before you commit. See [Run the Tests](../how-to-guides/run-the-tests.md) for the other checks.

## Make a Change

Pick something small for a first change: a wording fix in a page under `docs/`, a missing edge case in `tests/`, a clearer message in `stratarc/messages.py`. Read the part of the user documentation that covers what you are changing first, and [Source Layout](../reference/source-layout.md) if the change touches the template.

Two conventions catch newcomers. Runtime assets under `stratarc/data/` are reached only through `importlib.resources`, never through a path built from `__file__`; see [Package Data](../reference/package-data.md) for why. And a user-facing message is added to the catalog in `stratarc/messages.py` first, then raised by id.

## Check It

```bash
cd stratarc && python3 -m pytest
```

If you changed a command, an option or a message, regenerate the two reference pages that come from the code and commit the result:

```bash
cd stratarc && python3 scripts/docs/generate-reference.py
```

## Commit

Commit with a [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) message, for example `docs: clarify the init target rule` or `fix: refuse an init target that is a file`. Add a line under Unreleased in [the changelog](../../CHANGELOG.md) if the change is visible to a user. Keep the change to one thing, and say in the pull request what it does and how you tested it.

## Next Steps

- Read [Architecture](../explanation/architecture.md) before a change that touches more than one part of the pipeline.
- Read [Add a Runtime](../how-to-guides/add-a-runtime.md) to see how a runtime of your own is added.
- Read the [decision records](../explanation/decisions/README.md) before proposing a change to something they settle.
