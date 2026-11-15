# Explanation

Explanation pages give background. They are for a reader who wants to understand Stratarc rather than operate it: why it is shaped the way it is, what it trusts, what tradeoffs it makes and where its boundaries lie. They can be read away from the keyboard, and they are the right place to look before proposing a change to how the tool works.

## Pages

- [Architecture](architecture.md): how one source root becomes a configuration for each runtime, stage by stage.
- [Worktrees](worktrees.md): how checkout discovery, shared runtime configuration and permissions interact with linked Git worktrees.
- [Security Model](security-model.md): what Stratarc protects against, how, what it trusts in a source root and what it leaves to the runtimes.