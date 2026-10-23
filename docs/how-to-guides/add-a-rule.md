# Add a Rule

A rule is a standing instruction every agent session follows. This guide shows how to write one, choose who it applies to and get it into your runtimes. Rules are rendered into a digest inside each runtime's instruction file, and the full text stays in your source root.

## Write the File

Create `rules/<kebab-name>.md` in the source root. The file has no frontmatter, an H1 equal to the filename stem and a `## binding` section:

```markdown
# keep-answers-short

## binding

Keep answers under five sentences unless the user asks for more.

## rationale

Long answers bury the decision. Any further sections stay in this file, which the digest links to.
```

The `## binding` section is the short normative text that lands in the digest. Keep it under 120 words; `stratarc validate` reports a longer one as an error. Everything after it is for readers of the file.

## Choose the Tier

List the filename under a tier in `rules/tiers.json`:

```json
{
  "global": [],
  "common": ["keep-answers-short.md"],
  "project": []
}
```

| tier | applies |
| --- | --- |
| `global` | everywhere, and cannot be opted out of |
| `common` | everywhere by default, and a project can opt out in the control plane |
| `project` | only where a project opts in |

A rule that is in no tier is not rendered anywhere.

## Register and Deploy

```bash
cd ~/stratarc-source && stratarc reconcile
```

`reconcile` adds a `rule:keep-answers-short` row to `control-plane.md`. Then preview and deploy:

```bash
cd ~/stratarc-source && stratarc diff
```

```bash
cd ~/stratarc-source && stratarc sync
```

`sync` refreshes the digest block in `AGENTS.md` (between the `BEGIN RULES-DIGEST` and `END RULES-DIGEST` markers, which you never edit) and copies it into each runtime's instruction file.

## Make a Rule Apply to One Project

Put the rule in the `project` tier, then open `control-plane.md` and put an `x` in that project's column on the rule's row. See [Use the Control Plane](use-the-control-plane.md). A project can also carry rules of its own that no other project sees: [Set Up a Project](set-up-a-project.md).

## Check It Landed

```bash
cd ~/stratarc-source && stratarc check
```

`check` exits 0 when every runtime matches the source and 6 when something is out of date.
