# Worktrees

Stratarc recognizes linked Git worktrees, but project delivery does not automatically sync every worktree of a repository. Global runtime configuration, project configuration and permission discovery use different scopes.

## Global Runtime Configuration

Configuration rendered into the runtime directories under the configured home directory is shared by sessions using that home, including sessions opened in different worktrees. Changing the checked-out branch does not select a separate global runtime configuration.

## Project Checkout Discovery

For an active managed project, Stratarc searches beneath the configured projects directory for a folder with the project's name. It checks these layouts:

```text
<projects>/<project>
<projects>/<folder>/<project>
<projects>/<folder>/<group>/<project>
```

A candidate must be a directory with an existing `.git` entry. Both a primary checkout's `.git` directory and a linked worktree's `.git` file qualify. Discovery matches directory names; it does not enumerate a repository's worktrees through Git or select a target by branch.

Exactly one matching checkout is required for project delivery. If multiple candidates match, Stratarc reports the project as ambiguous and skips delivery to all of them. It does not prefer the primary checkout or a particular branch. If no candidate matches, it reports a missing checkout and skips delivery.

Paths containing a component beginning with `.` or `_` are excluded from project discovery. A worktree pool beneath such a directory does not create duplicate matches, but those worktrees receive no direct project delivery through this discovery mechanism. Worktrees outside the searched layouts, or with a different folder name, are likewise not automatically associated with the managed project.

The implementation is in [checkout discovery](../../stratarc/control_plane.py) and [project resolution](../../stratarc/projects.py).

## Duplicate Checkout Example

Consider a primary checkout and a detached worktree arranged as follows:

```text
~/projects/active/hub
~/projects/active/program-freeze/hub
```

Both paths match the managed project named `hub`. A full sync therefore skips project delivery to both and reports:

```text
skip: hub is ambiguous, 2 checkouts: ~/projects/active/hub, ~/projects/active/program-freeze/hub
```

The detached state of the second worktree does not change this result. Verification can report zero drift for the targets it checked while still listing this project as skipped. A successful verification result should be read together with its skipped-target count.

## Configuration Inside a Worktree

A worktree receives tracked configuration files from its checked-out revision. Uncommitted generated changes and ignored local configuration in another checkout do not automatically appear there. Later changes committed on another branch appear only when brought into the worktree's revision through normal Git operations, unless configuration is delivered there separately.

Existing worktrees can therefore retain older project instructions even when the global runtime configuration has been refreshed. The current project resolver does not provide automatic delivery to every worktree.

## Permissions and Trust

Permission and trust discovery uses a separate repository scan beneath the policy's additional directories. Linked worktrees, nested repositories and submodules qualify because each has a `.git` entry. This scan is bounded by its configured walk depth and pruned directories.

A worktree can consequently receive applicable permission or trust configuration without being selected for managed project delivery. Recognition by the permission scan does not mean its project instructions were refreshed. See [permission discovery](../../stratarc/permissions.py).

## Source Checkout Protection

When the configuration source itself is a linked worktree, Stratarc uses Git's common directory to identify the primary source checkout. Project delivery refuses both the active source checkout and its primary checkout. It also checks for source-tree content so a source checkout is protected when Git cannot resolve its identity. See [source checkout protection](../../stratarc/projects.py).

## Current Limitation

Supporting multiple checkouts without ambiguity would require an explicit primary-checkout selection policy, with a separate policy for delivering configuration to additional worktrees. The current resolver requires a single discoverable checkout per active managed project.
