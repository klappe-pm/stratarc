// Behavioral test of stratarc/data/hooks/opencode-runtime-hooks.ts, the OpenCode
// plugin bridge. Run with `bun test`; pytest runs it when bun is installed.
//
// The bridge reads the registry stratarc deploys at
// $HOME/.config/opencode/hooks/hooks.json and runs every command registered for
// an event. HOME points at a temporary directory before the module is
// imported, and each hook there is a fake that records the payload it was sent
// and answers as the test says: a <name>.deny file makes it print a deny
// decision (the file's content is the reason), <name>.fail makes it exit 1,
// <name>.garbage makes it print non-JSON.

import { afterAll, beforeAll, beforeEach, describe, expect, test } from "bun:test"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

const HOOKS = ["bash-gate.sh", "edit-gate.sh", "after.sh", "start.sh", "sub-start.sh", "sub-stop.sh"]

// Resolved, so a hook's $PWD (macOS reports /private/var for /var) compares equal.
const root = realpathSync(mkdtempSync(join(tmpdir(), "opencode-runtime-hooks-")))
const hookDir = join(root, "home", ".config", "opencode", "hooks")
const logDir = join(root, "logs")
const worktree = join(root, "worktree")
const originalHome = process.env.HOME

type Hooks = {
  event: (input: { event: unknown }) => Promise<void>
  "tool.execute.before": (input: Record<string, unknown>, output: { args: Record<string, unknown> }) => Promise<void>
  "tool.execute.after": (input: Record<string, unknown>) => Promise<void>
}

let bridge: (context: { directory: string; worktree?: string }) => Promise<Hooks>

function command(name: string): { type: string; command: string } {
  return { type: "command", command: `$HOME/.config/opencode/hooks/${name}` }
}

const REGISTRY = {
  PreToolUse: [
    { matcher: "Bash", hooks: [command("bash-gate.sh"), command("missing.sh")] },
    { matcher: "Write|Edit", hooks: [command("edit-gate.sh")] },
  ],
  PostToolUse: [{ hooks: [command("after.sh")] }],
  SessionStart: [{ hooks: [command("start.sh")] }],
  SubagentStart: [{ hooks: [command("sub-start.sh")] }],
  SubagentStop: [{ hooks: [command("sub-stop.sh")] }],
}

function fakeHook(name: string): string {
  const base = join(logDir, name)
  return [
    "#!/bin/bash",
    "input=$(cat)",
    `printf '%s\\n' "$input" >> '${base}.log'`,
    `printf '%s\\n' "$PWD" > '${base}.cwd'`,
    `if [ -f '${base}.fail' ]; then exit 1; fi`,
    `if [ -f '${base}.garbage' ]; then echo 'not json'; fi`,
    `if [ -f '${base}.deny' ]; then`,
    `  reason=$(cat '${base}.deny')`,
    `  printf '{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$reason"`,
    "fi",
    "",
  ].join("\n")
}

// Every payload a hook received, in order.
function calls(name: string): Record<string, unknown>[] {
  const path = join(logDir, `${name}.log`)
  if (!existsSync(path)) return []
  return readFileSync(path, "utf8").trim().split("\n").map((line) => JSON.parse(line))
}

function called(): string[] {
  return HOOKS.filter((name) => calls(name).length > 0)
}

function answer(name: string, kind: "deny" | "fail" | "garbage", content = ""): void {
  writeFileSync(join(logDir, `${name}.${kind}`), content)
}

beforeAll(async () => {
  process.env.HOME = join(root, "home")
  mkdirSync(worktree, { recursive: true })
  mkdirSync(hookDir, { recursive: true })
  writeFileSync(join(hookDir, "hooks.json"), JSON.stringify(REGISTRY))
  for (const name of HOOKS) writeFileSync(join(hookDir, name), fakeHook(name), { mode: 0o755 })
  // The bridge reads HOME once, when it is imported.
  bridge = (await import(join(process.env.STRATARC_PACKAGE_DIR ?? join(import.meta.dir, "../../stratarc"), "data/hooks/opencode-runtime-hooks.ts"))).StratarcHooks
})

afterAll(() => {
  if (originalHome === undefined) delete process.env.HOME
  else process.env.HOME = originalHome
  rmSync(root, { recursive: true, force: true })
})

beforeEach(() => {
  rmSync(logDir, { recursive: true, force: true })
  mkdirSync(logDir, { recursive: true })
})

async function plugin(): Promise<Hooks> {
  return bridge({ directory: worktree })
}

