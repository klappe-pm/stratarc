# Cut a Release

This guide is for a maintainer releasing a new version of Stratarc: bumping the version, settling the changelog and pushing the tag that publishes the package. Publishing runs in `.github/workflows/release.yml` through PyPI trusted publishing, so no PyPI token exists anywhere to leak. It assumes a clean checkout of `main` with the test suite green.

## Where the Version Lives

The version is `__version__` in `stratarc/__init__.py`. `pyproject.toml` declares the version as dynamic and reads it from that file through hatchling, so it is set in one place. The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## One-Time Setup

These steps are done once, by the repository owner, before the first release that uses the workflow.

1. On pypi.org, open the `stratarc` project, then Publishing, and add a trusted publisher: owner `klappe-pm`, repository `stratarc`, workflow `release.yml`, environment `pypi`.
2. In the repository settings, create an environment named `pypi` with yourself as a required reviewer, a deployment rule that allows only tags matching `v*`, and administrator bypass turned off.
3. Add a tag ruleset for `v*` so that only maintainers can create, move or delete release tags.

## Steps

1. Decide the new version from the Unreleased section of [the changelog](../../CHANGELOG.md): a breaking change bumps the major version, a new capability bumps the minor, a fix bumps the patch. A version number that was ever uploaded to PyPI can never be reused, even after it is deleted.
2. Set `__version__` in `stratarc/__init__.py`.
3. In the changelog, rename Unreleased to the version and the date, and open a new empty Unreleased section above it.
4. Run the full test suite, including the slow wheel test:

```bash
cd stratarc && python3 -P -m pytest
```

5. Commit as `chore: release <version>` and merge it through a pull request like any other change.
6. Tag the merge commit `v<version>` and push the tag:

```bash
cd stratarc && git tag -a v<version> -m "stratarc <version>" && git push origin v<version>
```

7. The release workflow starts on the tag. Its build job refuses a tag that is not on `main` or does not match `__version__`, builds the distributions with hash pinned tools and records their checksums in the job summary. Its test job installs the built wheel and runs the suite against it. Its publish job waits for your approval in the `pypi` environment; approve it once the first two jobs are green.
8. Create a GitHub release on the tag with the changelog section as its notes.

The project page shows the README, so every link in it must be absolute, and the page text of a published version can never be changed; a fix ships as a new version.

## The Lock Files

`requirements/build.txt` and `requirements/ci.txt` pin every tool the workflow installs, with hashes. They are compiled from `requirements/build.in` and `requirements/ci.in`. To update them, edit the `.in` file and recompile:

```bash
cd stratarc && python3 -m pip install pip-tools && pip-compile --generate-hashes --strip-extras --output-file=requirements/ci.txt requirements/ci.in
```

## After the Release

Confirm that `pipx install stratarc==<version>` works, that `stratarc init` scaffolds a source root, and that the project page on pypi.org renders the README with working links.
