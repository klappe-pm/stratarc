"""Ask installed runtimes to parse synthetic output, without credentials or inference.

Run from the checkout with `python3 scripts/verify-runtime-config.py`.
Only temporary source and home directories are read or written by the runtimes.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stratarc import companions, setup
from stratarc.registry import _detection_environment


def main() -> int:
    results = []
    for runtime, arguments in (
        ("claude", ["mcp", "get", "stratarc-fixture"]),
        ("codex", ["mcp", "list", "--json"]),
        ("opencode", ["debug", "config"]),
    ):
        executable = shutil.which(runtime)
        if executable is None:
            results.append({"runtime": runtime, "result": "missing"})
            continue
        with tempfile.TemporaryDirectory(prefix=f"stratarc-compat-{runtime}-") as temporary:
            home = Path(temporary)
            source = home / "source"
            setup.scaffold(source)
            target = home / ({"opencode": ".config/opencode"}.get(runtime, f".{runtime}"))
            target.mkdir(parents=True)
            (source / "components.json").write_text(json.dumps({
                "version": 1,
                "mcp_servers": [{"name": "stratarc-fixture", "wanted": True, "owner": "stratarc", "runtimes": [runtime], "command": "echo", "args": ["fixture"]}],
            }))
            env = _detection_environment(str(home))
            env.update({"XDG_CONFIG_HOME": str(home / ".config"), "CODEX_HOME": str(home / ".codex"), "CLAUDE_CONFIG_DIR": str(home / ".claude"), "OPENCODE_CONFIG_DIR": str(target)})
            env.pop("CLAUDE_CONFIG_DIR", None)
            previous = {key: os.environ.get(key) for key in ("STRATARC_HOME", "STRATARC_SOURCE")}
            os.environ.update({"STRATARC_HOME": str(home), "STRATARC_SOURCE": str(source)})
            try:
                adapter = importlib.import_module(f"stratarc.adapters.{runtime}")
                adapter.sync(source, target)
                companions.sync(runtime, source, target)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            try:
                version = subprocess.run([executable, "--version"], env=env, cwd=home, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
                parsed = subprocess.run([executable, *arguments], env=env, cwd=home, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
                accepted = parsed.returncode == 0 and "stratarc-fixture" in parsed.stdout
                if runtime == "codex" and accepted:
                    accepted = any(server.get("name") == "stratarc-fixture" for server in json.loads(parsed.stdout))
                result = {"runtime": runtime, "version": version.stdout.strip(), "result": "passed" if accepted else "failed", "exit": parsed.returncode}
                if not accepted:
                    result["diagnostic"] = (parsed.stderr or parsed.stdout)[:1000]
                results.append(result)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                results.append({"runtime": runtime, "result": "failed", "error": type(error).__name__})
    print(json.dumps({"evidence": "native parsing of synthetic MCP and runtime configuration; no inference or live server connection is verified", "runtimes": results}, indent=2))
    return 0 if all(item["result"] == "passed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
