# Roll Back a Deploy

A sync that exits 0 says only that the writes did not fail. This guide shows how to confirm that what is deployed equals what the source describes, how to have Stratarc undo a deploy that does not match, and what protects you from deploying an older policy over a newer one.

## Verify Instead of Trusting

```bash
cd ~/stratarc-source && stratarc sync --verify
```

After writing, `--verify` renders again into a scratch area and compares it with the deployed files byte for byte. Drift means exactly what a dry run would change. It never writes a deployed file, and it exits 6 when it finds drift.

The report lists every target it covers: the runtimes and projects it expected, the ones it compared, verified or found drifted, and the ones it skipped, each with a reason. A runtime `stratarc.toml` enables but that is not installed is expected and skipped; one that is turned off, or neither installed nor named, is excluded and listed with its reason. The result is `verified` only when every expected target was compared and matched, `incomplete` when an expected target was skipped, `no-targets` when nothing was compared and `drift` on any difference. The JSON report carries the same lists under `coverage` and a `complete` flag. Only drift changes the exit status, as before; to make automation require full coverage, add `--require-complete`, which exits 5 (message `msg-1155`) unless the result is `verified`:

```bash
cd ~/stratarc-source && stratarc sync --require-complete
```

A clean result is evidence of file consistency only: the same adapters render what is on disk. It does not show that a runtime loaded those files or enforces them; every report says so in its `evidence` field.

## Roll Back Automatically

```bash
cd ~/stratarc-source && stratarc sync --verify --rollback-on-drift
```

Before it writes, the run backs up every file each adapter will change, and each runtime's deploy stamp. If verification finds drift, it puts the backups back, removes files the run created and exits 6. If a backup is missing it exits 5 and names the file, instead of reporting a restore it cannot perform.

Rollback covers the runtime directories only. Project checkouts are verified but never rolled back, because they are working trees that may hold edits of yours. The three flags (`--verify`, `--rollback-on-drift`, `--require-complete`) cannot be combined with `--only`, `--check`, `--diff`, `--dry-run`, `--prune` or `--list`.

## When a Deploy Fails Partway

Before writing anything to a runtime or project, a write run checks every enabled runtime: each hook event has a mapping, the adapter is present and supports the installed version, the deploy is not older than the one in place, and the target can be written. If any check fails, nothing is written to any runtime or project, and the run exits 2 (5 when the only failure is an unsupported adapter version). The run does refresh the source root's derived files first, the rules digest in `AGENTS.md` and `control-plane.md`, which a later run regenerates.

A failure only the write can find, such as a runtime file the component renderer refuses to rewrite or a write the system rejects, fails that runtime; the others still deploy, and project delivery is not attempted. The run then prints a `sync: deployment:` account naming every target as `changed`, `current`, `failed` or `not-attempted`, with the reason, and exits with the failure's status. Every write run also writes the account to `~/.stratarc/state/deploy-last.json`, whose `result` is `complete`, `failed` (nothing was written), `partial` (something was), `restored` or `restore-failed`.

With `--rollback-on-drift`, a partial deployment puts back the runtime files it wrote from the backups taken before the write, and the account marks those runtimes `restored`; the exit status is still the failure's. If a backup is missing, the runtimes are marked `restore-failed` and the run exits 5. Restoration rewrites only the files the run backed up or created, so an unrelated file you edited in the meantime is left alone, and running the same command again is safe. Project checkouts and the source root are never rolled back.

## Restore a File by Hand

Every file Stratarc replaces in its own home, and every runtime file a `--rollback-on-drift` run changes, is first copied into `~/.stratarc/backups/`. Look there for an older copy:

```bash
ls ~/.stratarc/backups
```

## Clean Up Old Backups

Backups grow until you clean them. This lists what would go and removes nothing:

```bash
stratarc doctor --clean
```

Add `--yes` to remove it. The clean keeps the newest 20 versions of each file and anything under 30 days old, and never touches your settings or registered adapters.

## The Stale-Source Guard

Each runtime directory receives a stamp file, `.stratarc-deploy.json`, recording the policy version, the source checkout and its commit. A deploy that would replace a newer policy version with an older one is refused with a message naming both versions and the checkout that wrote the newer one. This protects you when several checkouts or machines share a runtime directory. Bump `policyVersion` in `permissions.json` when you change the policy.
