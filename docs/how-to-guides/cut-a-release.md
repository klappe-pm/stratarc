# Cut a Release

This guide is for a maintainer releasing a new version of Stratarc: bumping the version, settling the changelog, tagging and publishing the package. It publishes to PyPI and as a GitHub release. It assumes a clean checkout of `main` with the test suite green.

## Where the Version Lives

The version is `__version__` in `stratarc/__init__.py`. `pyproject.toml` declares the version as dynamic and reads it from that file through hatchling, so it is set in one place. The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Steps

1. Decide the new version from the Unreleased section of [the changelog](../../CHANGELOG.md): a breaking change bumps the major version, a new capability bumps the minor, a fix bumps the patch. A version number that was ever uploaded to PyPI can never be reused, even after it is deleted.
2. Set `__version__` in `stratarc/__init__.py`.
3. In the changelog, rename Unreleased to the version and the date, and open a new empty Unreleased section above it.
4. Run the full test suite, including the slow wheel test:

```bash
cd stratarc && python3 -m pytest
```

5. Commit as `chore: release <version>` and merge it through a pull request like any other change.
6. Tag the merge commit `v<version>` and push the tag:

```bash
cd stratarc && git tag -a v<version> -m "stratarc <version>" && git push origin v<version>
```

7. Build the distributions from the tag in a clean clone, and check them:

```bash
cd stratarc && python3 -m pip install build twine && python3 -m build --outdir dist && python3 -m twine check dist/*
```

8. Create a GitHub release on the tag with the changelog section as its notes.
9. Upload to PyPI. The project page shows the README, so every link in it must be absolute, and the page text of a published version can never be changed; a fix ships as a new version. Run the command in your own terminal and enter `__token__` as the username and a PyPI API token as the password. Never put the token in a file, a command line or a chat:

```bash
cd stratarc && python3 -m twine upload dist/*
```

## After the Release

Confirm that `pipx install stratarc==<version>` works, that `stratarc init` scaffolds a source root, and that the project page on pypi.org renders the README with working links.
