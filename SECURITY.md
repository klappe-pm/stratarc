# Security Policy

## Reporting a Vulnerability

Report vulnerabilities privately through GitHub security advisories: open the repository's Security tab and choose "Report a vulnerability", or go to <https://github.com/klappe-pm/stratarc/security/advisories/new>. Do not open a public issue, pull request or discussion for a suspected vulnerability.

Include the affected version or commit, the steps to reproduce, and the impact you observed. You will receive an acknowledgement, and the fix and disclosure are coordinated with you through the advisory.

## Scope

- The `stratarc` command and the Python package.
- The hook libraries shipped under `stratarc/data/`, including any way to leak a secret past the token-shaped value detector.
- The scaffold template and the files Stratarc writes into runtime directories, including any way to make it write outside the directories `permissions.json` allows.

Vulnerabilities in the agent runtimes themselves are out of scope; report those to their maintainers. How Stratarc treats secrets and what it trusts is described in the [Security Model](docs/explanation/security-model.md).

## Supported Versions

Only the latest release and the `main` branch receive security fixes.
