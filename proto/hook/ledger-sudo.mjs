// Claude Code PreToolUse hook: anything that is not a read-only command goes to the Ledger Secure Screen before it runs.
// stdin: hook JSON {tool_name, tool_input:{command|file_path}, cwd}. exit 0 = allow, exit 2 = block (stderr goes back to Claude).
// `node ledger-sudo.mjs --checkpoint`: human signs "CHECKPOINT <last hash> <n> entries" so a truncated log is detectable.
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Fail closed: a crash or unhandled rejection exits 2; exit 1 would let the command run.
for (const ev of ["uncaughtException", "unhandledRejection"]) process.on(ev, (e) => { console.error(`ledger-sudo: ${e?.message ?? e}`); process.exit(2); });
const die = (msg) => { console.error(`ledger-sudo: ${msg}`); process.exit(2); };

const LOG = fileURLToPath(new URL("../log/session.jsonl", import.meta.url));
const lines = (() => { try { return readFileSync(LOG, "utf8").split("\n").filter(Boolean); } catch { return []; } })();
const prev = lines.length ? JSON.parse(lines.at(-1)).hash : "0".repeat(64);
// ponytail: read prev then append, no lock. Two hooks at once could fork the chain (README, Honest limits).
function append(entry) {
  mkdirSync(fileURLToPath(new URL("../log/", import.meta.url)), { recursive: true });
  const e = { ts: new Date().toISOString(), ...entry, prev };
  e.hash = createHash("sha256").update(prev + JSON.stringify(e)).digest("hex");
  appendFileSync(LOG, JSON.stringify(e) + "\n");
}

// Show `text` on the device; the signature must come from the pinned LEDGER_ADDRESS, never from whoever answers on the port.
async function approve(text) {
  if (/[^\x20-\x7e]/.test(text)) die("non-printable or non-ASCII character; the device would show hex or wedge. Rewrite it as one ASCII line");
  if (text.length > 400) die("too long to read on the device; split the command");
  const address = process.env.LEDGER_ADDRESS || die("LEDGER_ADDRESS not set (ledgerd prints it at startup; put it in settings.json env)");
  let r;
  try {   // abort before Claude Code's 300 s hook timeout, otherwise the timeout runs the command (see README)
    r = await (await fetch(`http://127.0.0.1:${process.env.LEDGERD_PORT ?? 7777}/approve`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }), signal: AbortSignal.timeout(280_000) })).json();
  } catch (e) { r = { ok: false, reason: `ledgerd: ${e.message}` }; }   // fail closed
  if (r.ok && !(await (await import("viem")).verifyMessage({ address, message: text, signature: r.signature }))) r = { ok: false, reason: `signature is not from ${address}` };
  return r;
}

if (process.argv[2] === "--checkpoint") {
  const text = `CHECKPOINT ${prev} ${lines.length} entries`;
  const r = await approve(text);
  if (!r.ok) die(r.reason);
  append({ tier: null, cmd: null, cwd: null, text, signature: r.signature, address: process.env.LEDGER_ADDRESS, decision: "checkpoint" });
  console.log(text);
  process.exit(0);
}

const input = JSON.parse(readFileSync(0, "utf8"));
if (!/^(Bash|PowerShell)$/.test(input.tool_name)) {   // Edit|Write|MultiEdit: only keep the agent off this hook's own files
  if (/ledger-sudo\.mjs|settings(\.local)?\.json|session\.jsonl/.test(input.tool_input?.file_path ?? "")) die("protected file");
  process.exit(0);
}
const cmd = input.tool_input?.command ?? "";
const cwd = input.cwd ?? process.cwd();

// ponytail: allowlist, not a policy engine. tier0 = every ;/&&/||/|-separated segment starts with a read-only verb and the
// command has no shell tricks or paths that leave cwd. Everything else is shown to the human (default deny). Still a heuristic:
// `node x.mjs` and `npm test` run whatever the repo contains (README, Honest limits).
const SAFE = /^\s*(ls|dir|pwd|cat|head|tail|wc|echo|printf|grep|rg|find|which|where|file|stat|tree|diff|sort|uniq|jq|git (status|diff|log|show|branch|rev-parse|remote|ls-files|blame|add|commit|fetch)|node|npm (test|ls|view|outdated|run test)|npx (vitest|jest|tsc|eslint|prettier)|pytest|cargo (test|check|build|clippy)|make test)\b/;
const TRICKS = /[`$<>~]|\.\.|(^|[\s"'=])\/|[A-Za-z]:[\\/]|\b(eval|exec|base64|delete|iex)\b|\s-[cep]\s/;
const plain = cmd.replace(/2>&1/g, "");   // the one redirect every test runner needs
const tier = plain.split(/\|\|?|&&?|;|\n/).filter((s) => s.trim()).every((s) => SAFE.test(s)) && !TRICKS.test(plain)
  ? 0 : /\bgit\s+push\b.*(--force|-f\b|\s\+\w)/.test(cmd) ? 2 : 1;   // TODO tier2: second device co-signs; single device for now

if (tier === 0) { append({ tier, cmd, cwd, text: null, signature: null, decision: "auto" }); process.exit(0); }

// prev8 binds the line to its chain position: a signature only verifies there, so it cannot be replayed or moved.
const text = `tier${tier} ${prev.slice(0, 8)} ${cmd} cwd:${cwd}`;
const r = await approve(text);
if (r.ok) { append({ tier, cmd, cwd, text, signature: r.signature, address: process.env.LEDGER_ADDRESS, decision: "approved" }); process.exit(0); }
append({ tier, cmd, cwd, text, signature: null, decision: r.reason === "rejected" ? "rejected" : `error: ${r.reason}` });
console.error(r.reason === "rejected" ? `Rejected by human on Ledger ${r.model ?? "device"} at ${new Date().toISOString()}` : `ledger-sudo: ${r.reason}`);
process.exit(2);
