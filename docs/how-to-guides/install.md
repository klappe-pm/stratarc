# Install

This guide covers installing Stratarc: the supported methods, the Python versions it runs on, and how to upgrade and uninstall. If you have never used Stratarc, [Getting Started](../tutorials/getting-started.md) walks the install as one step among several.

## Requirements

Python 3.11 or newer. Stratarc has no runtime dependencies beyond the standard library.

## Install from PyPI

```bash
pipx install stratarc
```

`pipx` keeps the command in its own environment and puts it on your path. Plain `pip install stratarc` works too, into whichever environment is active.

## Install from the Repository

To install straight from GitHub, for example a tagged release, name the tag after an `@`:

```bash
pipx install git+https://github.com/klappe-pm/stratarc@<tag>
```

Leave off the `@<tag>` to follow the default branch.

## Install for Development

Contributors install an editable copy with the test dependencies. See [First Contribution](../tutorials/first-contribution.md) for the full setup.

```bash
cd stratarc && pip install -e '.[test]'
```

## Check the Install

```bash
stratarc --version
```

```bash
stratarc doctor
```

`doctor` reports the Python version, the home directory, the source root it resolved and each runtime with its target directory. It exits 3 when the home directory cannot be written to and 2 when the source root or its `stratarc.toml` is unusable, and says which.

## Upgrade

```bash
pipx upgrade stratarc
```

For a repository install, run `pipx reinstall stratarc` to pick up the latest commit.

## Uninstall

```bash
pipx uninstall stratarc
```

Uninstalling removes the command only. Your source root, the `~/.stratarc` home and anything already deployed into runtime directories stay where they are.
