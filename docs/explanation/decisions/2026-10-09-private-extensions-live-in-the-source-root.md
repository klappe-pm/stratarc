# Private Extensions Live in the Source Root

## Status

accepted, 2026-10-09

## Context

Some behavior belongs to one user's tree and not to the published engine: extra validation checks and renderers for particular projects. The engine needs a way to load these without containing them.

## Decision

Optional extensions live in the source root and are found through `paths.source_root()`. Extra validator checks are read from `scripts/private/validate_checks.py` ([validate.py](../../../stratarc/validate.py)), and project renderers from `scripts/private/project_renderers.py` ([projects.py](../../../stratarc/projects.py)). Each is loaded by file path. An absent extension is a no-op, and a broken one is reported and skipped so the rest of the run still completes. Runtimes are added the same way, from `adapters/`, see [a runtime is one adapter file in the source root](2026-10-14-a-runtime-is-one-adapter-file-in-the-source-root.md).

## Alternatives

- Python entry points. Rejected: a source root is not an installable package, so an entry point would force it to become one just to add a check.
- Configuration in `stratarc.toml` naming a module to import. Rejected: it adds a second place to look for something the source root's layout already locates.
- Build the extensions into the engine behind switches. Rejected: it would publish material that belongs to a single user and grow the engine for everyone.

## Consequences

- A source root with no extensions behaves as a plain one, with the generic checks only.
- Extensions are versioned with the source root that uses them, so they change in the same commit as the files they check.
- An extension runs arbitrary code from the source root, so loading one is a trust decision made by whoever owns that tree.
- A failing extension never loses the gate: the validator reports it as an error finding and keeps running the other checks.
