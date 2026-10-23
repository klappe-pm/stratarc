# Documentation

Stratarc renders one agent configuration source into any agent runtime. These pages cover installing and using it, looking things up, and changing the code. They follow the four [Diátaxis](https://diataxis.fr/) quadrants, so the folder a page sits in tells you what kind of page it is.

## Tutorials

Lessons that take you through a task from start to finish. [Getting Started](tutorials/getting-started.md) goes from an empty machine to a scaffolded source root and a first deployment. [First Contribution](tutorials/first-contribution.md) goes from a fresh clone to a passing test suite and a change ready for review. Index: [Tutorials](tutorials/README.md).

## How-To Guides

Recipes for a specific goal, for someone who already knows the basics.

- Set up: [Install](how-to-guides/install.md), [Configure Runtimes](how-to-guides/configure-runtimes.md), [Migrate Existing Config](how-to-guides/migrate-existing-config.md).
- Author: [Add a Rule](how-to-guides/add-a-rule.md), [Add a Skill, Command or Agent](how-to-guides/add-a-skill-command-or-agent.md), [Add a Hook](how-to-guides/add-a-hook.md), [Set Up a Project](how-to-guides/set-up-a-project.md), [Use the Control Plane](how-to-guides/use-the-control-plane.md).
- Operate: [Preview and Deploy](how-to-guides/preview-and-deploy.md), [Roll Back a Deploy](how-to-guides/roll-back-a-deploy.md), [Troubleshooting](how-to-guides/troubleshooting.md).
- Extend: [Add a Runtime](how-to-guides/add-a-runtime.md).
- Contribute: [Run the Tests](how-to-guides/run-the-tests.md), [Cut a Release](how-to-guides/cut-a-release.md).

Index: [How-To Guides](how-to-guides/README.md).

## Reference

Lookup pages that describe the machinery as it is. [CLI](reference/cli.md) and the generated [Commands](reference/generated/commands.md) list every command, [Configuration](reference/configuration.md) lists every key in `stratarc.toml`, [Source Layout](reference/source-layout.md) describes every file in a source root, [Control Plane](reference/control-plane.md) describes the opt-in tables, [Adapter Files](reference/adapter-files.md) is the contract for a runtime of your own, and [Runtimes](reference/runtimes/README.md) has one page per supported runtime. Index: [Reference](reference/README.md).

## Explanation

Background and reasons, for a reader who wants to understand rather than act. [Architecture](explanation/architecture.md) explains how one source root becomes several runtime configurations, [Security Model](explanation/security-model.md) explains what Stratarc protects and what it leaves to the runtimes, and [Decisions](explanation/decisions/README.md) holds the design records. Index: [Explanation](explanation/README.md).
