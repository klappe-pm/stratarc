# Add a Hook

A hook is a script a runtime runs when something happens in a session, such as before a tool call. You write the script once and register it once, and Stratarc deploys it into every runtime that has a hook system, translated to that runtime's format.

## Write the Script

Create `hooks/<kebab-name>.sh` in the source root and make it executable. The runtime sends the event payload as JSON on standard input. For a `PreToolUse` hook, exit 2 blocks the tool call and returns whatever you wrote to standard error to the agent; exit 0 allows it.

```bash
#!/usr/bin/env bash
# Refuse a git add or git commit that names a local database file.
set -euo pipefail

payload="$(cat)"

if printf '%s' "$payload" | grep -Eq 'git +(add|commit).*\.(db|sqlite3?)'; then
  printf 'refusing to stage a local database file\n' >&2
  exit 2
fi

exit 0
```

```bash
chmod +x ~/stratarc-source/hooks/block-database-commits.sh
```

## Register It

Add the script to `hooks/hooks.json`, which maps a canonical event to groups of hooks:

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "$HOME/.claude/hooks/block-database-commits.sh",
          "timeout": 3
        }
      ]
    }
  ]
}
```

- The event is one of `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `UserPromptSubmit`, `SessionStart`, `SubagentStart` or `SubagentStop`.
- `matcher` is a tool name pattern and is optional. Leave it out to match every tool.
- `command` always names the Claude Code location, `$HOME/.claude/hooks/<script>`. Each adapter rewrites the path for its runtime.
- `timeout` is in seconds. Adapters convert it to the runtime's own unit.

## Deploy

```bash
cd ~/stratarc-source && stratarc reconcile
```

`reconcile` adds a `hook:block-database-commits` row to `control-plane.md` under the event's table, on for `global` and off for projects. Then:

```bash
cd ~/stratarc-source && stratarc sync
```

## What Each Runtime Does With It

| runtime | where the registration goes | notes |
| --- | --- | --- |
| Claude Code | `hooks` in `settings.json` | the native format |
| Codex | `hooks.json` | the path points into `~/.codex/hooks` |
| Gemini CLI | `hooks` in `settings.json` | events are renamed, for example `PreToolUse` becomes `BeforeTool`, and timeouts become milliseconds |
| Cursor | `hooks.json` | entries are flat, and a matcher naming `Bash` becomes `Shell` |
| OpenCode | `hooks/hooks.json` | a small plugin that Stratarc deploys reads this registry and runs the commands |

An event a runtime cannot express is dropped, and the sync output says so. Hooks that were already in a runtime's settings and that Stratarc does not own are left in place.

## Shared Helpers

When a sync deploys hooks it also copies a small library to `hooks/lib/` in each runtime: `guard-utils.sh` holds the token-shaped value detector, `secret-scan.sh` scans text with it, and `log.sh` is a logging helper. A script of yours can `source` them from `$HOME/.claude/hooks/lib/` (the path is rewritten per runtime), and your own files in `hooks/lib/` are copied beside them.

## Test a Hook Without a Runtime

Feed the script a payload by hand:

```bash
printf '{"tool_name":"Bash","tool_input":{"command":"git add notes.db"}}' | ~/stratarc-source/hooks/block-database-commits.sh; echo "exit $?"
```
