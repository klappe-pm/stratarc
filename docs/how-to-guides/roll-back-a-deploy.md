# Roll Back a Deploy

A sync that exits 0 says only that the writes did not fail. This guide shows how to confirm that what is deployed equals what the source describes, how to have Stratarc undo a deploy that does not match, and what protects you from deploying an older policy over a newer one.

## Verify Instead of Trusting

```bash
cd ~/stratarc-source && stratarc sync --verify
```

After writing, `--verify` renders again into a scratch area and compares it with the deployed files byte for byte. Drift means exactly what a dry run would change. It never writes a deployed file, and it exits 6 when it finds drift.

## Roll Back Automatically

```bash
cd ~/stratarc-source && stratarc sync --verify --rollback-on-drift
```

Before it writes, the run backs up every file each adapter will change, and each runtime's deploy stamp. If verification finds drift, it puts the backups back, removes files the run created and exits 6. If a backup is missing it exits 5 and names the file, instead of reporting a restore it cannot perform.

Rollback covers the runtime directories only. Project checkouts are verified but never rolled back, because they are working trees that may hold edits of yours. The two flags cannot be combined with `--only`, `--check`, `--diff`, `--dry-run`, `--prune` or `--list`.

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
