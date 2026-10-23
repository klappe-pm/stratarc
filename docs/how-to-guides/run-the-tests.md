# Run the Tests

This guide covers running the test suite: the markers, the slow wheel test, the worked example and the two checks that need `bash` and `bun`. It assumes the editable install from [First Contribution](../tutorials/first-contribution.md).

## The Test Suite

```bash
cd stratarc && python3 -m pytest
```

Tests live under `tests/` and read only fixtures under `tests/fixtures/`, never a real home directory or real runtime configuration. A full run takes about a minute.

## The Slow Marker

One test is marked `slow`: it builds a wheel from the checkout, installs it into a fresh virtual environment, and runs the installed `stratarc` outside the checkout. It scaffolds a source root and compares it with the bundled template byte for byte, runs a dry-run sync and `doctor` against a temporary `HOME`, then adds a runtime of its own with `adapter new` and syncs it. It proves that the package data and the adapters ship correctly; see [Package Data](../reference/package-data.md). Skip it while iterating and run it before you commit:

```bash
cd stratarc && python3 -m pytest -m 'not slow'
```

## The Worked Example

`tests/test_examples.py` runs `stratarc diff`, `sync` and `check` on a copy of `examples/notes-cli/source` in a temporary home and compares what `sync` wrote with `examples/notes-cli/expected`, byte for byte. In the expected files `<home>` stands for the temporary home path. A sync also writes per-target stamp files and a few generated files that `expected/` does not hold; the `ENGINE_OWNED` pattern in the test lists them. When an adapter changes what a sync writes, the test names the files that differ. Update them from the output of a sync in a throwaway home, as the [example](../../examples/notes-cli/README.md) describes.

## The Shell and Bun Tests

Tests under `tests/` named `*.test.sh` run with `bash` and are marked `shell`; a non-zero exit fails them. The OpenCode hook bridge test, `tests/hooks/opencode-runtime-hooks.test.ts`, runs with `bun test` and is marked `bun`. It is skipped when `bun` is not installed. Run only one kind with `-m shell` or `-m bun`.

## The Reference Pages

Two pages under `docs/reference/generated/` are written from the code. A test fails when either differs from what the code produces. After changing a command, an option or a message, regenerate them:

```bash
cd stratarc && python3 scripts/docs/generate-reference.py
```
