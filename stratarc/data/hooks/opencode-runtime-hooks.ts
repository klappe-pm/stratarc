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

// The registry belongs to the installation this plugin was loaded from. An
// installed bridge lives at <target>/plugins/, so its registry is
// <target>/hooks/hooks.json, whatever target stratarc was configured with and
// whatever HOME says. A copy loaded from anywhere else (the packaged source,
// for one) falls back to the default target under HOME.
function resolveHookRoot(): string {
  const dir = ((import.meta as { dir?: string }).dir ?? "").replace(/\/+$/, "")
  const slash = dir.lastIndexOf("/")
  if (slash >= 0 && dir.slice(slash + 1) === "plugins") return `${dir.slice(0, slash)}/hooks`
  return `${home}/.config/opencode/hooks`
}

const hookRoot = resolveHookRoot()

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

// A missing or unreadable registry is reported, so it is never mistaken for
// an installation that registers no hooks on purpose (an empty object).
async function loadRegistry(): Promise<Registry> {
  const path = `${hookRoot}/hooks.json`
  const file = Bun.file(path)
  if (!(await file.exists())) {
    console.error(`stratarc hooks: no hook registry at ${path}; no hooks will run`)
    return {}
  }
  try {
    const parsed = JSON.parse(await file.text())
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed as Registry
    console.error(`stratarc hooks: the hook registry at ${path} is not a JSON object; no hooks will run`)
  } catch {
    console.error(`stratarc hooks: the hook registry at ${path} is not valid JSON; no hooks will run`)
  }
  return {}
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

// One file an apply_patch touches: the operation, the path it names, the
// destination of a move, and the lines the patch adds to it.
type PatchFile = { operation: "add" | "update" | "delete"; path: string; move_to?: string; content: string }

// Reads every file header of an apply_patch body (*** Add File, *** Update
// File with an optional *** Move to, *** Delete File). A patch that names no
// file, or carries a header this bridge does not know, is malformed: it
// returns an error rather than a reduced reading, so a hook never judges part
// of an operation as if it were all of it.
function parsePatch(patch: string): { files: PatchFile[] } | { error: string } {
  const files: PatchFile[] = []
  let current: PatchFile | undefined
  for (const line of patch.split("\n")) {
    const header = /^\*\*\* (Add File|Update File|Delete File|Move to): (.+)$/.exec(line)
    if (header) {
      const [, kind, path] = header
      if (kind === "Move to") {
        if (!current || current.operation !== "update") return { error: `"*** Move to: ${path}" does not follow an Update File header` }
        current.move_to = path
        continue
      }
      current = { operation: kind === "Add File" ? "add" : kind === "Update File" ? "update" : "delete", path, content: "" }
      files.push(current)
      continue
    }
    if (/^\*\*\* (Begin Patch|End Patch|End of File)\s*$/.test(line)) continue
    if (line.startsWith("*** ")) return { error: `unrecognized patch header "${line}"` }
    if (current && line.startsWith("+") && !line.startsWith("+++")) current.content += (current.content ? "\n" : "") + line.slice(1)
  }
  if (files.length === 0) return { error: "the patch names no file" }
  return { files }
}

// The tool_input payloads one tool call is checked with. Write and Edit are
// one payload in Claude Code's shape. apply_patch is one payload per affected
// path, a move's destination included, so a hook that reads file_path sees
// every file; each payload also carries the whole patch (files, patch_text)
// for a hook that wants the operation entire. A patch that cannot be read
// blocks before the tool runs (strict); after it ran, the hooks get the raw
// patch and the reason it could not be read, since there is nothing to block.
function editedInputs(tool: string, args: Args, strict: boolean): Args[] | undefined {
  const filePath = value(args, "filePath", "file_path")
  if (tool === "write") return [{ file_path: filePath, content: value(args, "content") }]
  if (tool === "edit") return [{ file_path: filePath, old_string: value(args, "oldString", "old_string"), new_string: value(args, "newString", "new_string") }]
  if (tool !== "apply_patch") return undefined
  const patch = value(args, "patchText", "patch_text")
  const parsed = parsePatch(patch)
  if ("error" in parsed) {
    if (strict) throw new Error(`stratarc hooks: cannot check apply_patch: ${parsed.error}`)
    return [{ file_path: "", content: "", files: [], patch_text: patch, parse_error: parsed.error }]
  }
  const inputs: Args[] = []
  for (const file of parsed.files) {
    const base = { operation: file.operation, content: file.content, files: parsed.files, patch_text: patch }
    inputs.push({ file_path: file.path, ...base })
    if (file.move_to) inputs.push({ file_path: file.move_to, move_from: file.path, ...base })
  }
  return inputs
}

function toolPayloads(event: string, sessionID: string, cwd: string, tool: string, args: Args, callID?: string): { name: string; bodies: string[] } {
  const name = TOOL_NAMES[tool] ?? tool
  const inputs = editedInputs(tool, args, event === "PreToolUse") ?? [args]
  return { name, bodies: inputs.map((input) => payload(event, sessionID, cwd, name, input, callID)) }
}

// Runs the hooks for one tool event, once per payload. A tool call no hook
// matches is never parsed, so a patch this bridge cannot read blocks only
// when a hook would have checked it.
async function dispatchTool(registry: Registry, event: string, sessionID: string, cwd: string, tool: string, args: Args, callID?: string): Promise<void> {
  const name = TOOL_NAMES[tool] ?? tool
  if (commandsFor(registry, event, name).length === 0) return
  const { bodies } = toolPayloads(event, sessionID, cwd, tool, args, callID)
  for (const body of bodies) await dispatch(registry, event, body, cwd, name)
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
      await dispatchTool(registry, "PreToolUse", id, cwd, input.tool, output.args, input.callID)
    },
    "tool.execute.after": async (input: { tool: string; sessionID?: string; sessionId?: string; callID?: string; args: Args }) => {
      const id = input.sessionID || input.sessionId || ""
      await dispatchTool(registry, "PostToolUse", id, cwd, input.tool, input.args, input.callID)
    },
  }
}
