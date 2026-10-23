# Troubleshooting

This guide matches a message or a symptom to its fix. Every refusal prints a message id of the form `msg-NNNN` and exits with a status from the exit-code map; look the id up in [Errors](../reference/generated/errors.md) for the full problem and recovery. If your problem is not here, see [Support](../../SUPPORT.md).

## `stratarc doctor` First

```bash
stratarc doctor
```

It reports the Python version, the home directory and whether it can be written, the source root it resolved and how (`--root`, `STRATARC_SOURCE`, the nearest `stratarc.toml`, or the current directory), and each runtime with its target and whether that exists. Most problems below show up there.

## Init Refuses the Target

`stratarc init` writes only into a directory that does not exist or is empty, and says `exists and is not empty` otherwise. Pick a new directory, or empty the one you named. It never merges a template into existing files.

## A Runtime Is Skipped

A sync writes only into a runtime whose target directory exists, and skips the rest without an error. Check `stratarc sync --list`. Run the runtime once so it creates its directory, or set `target` in `stratarc.toml`. A runtime with `enabled = false`, or an empty `runtime:<name>` cell in the `global` column of the control plane, is skipped too.

## Missing `runtimeDirectories` Entry

```text
sync: claude: missing runtimeDirectories entry for ~/.claude
```

A sync writes only into directories `permissions.json` lists under `runtimeDirectories`. Add the target, using `~` for your home. `stratarc adapter new` does this for a runtime you add.

## A Runtime Table Has No Adapter

`[runtimes.<name>]` in `stratarc.toml` names a runtime that no adapter provides, and `sync` stops. Either remove the table, or create `adapters/<name>.py` in the source root: [Add a Runtime](add-a-runtime.md).

## Refusing to Deploy: Validation Found an Error

```text
sync: refusing to deploy; stratarc.validate --strict --checks generic found an error
```

Run the validator to see the findings, which name the file and the problem:

```bash
cd ~/stratarc-source && stratarc validate --strict
```

Common ones are an agent whose `tools` line names a tool the runtime does not have, a rule with no `## binding` section or one over 120 words, an entry in `components.json` with an unknown key, and a hook registered in `hooks/hooks.json` whose script does not exist.

## A New Rule or Item Does Not Appear

`diff` and `sync` read `control-plane.md`. After you add a source file, run `stratarc reconcile` (a sync does this first). A rule must also be listed in a tier in `rules/tiers.json`, and its `x` must be on in the scope's column. The message `control-plane: stale` means a row is missing or out of date, and `reconcile` fixes it.

## A Deployed File Keeps Reverting

A sync overwrites any file Stratarc owns, so a hand edit to a deployed `AGENTS.md`, command or rule is lost on the next sync. Edit the source instead. Settings files such as `settings.json` are merged, so keys Stratarc does not own are kept.

## A Newer Policy Is Already Deployed

```text
deployed policy version 7 (from /path/to/other-checkout) is newer than the source's version 5; refusing to write an older policy over it
```

Another checkout deployed a higher `policyVersion` to the same runtime directory. Update this checkout from the other one, or raise `policyVersion` in `permissions.json` if this change is the newer one.

## Components Refuse a Token

`components.json` accepts secrets only as `secret://namespace/key` references. A value that looks like a credential is refused, and the message names the entry and key but never repeats the value. Replace it with a reference, and rotate the credential if it was ever committed.

## An Adapter Does Not Support the Installed Runtime

`msg-1114` (exit 5) means the runtime version is outside the range the adapter supports, so the deploy stops before writing. `msg-1115` is a warning that the runtime is newer than the version the adapter was tested against, and the deploy continues. `stratarc adapter status` compares every adapter with its installed runtime.

## The Check Exits 6

`stratarc check` exits 6 when a runtime differs from what the source renders. Run `stratarc diff` to see each file. If the difference is a hand edit you want to keep, move it into the source; if it is not, `stratarc sync` replaces it.

## The Home Cannot Be Written

Exit 3 with `msg-1003` or `msg-1118` means `~/.stratarc` is missing or not writable. Make it writable, or point at another home with `--home` or `STRATARC_HOME`.
