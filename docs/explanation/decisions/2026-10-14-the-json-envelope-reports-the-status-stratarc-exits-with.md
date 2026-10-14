# The JSON Envelope Reports the Status Stratarc Exits With

## Status

accepted, 2026-10-14. Refines the envelope in [exit code map](2026-10-09-exit-code-map.md).

## Context

An engine command run with `--json` puts an `exit` field in `data`. It carried the status the command's module returned, before stratarc mapped it. A module that reports drift returns 1, which stratarc exits with as 6, so `stratarc --json check` printed `data.exit` 1 beside an error message that said "exited 6" and a process status of 6. A module status outside the exit code map, which stratarc exits with as 1, showed the same split. The field was not documented, so a caller had no way to know which number to trust.

## Decision

`data.exit` is the status stratarc exits with, after the drift and failure mapping. It always equals the process status and the number in a generated error message. The module's own return is not reported.

## Alternatives

Keeping the module's return under a second key, such as `module_exit`, would preserve a number no caller needs: the drift mapping is fixed by the command, so the module's return can be read off the documented table. Leaving `data.exit` as the module's return and rewording the message would keep the envelope disagreeing with the process status, which is the number scripts branch on.

## Consequences

A caller that read `data.exit` 1 as drift from `check`, `reconcile --check`, `projects --check`, `projects --verify` or `gen-rules-digest --check` must read 6. The field matches the `exit` of a `sync --verify` report, which already carried the mapped status. The change is listed under Changed in the CHANGELOG.
