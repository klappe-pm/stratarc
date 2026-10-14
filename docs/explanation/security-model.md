# Security Model

This page explains what Stratarc protects against and how, for a reader deciding whether to trust it with their runtime configuration. It says why each protection exists and what it does not cover. To report a vulnerability, follow [Security](../../SECURITY.md).

## What Stratarc Trusts

The source root is trusted input. Stratarc renders what it finds there, and a source root can run Python of its own: adapters in `adapters/`, validator checks and project renderers in `scripts/private/`. Loading one is a decision made by whoever owns that directory, so keep it in a repository you control and review it as code.

The runtime directories are output Stratarc owns in part. It writes only the files it produces, merges into shared settings files without removing keys it does not own, and never deletes anything on a sync. Deleting is `prune`, which removes only what an adapter says it owns and lists first with `--dry-run`.

## Where It Will Write

A sync writes into a runtime directory only when that directory is listed in `runtimeDirectories` in `permissions.json` and already exists. A target that is missing from the list is refused, so a mistyped `target` in `stratarc.toml` cannot send files somewhere unexpected. Writes into `~/.stratarc` use mode 0700 and 0600, copy the file they replace into `backups/` first and replace it atomically. A file written by a newer Stratarc is never rewritten by an older one.

## Secrets

Stratarc never reads, stores or resolves a secret. Configuration refers to one by name, as `secret://namespace/key`, and whatever resolves that name at launch is outside Stratarc. Three checks keep a literal out of the files it handles:

- `components.json` refuses a value that looks like a credential, and its message names the entry and key but never repeats the value. The detector matches private key blocks, cloud and source host tokens, `sk`-prefixed API keys, JWTs, bearer tokens and long values assigned to a name containing `key`, `token` or `secret`.
- `check` reports a literal secret found in a runtime's own files, by file and key, never by value.
- The change log stores digests rather than content, and every text value passes the same detector before it is written. If the detector cannot run, the value is replaced and nothing unredacted is written.

A server whose environment uses a `secret://` reference is not rendered into a runtime file, because writing the reference would only give the runtime a string it cannot resolve. The sync output names it.

## Protection Against a Stale Source

Each runtime directory carries a stamp recording the policy version, source checkout and commit that wrote it. A deploy that would replace a newer policy version with an older one is refused. This stops a stale checkout from silently reverting a permission change, which is the failure that is easiest to miss.

## Public Repositories

A repository listed in `projects-root/public-targets.json` receives nothing: no delivered file, no control-plane column and no permission rewrite. A list that exists but cannot be read stops the run instead of being treated as empty, because reading it as empty would treat the one checkout the file protects as an ordinary project.

## What Stratarc Does Not Cover

It does not sandbox the runtimes. The permission policy is translated into each runtime's own enforcement, and how well a runtime enforces it is the runtime's responsibility. It does not inspect the content of hook scripts, skills or commands you write. And it does not make a runtime directory safe to share: the files it writes are readable by whoever can read your home directory.