describe("tool calls", () => {
  test("a Bash call runs the hooks registered for Bash with the Claude Code payload", async () => {
    const hooks = await plugin()
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1", callID: "c1" }, { args: { command: "ls" } })
    expect(called()).toEqual(["bash-gate.sh"])
    const [payload] = calls("bash-gate.sh")
    expect(payload).toMatchObject({ hook_event_name: "PreToolUse", session_id: "s1", tool_name: "Bash", tool_input: { command: "ls" }, tool_use_id: "c1" })
  })

  test("a matcher selects by tool name and an edit is reshaped to file_path and content", async () => {
    const hooks = await plugin()
    await hooks["tool.execute.before"]({ tool: "write", sessionID: "s1" }, { args: { filePath: "/x/a.md", content: "hello" } })
    expect(called()).toEqual(["edit-gate.sh"])
    expect(calls("edit-gate.sh")[0]).toMatchObject({ tool_name: "Write", tool_input: { file_path: "/x/a.md", content: "hello" } })
  })

  test("a tool no group matches runs nothing before the call", async () => {
    const hooks = await plugin()
    await hooks["tool.execute.before"]({ tool: "glob", sessionID: "s1" }, { args: { pattern: "*" } })
    expect(called()).toEqual([])
  })

  test("PostToolUse hooks run after any tool call", async () => {
    const hooks = await plugin()
    await hooks["tool.execute.after"]({ tool: "read", sessionID: "s1", args: { filePath: "/x" } })
    expect(called()).toEqual(["after.sh"])
    expect(calls("after.sh")[0]).toMatchObject({ hook_event_name: "PostToolUse", tool_name: "Read" })
  })

  test("the hook runs in the worktree", async () => {
    const hooks = await plugin()
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } })
    expect(readFileSync(join(logDir, "bash-gate.sh.cwd"), "utf8").trim()).toBe(worktree)
  })
})

describe("blocking", () => {
  test("a deny decision blocks the call with the hook's reason", async () => {
    answer("bash-gate.sh", "deny", "no database commits")
    const hooks = await plugin()
    await expect(hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "git commit" } })).rejects.toThrow("no database commits")
  })

  test("a non-zero exit blocks the call", async () => {
    answer("bash-gate.sh", "fail")
    const hooks = await plugin()
    await expect(hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } })).rejects.toThrow("exit code 1")
  })

  test("output that is not JSON does not block", async () => {
    answer("bash-gate.sh", "garbage")
    const hooks = await plugin()
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } })
    expect(called()).toEqual(["bash-gate.sh"])
  })

  test("a registered script that was not deployed exits 127 and is skipped", async () => {
    const hooks = await plugin()
    expect(existsSync(join(hookDir, "missing.sh"))).toBe(false)
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } })
    expect(called()).toEqual(["bash-gate.sh"])
  })
})

describe("sessions", () => {
  test("a new session runs SessionStart with source startup", async () => {
    const hooks = await plugin()
    await hooks.event({ event: { type: "session.created", properties: { info: { id: "root-1" } } } })
    expect(calls("start.sh")[0]).toMatchObject({ hook_event_name: "SessionStart", session_id: "root-1", source: "startup" })
  })

  test("a child session is a subagent: start and stop, never SessionStart", async () => {
    const hooks = await plugin()
    await hooks.event({ event: { type: "session.created", properties: { info: { id: "child-1", parentID: "root-1" } } } })
    expect(called()).toEqual(["sub-start.sh"])
    expect(calls("sub-start.sh")[0]).toMatchObject({ hook_event_name: "SubagentStart", session_id: "root-1", agent_id: "child-1" })
    await hooks.event({ event: { type: "session.idle", properties: { sessionID: "child-1" } } })
    expect(calls("sub-stop.sh")[0]).toMatchObject({ hook_event_name: "SubagentStop", session_id: "root-1", agent_id: "child-1" })
  })

  test("a root session going idle stops nothing", async () => {
    const hooks = await plugin()
    await hooks.event({ event: { type: "session.idle", properties: { sessionID: "root-1" } } })
    expect(called()).toEqual([])
  })
})

describe("registry", () => {
  test("a missing registry registers nothing", async () => {
    const registry = join(hookDir, "hooks.json")
    const saved = readFileSync(registry, "utf8")
    rmSync(registry)
    try {
      const hooks = await plugin()
      await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } })
      expect(called()).toEqual([])
      expect(readdirSync(hookDir)).not.toContain("hooks.json")
    } finally {
      writeFileSync(registry, saved)
    }
  })
})
