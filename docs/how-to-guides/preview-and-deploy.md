# Preview and Deploy

Stratarc separates looking from writing. `diff` and `check` never write; `sync` writes. This guide shows how to see a change before it lands, deploy it, and keep a runtime directory free of files the source no longer produces.

## See What Would Change

```bash
cd ~/stratarc-source && stratarc diff
```

`diff` renders the source exactly as a sync would and prints each file it would copy, merge or write, with paths shown under `~`. It writes nothing and exits 0 even when it finds differences. It also reports a rule you added since the last sync, because it re-embeds the rules digest in a scratch copy instead of reading the stale one.

```bash
cd ~/stratarc-source && stratarc check
```

`check` makes the same comparison and exits 6 when anything is out of date. It also reports what each runtime holds that the source does not own: orphan files, hook groups another tool registered, and literal secrets found in a runtime's files. Use it in a script or a pre-push step.

## Deploy

```bash
cd ~/stratarc-source && stratarc sync
```

Before it writes, `sync` validates the source and stops on an error. It then refreshes `control-plane.md` and the rules digest, and renders each enabled runtime whose directory exists, and each active project. It writes only files it owns, merges into shared settings files without disturbing your own entries, and never removes a file. A line per change names what it did.

To try one runtime, or a dry run that is the same as `diff`:

```bash
cd ~/stratarc-source && stratarc sync --only gemini
```

```bash
cd ~/stratarc-source && stratarc sync --dry-run
```

## Remove What the Source No Longer Produces

`sync` adds and updates but does not delete. After you delete a rule, command or skill from the source, its deployed copy is still in each runtime. List what would go, then remove it:

```bash
cd ~/stratarc-source && stratarc prune --dry-run
```

```bash
cd ~/stratarc-source && stratarc prune
```

`prune` removes only paths Stratarc owns, such as `commands/`, `prompts/` and `rules/`, and only files the current source does not produce. A command you installed into a runtime by hand stays. It writes the list of what it removed to `~/.stratarc/telemetry/` first.

## Verify After the Write

```bash
cd ~/stratarc-source && stratarc sync --verify
```

`--verify` re-renders after the write and compares byte for byte with what is on disk. It exits 6 on a difference. See [Roll Back a Deploy](roll-back-a-deploy.md) for restoring automatically.

## Read the Exit Status

| status | meaning |
| --- | --- |
| 0 | done, or nothing to do |
| 2 | the source is invalid, or a guard refused the deploy |
| 5 | an adapter does not support the installed runtime version |
| 6 | `check` or `--verify` found drift |

The full table is in [CLI](../reference/cli.md), and each message id is explained in [Errors](../reference/generated/errors.md).
