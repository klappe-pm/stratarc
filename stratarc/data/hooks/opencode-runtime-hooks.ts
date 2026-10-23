// The stratarc hook bridge for OpenCode.
//
// OpenCode has no hook registry of its own, so hooks are a local plugin. This
// plugin reads the registry stratarc deploys beside the hook scripts
// (hooks/hooks.json, in Claude Code's shape: event, then groups with an
// optional matcher and a list of commands) and runs every command registered
// for an OpenCode event, with the payload on standard input. Nothing about a
// particular hook is built in, so the hooks a source root registers work here
// the way they do on every other runtime.
//
// A command that exits non-zero blocks the tool call. A command that prints a
// JSON object with hookSpecificOutput.permissionDecision "deny" blocks it with
// the reason it gives. A command whose script was not deployed exits 127 and
// is skipped, so a missing optional hook never blocks a tool call.

const home = process.env.HOME ?? ""
const hookRoot = `${home}/.config/opencode/hooks`

type Args = Record<string, unknown>
type Hook = { command?: string }
type Group = { matcher?: string; hooks?: Hook[] }
type Registry = Record<string, Group[]>
type SessionEvent = { type: string; properties?: { sessionID?: string; info?: { id?: string; parentID?: string } } }

// OpenCode's lower-case tool names, spelled the way Claude Code's matchers are.
const TOOL_NAMES: Record<string, string> = {
  bash: "Bash",
  read: "Read",
  write: "Write",
  edit: "Edit",
  apply_patch: "Write",
  task: "Task",
  glob: "Glob",
  grep: "Grep",
  list: "LS",
  webfetch: "WebFetch",
  todowrite: "TodoWrite",
}

async function loadRegistry(): Promise<Registry> {
  const file = Bun.file(`${hookRoot}/hooks.json`)
  if (!(await file.exists())) return {}
  try {
    const parsed = JSON.parse(await file.text())
    return parsed && typeof parsed === "object" ? (parsed as Registry) : {}
  } catch {
    return {}
  }
}

function matcherAccepts(matcher: string | undefined, tool: string | undefined): boolean {
  if (!matcher || tool === undefined) return true
  try {
    return new RegExp(`^(?:${matcher})$`).test(tool)
  } catch {
    return false
  }
}

function commandsFor(registry: Registry, event: string, tool?: string): string[] {
  const commands: string[] = []
  for (const group of registry[event] ?? []) {
    if (!matcherAccepts(group.matcher, tool)) continue
    for (const hook of group.hooks ?? []) if (hook.command) commands.push(hook.command)
  }
  return commands
}

function value(args: Args, ...names: string[]): string {
  for (const name of names) {
    const candidate = args[name]
    if (typeof candidate === "string") return candidate
  }
  return ""
}

// callID is OpenCode's id for one tool call, carried as tool_use_id so a hook
// can pair a PreToolUse with its PostToolUse.
function payload(event: string, sessionID: string, cwd: string, toolName?: string, toolInput?: Args, callID?: string): string {
  return JSON.stringify({ hook_event_name: event, session_id: sessionID, cwd, tool_name: toolName, tool_input: toolInput, tool_use_id: callID })
}

// SessionStart's payload, with source "startup" because session.created fires
// once, when a session is new.
function sessionStartPayload(sessionID: string, cwd: string): string {
  return JSON.stringify({ hook_event_name: "SessionStart", session_id: sessionID, cwd, source: "startup" })
}

// A task subagent runs in a child session: the child's session.created is the
// start signal and the child going idle or being deleted is the stop signal.
function subagentPayload(event: string, parentID: string, childID: string, cwd: string): string {
  return JSON.stringify({ hook_event_name: event, session_id: parentID, agent_id: childID, cwd })
}

async function run(command: string, input: string, cwd: string): Promise<void> {
  const child = Bun.spawn(["bash", "-c", command], { cwd, stdin: "pipe", stdout: "pipe", stderr: "inherit", env: { ...process.env, HOME: home } })
  child.stdin.write(input)
  child.stdin.end()
  const stdout = await new Response(child.stdout).text()
  const exitCode = await child.exited
  if (exitCode === 127) return
  if (exitCode !== 0) throw new Error(`${command} failed with exit code ${exitCode}`)
  if (!stdout) return
  try {
    const response = JSON.parse(stdout)
    const output = response?.hookSpecificOutput
    if (output?.permissionDecision === "deny") throw new Error(output.permissionDecisionReason || "Hook denied this action")
  } catch (error) {
    if (error instanceof SyntaxError) return
    throw error
  }
}

async function dispatch(registry: Registry, event: string, input: string, cwd: string, tool?: string): Promise<void> {
  for (const command of commandsFor(registry, event, tool)) await run(command, input, cwd)
}

function editedInput(tool: string, args: Args): Args | undefined {
  const filePath = value(args, "filePath", "file_path")
  if (tool === "write") return { file_path: filePath, content: value(args, "content") }
  if (tool === "edit") return { file_path: filePath, old_string: value(args, "oldString", "old_string"), new_string: value(args, "newString", "new_string") }
  if (tool !== "apply_patch") return undefined
  const patch = value(args, "patchText", "patch_text")
  const files = [...patch.matchAll(/^\*\*\* (?:Add|Update) File: (.+)$/gm)].map((match) => match[1])
  const additions = patch.split("\n").filter((line) => line.startsWith("+") && !line.startsWith("+++")).map((line) => line.slice(1)).join("\n")
  return { file_path: files[0] ?? "", content: additions }
}

function toolPayload(event: string, sessionID: string, cwd: string, tool: string, args: Args, callID?: string): { name: string; body: string } {
  const edit = editedInput(tool, args)
  const name = TOOL_NAMES[tool] ?? tool
  return { name, body: payload(event, sessionID, cwd, name, edit ?? args, callID) }
}

export const StratarcHooks = async ({ directory, worktree }: { directory: string; worktree?: string }) => {
  const cwd = worktree || directory
  const registry = await loadRegistry()
  // child session id -> parent session id, for every child seen created.
  const children = new Map<string, string>()
  return {
    event: async ({ event }: { event: SessionEvent }) => {
      const info = event.properties?.info
      if (event.type === "session.created") {
        if (info?.parentID) {
          children.set(info.id ?? "", info.parentID)
          await dispatch(registry, "SubagentStart", subagentPayload("SubagentStart", info.parentID, info.id ?? "", cwd), cwd)
          return
        }
        await dispatch(registry, "SessionStart", sessionStartPayload(info?.id ?? "", cwd), cwd)
        return
      }
      if (event.type === "session.idle" || event.type === "session.deleted") {
        const childID = event.properties?.sessionID || info?.id || ""
        const parentID = children.get(childID) || info?.parentID
        if (!parentID) return
        children.delete(childID)
        await dispatch(registry, "SubagentStop", subagentPayload("SubagentStop", parentID, childID, cwd), cwd)
      }
    },
    "tool.execute.before": async (input: { tool: string; sessionID?: string; sessionId?: string; callID?: string }, output: { args: Args }) => {
      const id = input.sessionID || input.sessionId || ""
      const { name, body } = toolPayload("PreToolUse", id, cwd, input.tool, output.args, input.callID)
      await dispatch(registry, "PreToolUse", body, cwd, name)
    },
    "tool.execute.after": async (input: { tool: string; sessionID?: string; sessionId?: string; callID?: string; args: Args }) => {
      const id = input.sessionID || input.sessionId || ""
      const { name, body } = toolPayload("PostToolUse", id, cwd, input.tool, input.args, input.callID)
      await dispatch(registry, "PostToolUse", body, cwd, name)
    },
  }
}
