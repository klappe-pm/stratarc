# Antigravity CLI

This page is the reference for what Stratarc writes into the Antigravity CLI (`agy`) target, `~/.gemini/antigravity-cli/` by default. Antigravity CLI receives the selected skills and the default model. The adapter is `stratarc/adapters/agy.py`.

## Target

`runtimes.agy.target` in `stratarc.toml`, default `~/.gemini/antigravity-cli`. The directory sits inside Gemini CLI's, and each adapter writes only its own files. `permissions.json` must list it under `runtimeDirectories`.

## Outputs

| output | built from | notes |
| --- | --- | --- |
| `skills/<name>/` | `skills/` | one directory per skill, added and updated; nothing is deleted by a sync |
| `settings.json`, `model` | `runtime_settings.agy` in `components.json` | the one key written, and only when `runtime_settings.agy.model` is set; every other key is left as it was |

## Model

Antigravity CLI serves models from several providers (Gemini, Claude and GPT-OSS), and `settings.json` holds the model's label, as `/model` saves it. `runtime_settings.agy.model` is translated through `runtime_settings.agy.aliases`, so a short name such as `opus` or a provider-qualified id such as `google-antigravity/gemini-3.1-pro-high` can map to the label:

```json
{
  "runtime_settings": {
    "agy": {
      "model": "opus",
      "aliases": {
        "opus": "Claude Opus 4.6 (Thinking)",
        "google-antigravity/gemini-3.1-pro-high": "Gemini 3.1 Pro (High)"
      }
    }
  }
}
```

A Claude short name with no alias, and `inherit`, are not written, and a sync names the Claude name it skipped. A `settings.json` that is not a JSON object is left alone.

## Hook Events

Antigravity CLI has no hook registry this adapter renders. Every canonical event is listed in `hook_events` as a deliberate drop.

## Not Written

Instructions are not written here: Antigravity CLI reads `~/.gemini/GEMINI.md`, which the [Gemini CLI](gemini.md) adapter writes. Hooks, commands, agents, permissions and MCP servers are not rendered. A sync names a selected MCP server it cannot render instead of dropping it silently.
