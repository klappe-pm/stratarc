# Contributing

Thank you for helping improve Stratarc. Open an issue to discuss a change before writing a large pull request, so the effort goes where it will be merged. This page holds the rules every contribution follows; the walkthroughs and reference live under [docs](docs/README.md), starting with [First Contribution](docs/tutorials/first-contribution.md). Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setup

```bash
git clone https://github.com/klappe-pm/stratarc && cd stratarc && python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[test]'
```

## Tests

Run the suite before every commit. The slow marker builds a wheel and installs it into a fresh virtual environment. [Run the Tests](docs/how-to-guides/run-the-tests.md) covers the other checks.

```bash
python3 -m pytest
```

```bash
python3 -m pytest -m 'not slow'
```

## Guidelines

- Python 3.11 or newer, standard library only at runtime. `pytest` and `jsonschema` are test dependencies.
- Runtime assets live under `stratarc/data/` and are read through `importlib.resources`, never through a path built from `__file__`. See [Package Data](docs/reference/package-data.md).
- Tests read fixtures only: never the live home directory or a user's real runtime configuration.
- A user-facing error is added to the catalog in `stratarc/messages.py` first and raised by id. After changing a command, an option or a message, run `python3 scripts/docs/generate-reference.py` and commit the regenerated pages.
- Documentation goes in `docs/`, in the folder for its kind: `tutorials/`, `how-to-guides/`, `reference/` or `explanation/`. Headings use Title Case, and each paragraph and list item is one line, not hard-wrapped.
- Never commit a secret, credential, private key or `.env` file. `.env.example` with placeholder values is allowed.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Pull Requests

Keep each pull request to one change, describe what it does and how you tested it, and make sure the test suite passes. Add a line under Unreleased in [CHANGELOG.md](CHANGELOG.md) for any user-visible change. A change that affects a decision recorded under [docs/explanation/decisions](docs/explanation/decisions/README.md) should add a record that amends or replaces it.

## License

By contributing, you agree that your contributions are licensed under the MIT license in [LICENSE](LICENSE).
