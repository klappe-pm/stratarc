# Exit Code Map

## Status

accepted, 2026-10-09

## Context

Scripts and CI jobs that call stratarc need to tell a bad argument from a refused write, a conflict, a missing prerequisite and a deployed file that no longer matches its source. A caller should be able to branch on the status alone, and read the same structured error when it asks for JSON.

## Decision

stratarc exits 0 for ok, 1 for failure, 2 for invalid input, 3 for denied, 4 for conflict, 5 for unavailable, 6 for drift or a failed verification and 130 for an interrupted run. With `--json` every command prints one JSON envelope, `{ok, data, error}`, where `error` carries `code`, `message`, `param` and `hint`. The codes live in [messages.py](../../../stratarc/messages.py) and are mapped to names in [cli.py](../../../stratarc/cli.py).

## Alternatives

- Exit 1 for every failure. Simple, but a script cannot tell a typo from a drifted deployment without parsing text.
- Reuse another tool's table unchanged. It lacks a code for drift and for a newer-schema refusal, so those would collapse into a generic failure.

## Consequences

- A script can branch on the status alone: 6 means rerun a sync, 5 means upgrade or wait, 2 means fix the call.
- A new failure class needs a new code only if callers must react differently to it; otherwise it reuses the nearest existing code.
- The numbers are part of the public contract and cannot be reassigned without a superseding record.
